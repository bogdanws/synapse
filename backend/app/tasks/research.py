"""Research-pipeline taskiq task (stub).

This is intentionally a placeholder. The real implementation will drive the
LangGraph orchestration of Scout → Scribe → Critic and stream progress events
over Redis pubsub. For now it just sleeps so the rest of the plumbing
(enqueue → worker → WebSocket bridge) can be exercised end-to-end.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from app.tasks.broker import broker

_log = structlog.get_logger(__name__)


@broker.task(task_name="research.run_pipeline")
async def run_research_pipeline(job_id: UUID) -> None:
    """Stub pipeline runner. Replaced in a later change with the real graph."""
    _log.info("research_pipeline_stub_started", job_id=str(job_id))
