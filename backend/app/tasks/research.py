"""Research-pipeline taskiq task.

Thin shim: the broker wires `run_research_pipeline(job_id)` to `app.agents.orchestrator.run_pipeline`, which owns the actual graph execution, persistence, and event emission. Keeping this module thin means changes to the pipeline don't require touching task registration.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from app.agents.orchestrator import run_pipeline
from app.db.session import async_session_factory
from app.tasks.broker import broker

_log = structlog.get_logger(__name__)


@broker.task(task_name="research.run_pipeline")
async def run_research_pipeline(job_id: UUID) -> None:
    """Drive the Scout → Scribe → Critic pipeline for a persisted job."""
    _log.info("research_pipeline_started", job_id=str(job_id))
    await run_pipeline(
        job_id=job_id,
        session_factory=async_session_factory,
    )
    _log.info("research_pipeline_finished", job_id=str(job_id))
