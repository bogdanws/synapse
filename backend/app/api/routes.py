"""HTTP route handlers."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_active_user
from app.auth.models import User
from app.db.session import get_db
from app.middleware.ratelimit import limiter
from app.models import orm
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
async def start_research(
    request: Request,
    payload: ResearchRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
) -> ResearchJob:
    """Persist a new research job and hand it off to the worker.

    The row is committed before the task is enqueued so the worker (which loads the job by id) is guaranteed to see it. If the enqueue fails the row is left in `pending`; a later sweep can either retry it or mark it as failed.
    """
    now = datetime.now(UTC)
    row = orm.ResearchJob(
        user_id=user.id,
        topic=payload.topic,
        language=payload.language,
        depth=payload.depth.value,
        models=dict(payload.models),
        status=JobStatus.PENDING.value,
        progress=0.0,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    await run_research_pipeline.kiq(row.id)

    return ResearchJob(
        id=row.id,
        topic=row.topic,
        language=row.language,
        depth=payload.depth,
        models=row.models,
        status=JobStatus(row.status),
        progress=row.progress,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
