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

from app.agents.scout import ScoutAgent, _canonical_url, _RawSource
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

# Caps on follow-up source reuse. Without them a chain of follow-ups grows without
# bound: every child persists `seeds + fresh`, so a grandchild would seed off that
# larger set, and the single batched scoring/Scribe prompts would balloon in tokens
# and cost. `_MAX_SEED_SOURCES` bounds what we carry forward from the parent;
# `_MAX_MERGED_SEED_SOURCES` bounds the combined set a follow-up emits, which is what
# the next child sees — so each generation is bounded regardless of chain length.
_MAX_SEED_SOURCES = 20
_MAX_MERGED_SEED_SOURCES = 20


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
    sub_questions_override: list[str] | None = None,
    seed_sources: list[Source] | None = None,
) -> ScoutOutput:
    """Execute Scout end-to-end and emit progress events.

    Searches each sub-question concurrently — Exa rate limits per request, not per second, so issuing them in parallel is safe and meaningfully cuts latency on deeper runs.

    When `sub_questions_override` is supplied (user approved a preview plan), the decompose
    LLM call is skipped entirely and the provided questions are used as-is, preserving the
    user's approved plan rather than generating a new decomposition.

    `seed_sources` carries a parent job's already-gathered sources into a follow-up run. They keep the credibility/relevance the parent already assigned (we don't re-judge them — only their snippet is persisted, so re-scoring would rate them on strictly less material than the full-bodied fresh hits and bias the comparison). The seeds are capped to the strongest `_MAX_SEED_SOURCES`, any fresh hit that rediscovers a seed URL is dropped in favour of the parent copy, and the combined set is capped to `_MAX_MERGED_SEED_SOURCES` so a chain of follow-ups can't grow the source set — or the scoring/Scribe prompts — without bound.
    """
    if sub_questions_override:
        sub_questions = sub_questions_override
        _log.info("scout_using_override", job_id=str(job_id), count=len(sub_questions))
    else:
        sub_questions = await agent.decompose(topic)
        _log.info("scout_decomposed", job_id=str(job_id), count=len(sub_questions))
    await publish(SubQuestionsGenerated(job_id=job_id, sub_questions=sub_questions))

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
    if seed_sources:
        seeds = _rank_by_score(seed_sources)[:_MAX_SEED_SOURCES]
        fresh = await agent.score(topic, _drop_seed_collisions(deduped, seeds))
        scored = _reindex(_cap_by_score(seeds + fresh, _MAX_MERGED_SEED_SOURCES))
    else:
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


def _source_score(src: Source) -> float:
    """Rank key for capping: a source must be both credible and on-topic to survive."""
    return src.credibility * src.relevance


def _rank_by_score(sources: list[Source]) -> list[Source]:
    """Sort by combined score, strongest first. Stable, so ties keep their input order."""
    return sorted(sources, key=_source_score, reverse=True)


def _cap_by_score(sources: list[Source], limit: int) -> list[Source]:
    """Keep the `limit` strongest sources while preserving the input ordering of the survivors.

    Capping selects by score, but the emission/citation order is left as-is (seeds first, then fresh) rather than reordered by score.
    """
    if len(sources) <= limit:
        return sources
    keep = {id(s) for s in _rank_by_score(sources)[:limit]}
    return [s for s in sources if id(s) in keep]


def _drop_seed_collisions(fresh: list[_RawSource], seeds: list[Source]) -> list[_RawSource]:
    """Drop fresh hits that rediscover a seed URL so the parent's copy (and its score) wins."""
    seed_urls = {_canonical_url(str(s.url)) for s in seeds}
    return [r for r in fresh if _canonical_url(r.url) not in seed_urls]


def _reindex(sources: list[Source]) -> list[Source]:
    """Reassign sequential short ids (`s1`, `s2`, …) over a merged set.

    Seeds carry the ids from their parent run and freshly scored hits start again at `s1`, so a merge collides; re-indexing gives the child report one clean, unique id space for citations.
    """
    return [src.model_copy(update={"id": f"s{i + 1}"}) for i, src in enumerate(sources)]
