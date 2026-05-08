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

from app.models import orm
from app.models.research import (
    CriticAnnotations,
    JobStatus,
    ScribeReport,
    Source,
)
from app.models.research import (
    ResearchJob as ResearchJobModel,
)

_log = structlog.get_logger(__name__)


class JobNotFoundError(LookupError):
    """Raised when the orchestrator is asked to run a job whose row doesn't exist."""


class JobRepository:
    """Per-job reads and writes. Construct one per session; not thread-safe."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_job(self, job_id: UUID) -> ResearchJobModel:
        """Load a job row and convert it to the API model used by the orchestrator."""
        row = await self._session.get(orm.ResearchJob, job_id)
        if row is None:
            msg = f"research job {job_id} not found"
            raise JobNotFoundError(msg)
        return _to_research_job(row)

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
