"""LangGraph node wrapping `ScribeAgent` with progress events.

The agent makes a single LLM call and returns the whole report at once; the node validates that report (already done inside the agent's retry loop), then replays it to subscribers as a stream of `SectionDrafted` events followed by `ScribeComplete`. This matches the contract Critic and the frontend expect without committing the project to per-section LLM calls yet.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from app.agents.scout_graph import EventPublisher
from app.agents.scribe import ScribeAgent
from app.models.events import ScribeComplete, SectionDrafted
from app.models.research import ScribeReport, Source
from app.services.events import publish as default_publish

_log = structlog.get_logger(__name__)


async def run_scribe(
    *,
    job_id: UUID,
    topic: str,
    sub_questions: list[str],
    sources: list[Source],
    agent: ScribeAgent,
    publish: EventPublisher = default_publish,
) -> ScribeReport:
    """Execute Scribe end-to-end and emit per-section progress events."""
    report = await agent.synthesize(
        job_id=job_id,
        topic=topic,
        sub_questions=sub_questions,
        sources=sources,
    )
    for section in report.sections:
        await publish(SectionDrafted(job_id=job_id, section=section))
    await publish(ScribeComplete(job_id=job_id))
    _log.info(
        "scribe_complete",
        job_id=str(job_id),
        section_count=len(report.sections),
    )
    return report
