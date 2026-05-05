"""HTTP route handlers."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, status

from app.models.research import (
    JobStatus,
    ResearchJobResponse,
    ResearchRequest,
)

router = APIRouter()


@router.post(
    "/research",
    response_model=ResearchJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["research"],
)
async def start_research(payload: ResearchRequest) -> ResearchJobResponse:
    """Queue a new research job.

    TODO: persist job to DB, push to Redis queue, hand off to orchestrator.
    """
    job_id: UUID = uuid4()
    return ResearchJobResponse(
        id=job_id,
        topic=payload.topic,
        status=JobStatus.PENDING,
        progress=0.0,
    )
