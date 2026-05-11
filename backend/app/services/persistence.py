"""Database writers for the research pipeline.

Wraps the ORM in narrow async methods so the orchestrator and graph nodes don't have to know SQLAlchemy. Each method takes a session, modifies it, and leaves the commit decision to the caller — that lets the orchestrator group several writes (e.g. report + annotations + status update) into one transaction.

The module assumes the parent `research_jobs` row already exists; creating the row is the API layer's job.

Source content (`Source.content`) is not persisted here yet because the API-boundary `Source` Pydantic model intentionally omits it. When the LLM-judged Critic learns to read full source bodies, threading the raw content through the graph state will be a separate, contained change.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import Integer, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import orm
from app.models.research import (
    ClaimFlag,
    Contradiction,
    CriticAnnotations,
    JobStatus,
    ReportSection,
    ScribeReport,
    SectionConfidence,
    Source,
    Verdict,
    VerifiedReport,
)
from app.models.research import (
    ResearchJob as ResearchJobModel,
)

_log = structlog.get_logger(__name__)


class JobNotFoundError(LookupError):
    """Raised when the orchestrator is asked to run a job whose row doesn't exist."""


class ReportNotFoundError(RuntimeError):
    """Raised when a job exists but its report has not been persisted yet."""


class JobRepository:
    """Per-job reads and writes. Construct one per session; not thread-safe."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_job(self, job_id: UUID, *, user_id: UUID | None = None) -> ResearchJobModel:
        """Load a job row and convert it to the API model used by the orchestrator.

        When `user_id` is supplied the lookup is restricted to that owner; a job that exists but belongs to someone else surfaces as `JobNotFoundError` so we don't leak existence across tenants. Pass `None` only from trusted internal callers (e.g. the orchestrator) that must read any job.
        """
        if user_id is None:
            row = await self._session.get(orm.ResearchJob, job_id)
        else:
            stmt = select(orm.ResearchJob).where(
                orm.ResearchJob.id == job_id,
                orm.ResearchJob.user_id == user_id,
            )
            row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            msg = f"research job {job_id} not found"
            raise JobNotFoundError(msg)
        return _to_research_job(row)

    async def get_report(self, job_id: UUID, *, user_id: UUID | None = None) -> VerifiedReport:
        """Reconstruct a VerifiedReport from the ORM rows for a completed job.

        When `user_id` is supplied the lookup is restricted to that owner; a job that exists but belongs to someone else surfaces as `JobNotFoundError` so we don't leak existence across tenants. Pass `None` only from trusted internal callers (e.g. the orchestrator) that must read any job.
        """
        stmt = select(orm.ResearchJob).where(orm.ResearchJob.id == job_id)
        if user_id is not None:
            stmt = stmt.where(orm.ResearchJob.user_id == user_id)
        # Async ORM cannot perform implicit lazy IO on plain attribute access
        # (`row.report`) outside SQLAlchemy's greenlet bridge. Eager-loading
        # prevents MissingGreenlet in FastAPI handlers.
        stmt = stmt.options(
            selectinload(orm.ResearchJob.report).selectinload(orm.Report.critic_annotation),
            selectinload(orm.ResearchJob.sources),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            msg = f"research job {job_id} not found"
            raise JobNotFoundError(msg)

        report_row = row.report
        if report_row is None:
            msg = f"report for job {job_id} not yet available"
            raise ReportNotFoundError(msg)

        report = _from_report_row(row, report_row)

        annotation_row = report_row.critic_annotation
        if annotation_row is None:
            msg = f"annotations for job {job_id} not yet available"
            raise ReportNotFoundError(msg)

        annotations = _from_annotation_row(annotation_row)

        return VerifiedReport(
            job=_to_research_job(row),
            report=report,
            annotations=annotations,
        )

    async def set_status(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        progress: float | None = None,
    ) -> None:
        """Update the status (and optionally progress) of a job in flight."""
        row = await self._require_row(job_id)
        row.status = status.value
        if progress is not None:
            row.progress = progress

    async def mark_completed(self, job_id: UUID) -> None:
        row = await self._require_row(job_id)
        row.status = JobStatus.COMPLETED.value
        row.progress = 1.0
        row.completed_at = datetime.now(UTC)
        row.error = None

    async def mark_failed(self, job_id: UUID, error: str) -> None:
        row = await self._require_row(job_id)
        row.status = JobStatus.FAILED.value
        row.error = error
        row.completed_at = datetime.now(UTC)

    async def replace_sources(self, job_id: UUID, sources: list[Source]) -> None:
        """Persist Scout's sources, replacing any prior set for this job.

        Replace-rather-than-merge keeps the table consistent with the in-memory `state["sources"]` after a node retry: short_ids are reassigned per run, so a partial overlay would risk duplicate or stale rows.
        """
        await self._session.execute(delete(orm.Source).where(orm.Source.job_id == job_id))
        for src in sources:
            self._session.add(_to_source_orm(job_id, src))

    async def save_report(self, job_id: UUID, report: ScribeReport) -> UUID:
        """Persist a Scribe report; replaces any existing report for the job. Returns the new row id."""
        await self._session.execute(delete(orm.Report).where(orm.Report.job_id == job_id))
        row = orm.Report(
            id=report.id,
            job_id=job_id,
            title=report.title,
            summary_md=report.summary_md,
            body=_report_body_jsonb(report),
            model=report.model,
            generated_at=report.generated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def save_annotations(self, report_id: UUID, annotations: CriticAnnotations) -> UUID:
        """Persist Critic's annotations for a report; replaces any existing annotation row."""
        await self._session.execute(
            delete(orm.CriticAnnotation).where(orm.CriticAnnotation.report_id == report_id)
        )
        row = orm.CriticAnnotation(
            id=annotations.id,
            report_id=report_id,
            body=annotations.model_dump(mode="json"),
            overall_confidence=annotations.overall_confidence,
            model=annotations.model,
            generated_at=annotations.generated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return row.id

    async def _require_row(self, job_id: UUID) -> orm.ResearchJob:
        row = await self._session.get(orm.ResearchJob, job_id)
        if row is None:
            msg = f"research job {job_id} not found"
            raise JobNotFoundError(msg)
        return row


# ---- mapping helpers --------------------------------------------------------


def _to_research_job(row: orm.ResearchJob) -> ResearchJobModel:
    return ResearchJobModel(
        id=row.id,
        topic=row.topic,
        language=row.language,
        depth=row.depth,  # type: ignore[arg-type]
        models=row.models,
        sub_questions=row.sub_questions_override,
        status=JobStatus(row.status),
        progress=row.progress,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def _to_source_orm(job_id: UUID, src: Source) -> orm.Source:
    return orm.Source(
        job_id=job_id,
        short_id=src.id,
        url=str(src.url),
        title=src.title,
        author=src.author,
        published_at=src.published_at,
        snippet=src.snippet,
        content=None,
        credibility=src.credibility,
        relevance=src.relevance,
    )


def _from_report_row(job_row: orm.ResearchJob, report_row: orm.Report) -> ScribeReport:
    """Reconstruct a ScribeReport Pydantic model from the ORM row and its JSONB body.

    The JSONB body stores the fields that don't have dedicated columns; see `_report_body_jsonb` for the write path.
    """
    body = report_row.body
    sources = [
        Source(
            id=s["id"],
            url=s["url"],
            title=s["title"],
            author=s.get("author"),
            published_at=s.get("published_at"),
            credibility=s["credibility"],
            relevance=s["relevance"],
            snippet=s["snippet"],
        )
        for s in body.get("sources", [])
    ]
    sections = [ReportSection(**sec) for sec in body.get("sections", [])]
    contradictions = [Contradiction(**c) for c in body.get("contradictions", [])]
    follow_ups: list[str] = list(body.get("follow_ups", []))
    return ScribeReport(
        id=body["id"],
        job_id=job_row.id,
        topic=body["topic"],
        title=report_row.title,
        summary_md=report_row.summary_md,
        sections=sections,
        sources=sources,
        contradictions=contradictions,
        follow_ups=follow_ups,
        generated_at=report_row.generated_at,
        model=report_row.model,
    )


def _from_annotation_row(row: orm.CriticAnnotation) -> CriticAnnotations:
    """Reconstruct CriticAnnotations from its JSONB body column."""
    body = row.body
    section_confidence = [SectionConfidence(**sc) for sc in body.get("section_confidence", [])]
    claim_flags = [
        ClaimFlag(
            claim_id=cf["claim_id"],
            section_id=cf["section_id"],
            verdict=Verdict(cf["verdict"]),
            rationale=cf["rationale"],
            supporting_source_ids=cf.get("supporting_source_ids", []),
        )
        for cf in body.get("claim_flags", [])
    ]
    return CriticAnnotations(
        id=body["id"],
        report_id=body["report_id"],
        section_confidence=section_confidence,
        claim_flags=claim_flags,
        overall_confidence=row.overall_confidence,
        model=row.model,
        generated_at=row.generated_at,
    )


def _report_body_jsonb(report: ScribeReport) -> dict[str, object]:
    """Serialise the parts of a `ScribeReport` that don't have dedicated columns.

    The hot fields (`title`, `summary_md`, `model`, `generated_at`) live in real columns for indexability; everything else is one JSONB blob so the schema can evolve without a migration until v1 ships.
    """
    return {
        "id": str(report.id),
        "topic": report.topic,
        "sections": [s.model_dump(mode="json") for s in report.sections],
        "sources": [s.model_dump(mode="json") for s in report.sources],
        "contradictions": [c.model_dump(mode="json") for c in report.contradictions],
        "follow_ups": list(report.follow_ups),
    }


async def load_sources(session: AsyncSession, job_id: UUID) -> list[Source]:
    """Read sources back as Pydantic models. Used by the API layer when serving `/research/{job_id}`.

    Lives here next to the writers so the JSONB shape stays in one place.
    """
    rows = (
        (
            await session.execute(
                select(orm.Source)
                .where(orm.Source.job_id == job_id)
                .order_by(cast(func.substr(orm.Source.short_id, 2), Integer))
            )
        )
        .scalars()
        .all()
    )
    return [
        Source(
            id=r.short_id,
            url=r.url,  # type: ignore[arg-type]
            title=r.title,
            author=r.author,
            published_at=r.published_at,
            credibility=r.credibility,
            relevance=r.relevance,
            snippet=r.snippet,
        )
        for r in rows
    ]
