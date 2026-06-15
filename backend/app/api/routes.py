"""HTTP route handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scout import ScoutAgent, ScoutValidationError
from app.auth.dependencies import current_active_user
from app.auth.models import User
from app.db.session import get_db
from app.middleware.ratelimit import limiter
from app.models import orm
from app.models.research import (
    FollowUpRequest,
    JobLineage,
    JobStatus,
    PreviewResponse,
    ResearchJob,
    ResearchRequest,
    VerifiedReport,
)
from app.services.export import build_markdown, render_pdf
from app.services.persistence import JobNotFoundError, JobRepository, ReportNotFoundError
from app.services.search import ExaSearchClient
from app.tasks.research import run_research_pipeline

router = APIRouter(dependencies=[Depends(current_active_user)])

# Longest follow-up chain we allow (root -> child -> ... ). Each generation reuses
# the previous one's sources, so an unbounded chain is both a cost and a
# coherence risk; cap it and surface the limit as a 409 rather than silently
# spawning ever-deeper threads.
_MAX_FOLLOW_UP_DEPTH = 5


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


@router.post(
    "/research/{job_id}/follow-up",
    response_model=ResearchJob,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["research"],
)
@limiter.limit("4/minute")
async def start_follow_up(
    request: Request,
    job_id: UUID,
    payload: FollowUpRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
) -> ResearchJob:
    """Spawn a child research job that follows up on a completed report.

    The child inherits the parent's language, depth, and per-agent models, and its single sub-question is the follow-up question — so the worker skips Scout's decompose step. The orchestrator separately seeds the child with the parent's sources (resolved via the FollowUp edge written here), so the run reuses the parent's evidence on top of a fresh, question-scoped search. Follow-up chains are capped at `_MAX_FOLLOW_UP_DEPTH`.
    """
    repo = JobRepository(session)
    try:
        parent = await repo.get_job(job_id, user_id=user.id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.") from exc

    if parent.status is not JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a completed report can be followed up.",
        )

    if await repo.get_follow_up_depth(job_id, limit=_MAX_FOLLOW_UP_DEPTH) >= _MAX_FOLLOW_UP_DEPTH:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Follow-up chains are limited to {_MAX_FOLLOW_UP_DEPTH} levels.",
        )

    now = datetime.now(UTC)
    child = orm.ResearchJob(
        user_id=user.id,
        topic=payload.question,
        language=parent.language,
        depth=parent.depth.value,
        models=dict(parent.models),
        sub_questions_override=[payload.question],
        status=JobStatus.PENDING.value,
        progress=0.0,
        created_at=now,
        updated_at=now,
    )
    # The child job and its parent edge must land atomically: a child without the
    # edge would run as a fresh root job (no parent sources) and orphan itself from
    # the lineage. `flush` assigns `child.id` so the edge can reference it; the
    # single `commit` makes both rows visible together.
    session.add(child)
    await session.flush()
    session.add(
        orm.FollowUp(parent_job_id=job_id, child_job_id=child.id, question=payload.question)
    )
    await session.commit()

    await run_research_pipeline.kiq(child.id)

    return await repo.get_job(child.id, user_id=user.id)


@router.get(
    "/research/{job_id}/lineage",
    response_model=JobLineage,
    status_code=status.HTTP_200_OK,
    tags=["research"],
)
async def get_job_lineage(
    job_id: UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
) -> JobLineage:
    """Return a job's immediate follow-up lineage: its parent (if any) and its children."""
    try:
        return await JobRepository(session).get_lineage(job_id, user_id=user.id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.") from exc


@router.get(
    "/research/{job_id}/report",
    response_model=VerifiedReport,
    status_code=status.HTTP_200_OK,
    tags=["research"],
)
async def get_report(
    job_id: UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
) -> VerifiedReport:
    repo = JobRepository(session)
    try:
        # Restrict the lookup to this user so other tenants' jobs surface as 404, not 200.
        return await repo.get_report(job_id, user_id=user.id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.") from exc
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet available — job may still be running.",
        ) from exc


@router.get(
    "/research/{job_id}/export/markdown",
    tags=["research"],
)
async def export_markdown(
    job_id: UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    repo = JobRepository(session)
    try:
        verified = await repo.get_report(job_id, user_id=user.id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.") from exc
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet available — job may still be running.",
        ) from exc

    md_str = build_markdown(verified)
    return Response(
        content=md_str,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="synapse-report-{job_id}.md"'},
    )


@router.get(
    "/research/{job_id}/export/pdf",
    tags=["research"],
)
async def export_pdf(
    job_id: UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    repo = JobRepository(session)
    try:
        verified = await repo.get_report(job_id, user_id=user.id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.") from exc
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet available — job may still be running.",
        ) from exc

    pdf_bytes = await render_pdf(verified)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="synapse-report-{job_id}.pdf"'},
    )
