"""LangGraph node wrapping `CriticAgent` with progress events.

Sections are verified in parallel; `ClaimVerified` events are streamed as each section's LLM call returns rather than waiting for the slowest one. The aggregated `CriticAnnotations` is built and globally-validated only after all sections complete.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from app.agents.critic import CriticAgent, _CriticSectionOutput
from app.agents.scout_graph import EventPublisher
from app.models.events import ClaimVerified
from app.models.research import CriticAnnotations, ScribeReport
from app.services.events import publish as default_publish

_log = structlog.get_logger(__name__)


async def run_critic(
    *,
    job_id: UUID,
    report: ScribeReport,
    agent: CriticAgent,
    publish: EventPublisher = default_publish,
) -> CriticAnnotations:
    """Execute Critic over a `ScribeReport` and emit per-flag progress events."""
    if not report.sections:
        # Defensive: Scribe should never emit an empty report (its validator forbids it), but if it does we surface a clear failure rather than silently returning empty annotations.
        msg = "cannot critique a report with no sections"
        raise ValueError(msg)

    tasks = [
        asyncio.create_task(
            agent.verify_section(
                topic=report.topic,
                section=section,
                sources=report.sources,
            )
        )
        for section in report.sections
    ]

    section_outputs: list[_CriticSectionOutput] = []
    try:
        for completed in asyncio.as_completed(tasks):
            output = await completed
            section_outputs.append(output)
            for flag in output.claim_flags:
                await publish(ClaimVerified(job_id=job_id, flag=flag))
    except BaseException:
        # If any section fails (validation exhausted or LLM errored out) the partial work in flight is no longer useful; cancel sibling tasks before propagating so we don't leak background coroutines.
        for task in tasks:
            if not task.done():
                task.cancel()
        # Drain cancellations so the event loop closes cleanly.
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    annotations = agent.aggregate(report, section_outputs)
    _log.info(
        "critic_complete",
        job_id=str(job_id),
        section_count=len(annotations.section_confidence),
        flag_count=len(annotations.claim_flags),
        overall_confidence=annotations.overall_confidence,
    )
    return annotations
