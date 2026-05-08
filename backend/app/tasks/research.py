"""Research-pipeline taskiq task (stub).

This is intentionally a placeholder. The real implementation will drive the
LangGraph orchestration of Scout → Scribe → Critic and stream progress events
over Redis pubsub. For now it just publishes a single `JobCompleted` event so
the rest of the plumbing (enqueue → worker → pubsub → WebSocket bridge) can be
exercised end-to-end.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import structlog

from app.config import get_settings
from app.models.events import JobCompleted
from app.services.events import publish
from app.tasks.broker import broker

_log = structlog.get_logger(__name__)

# Stub-only: Redis pubsub has no replay, so a synchronous-fast stub publishes its terminal event before the browser can navigate and open a WS.
# A short delay lets manual end-to-end checks see the event flow.
# The real pipeline lands in a later change and runs for seconds-to-minutes; this delay disappears with it.
_STUB_DELAY_SECONDS = 3.0


@broker.task(task_name="research.run_pipeline")
async def run_research_pipeline(job_id: UUID) -> None:
    """Stub pipeline runner. Replaced in a later change with the real graph."""
    _log.info("research_pipeline_stub_started", job_id=str(job_id))
    if get_settings().app_env != "test":
        await asyncio.sleep(_STUB_DELAY_SECONDS)
    await publish(JobCompleted(job_id=job_id, overall_confidence=0.0))
