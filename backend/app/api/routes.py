"""HTTP route handlers."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, status

from app.auth.dependencies import current_active_user
from app.middleware.ratelimit import limiter
from app.models.research import (
    JobStatus,
    ResearchJob,
    ResearchRequest,
)
from app.tasks.research import run_research_pipeline

router = APIRouter(dependencies=[Depends(current_active_user)])


@router.post(
    "/research",
    response_model=ResearchJob,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["research"],
)
@limiter.limit("4/minute")
async def start_research(request: Request, payload: ResearchRequest) -> ResearchJob:
    """Queue a new research job and hand it off to the worker.

    Persistence to Postgres is wired in a later change; for now the job descriptor is returned synthetically and the heavy work runs in the taskiq worker process.
    """
    job_id: UUID = uuid4()
    await run_research_pipeline.kiq(job_id)
    return ResearchJob(
        id=job_id,
        topic=payload.topic,
        language=payload.language,
        depth=payload.depth,
        models=payload.models,
        status=JobStatus.PENDING,
        progress=0.0,
    )
