"""LangGraph node wrapping `ScoutAgent` with event publishing.

Kept in its own module so the agent itself stays free of pubsub plumbing — this is the seam tests use to exercise the agent without standing up Redis.

The node publishes four events:
  - `SubQuestionsGenerated` after `decompose`,
  - `SourceFound` per source as Exa results stream in,
  - `SourceScored` per source after the relevance/credibility pass,
  - `ScoutComplete` at the end.

`SourceFound` is emitted with a `relevance=0`/`credibility=0` placeholder Source because the score isn't known yet; the matching `SourceScored` event carries the final values keyed by `source_id`. The frontend updates the existing card in place when the score event arrives.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import structlog

from app.agents.scout import ScoutAgent, _RawSource
from app.models.events import (
    ProgressEvent,
    ScoutComplete,
    SourceFound,
    SourceScored,
    SubQuestionsGenerated,
)
from app.models.research import Source
from app.services.events import publish as default_publish

_log = structlog.get_logger(__name__)

EventPublisher = Callable[[ProgressEvent], Awaitable[None]]


@dataclass(slots=True, frozen=True)
class ScoutOutput:
    """What downstream nodes (Scribe) need from a successful Scout run."""

    sub_questions: list[str]
    sources: list[Source]


async def run_scout(
    *,
    job_id: UUID,
    topic: str,
    agent: ScoutAgent,
    publish: EventPublisher = default_publish,
) -> ScoutOutput:
    """Execute Scout end-to-end and emit progress events.

    Searches each sub-question concurrently — Exa rate limits per request, not per second, so issuing them in parallel is safe and meaningfully cuts latency on deeper runs.
    """
    sub_questions = await agent.decompose(topic)
    await publish(SubQuestionsGenerated(job_id=job_id, sub_questions=sub_questions))
    _log.info("scout_decomposed", job_id=str(job_id), count=len(sub_questions))

    raw_per_question = await asyncio.gather(
        *(agent.search(q) for q in sub_questions),
        return_exceptions=True,
    )
    raw_sources: list[_RawSource] = []
    for q, result in zip(sub_questions, raw_per_question, strict=True):
        if isinstance(result, BaseException):
            # One failed sub-question shouldn't sink the whole job; the others may still cover the topic. Surface the failure in logs and carry on.
            _log.warning("scout_search_failed", job_id=str(job_id), query=q, error=str(result))
            continue
        raw_sources.extend(result)

    deduped = await agent.deduplicate(raw_sources)
    scored = await agent.score(topic, deduped)

    # Emit `SourceFound` first for every retained source so the UI can render
    # cards before any scores have settled, then `SourceScored` to fill in the
    # numbers. Two passes keeps the event order semantically meaningful.
    for src in scored:
        await publish(SourceFound(job_id=job_id, source=_unscored_view(src)))
    for src in scored:
        await publish(
            SourceScored(
                job_id=job_id,
                source_id=src.id,
                credibility=src.credibility,
                relevance=src.relevance,
            )
        )

    await publish(ScoutComplete(job_id=job_id, source_count=len(scored)))
    _log.info("scout_complete", job_id=str(job_id), source_count=len(scored))
    return ScoutOutput(sub_questions=sub_questions, sources=scored)


def _unscored_view(src: Source) -> Source:
    """Return a copy with credibility/relevance zeroed out for the discovery event."""
    return src.model_copy(update={"credibility": 0.0, "relevance": 0.0})
