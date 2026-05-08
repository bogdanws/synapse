"""HTTP route handlers."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scout import ScoutAgent, ScoutValidationError
from app.auth.dependencies import current_active_user
from app.auth.models import User
from app.db.session import get_db
from app.middleware.ratelimit import limiter
from app.models import orm
from app.models.research import (
    JobStatus,
    PreviewResponse,
    ResearchJob,
    ResearchRequest,
)
from app.services.search import ExaSearchClient
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
        sub_questions_override=payload.sub_questions or None,
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
        sub_questions=row.sub_questions_override,
        status=JobStatus(row.status),
        progress=row.progress,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post(
    "/research/preview",
    response_model=PreviewResponse,
    status_code=status.HTTP_200_OK,
    tags=["research"],
)
@limiter.limit("10/minute")
async def preview_research(
    request: Request,
    payload: ResearchRequest,
    user: User = Depends(current_active_user),
) -> PreviewResponse:
    """Run only Scout's decompose step and return the proposed sub-questions.

    No job row is created and no work is queued. This is intentionally a
    synchronous preview: the caller gets sub-questions back immediately so they
    can review and drop them before committing to a full research run.
    """
    async with httpx.AsyncClient() as http:
        agent = ScoutAgent(
            model=payload.models["scout"],
            search_client=ExaSearchClient(http_client=http),
        )
        try:
            sub_questions = await agent.decompose(payload.topic)
        except ScoutValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Scout could not decompose the topic into sub-questions after retries.",
            ) from exc
    return PreviewResponse(sub_questions=sub_questions)
