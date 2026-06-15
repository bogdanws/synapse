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
from sqlalchemy.orm import aliased, selectinload

from app.models import orm
from app.models.research import (
    ClaimFlag,
    Contradiction,
    CriticAnnotations,
    FollowUpLink,
    JobLineage,
    JobListResponse,
    JobStatus,
    JobSummary,
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

    async def list_jobs(self, user_id: UUID, *, limit: int, offset: int) -> JobListResponse:
        """Return the user's jobs newest-first, with derived source count, confidence, and parent edge.

        `source_count` is a correlated COUNT (0 when Scout hasn't written sources yet);
        `overall_confidence` comes from the Critic annotations and is NULL until the job completes;
        `parent_job_id`/`parent_topic` come from the at-most-one `FollowUp` child edge so the UI can
        badge follow-up jobs and link back to the parent. `follow_ups` is extracted from the report
        body's `follow_ups` array *in SQL* (`body['follow_ups']`) rather than selecting the whole
        JSONB document, so this hot, paginated query never detoasts/transfers/parses the full report.
        Ordering carries a secondary `id` key so offset paging stays stable when `created_at` ties.
        """
        parent = aliased(orm.ResearchJob)
        source_count = (
            select(func.count())
            .select_from(orm.Source)
            .where(orm.Source.job_id == orm.ResearchJob.id)
            .scalar_subquery()
        )
        stmt = (
            select(
                orm.ResearchJob,
                source_count,
                orm.CriticAnnotation.overall_confidence,
                orm.FollowUp.parent_job_id,
                parent.topic,
                orm.Report.body["follow_ups"],
            )
            .outerjoin(orm.Report, orm.Report.job_id == orm.ResearchJob.id)
            .outerjoin(orm.CriticAnnotation, orm.CriticAnnotation.report_id == orm.Report.id)
            .outerjoin(orm.FollowUp, orm.FollowUp.child_job_id == orm.ResearchJob.id)
            .outerjoin(parent, parent.id == orm.FollowUp.parent_job_id)
            .where(orm.ResearchJob.user_id == user_id)
            .order_by(orm.ResearchJob.created_at.desc(), orm.ResearchJob.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).all()

        total_stmt = (
            select(func.count())
            .select_from(orm.ResearchJob)
            .where(orm.ResearchJob.user_id == user_id)
        )
        total = (await self._session.execute(total_stmt)).scalar_one()

        items = [
            JobSummary(
                id=job.id,
                topic=job.topic,
                status=JobStatus(job.status),
                progress=job.progress,
                created_at=job.created_at,
                source_count=count,
                overall_confidence=confidence,
                parent_job_id=parent_job_id,
                parent_topic=parent_topic,
                follow_ups=list(follow_ups or []),
            )
            for job, count, confidence, parent_job_id, parent_topic, follow_ups in rows
        ]
        return JobListResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_follow_up_parent_id(self, child_job_id: UUID) -> UUID | None:
        """Return the parent job id if `child_job_id` was spawned as a follow-up, else None.

        Used by the orchestrator to decide whether to seed Scout with the parent's sources. A job has at most one parent edge.
        """
        stmt = select(orm.FollowUp.parent_job_id).where(orm.FollowUp.child_job_id == child_job_id)
        return (await self._session.execute(stmt)).scalars().first()

    async def get_follow_up_depth(self, job_id: UUID, *, limit: int) -> int:
        """Count follow-up ancestors above `job_id` (0 for a root), stopping once `limit` is reached.

        Walks parent edges one indexed point-lookup at a time. The caller only needs to know whether a new child would exceed a depth cap, so the walk short-circuits at `limit` rather than resolving the full chain — and that bound doubles as a guard against a pathological cycle (which shouldn't exist: a child is always created after its parent).
        """
        depth = 0
        current = job_id
        while depth < limit:
            parent = await self.get_follow_up_parent_id(current)
            if parent is None:
                break
            depth += 1
            current = parent
        return depth

    async def get_lineage(self, job_id: UUID, *, user_id: UUID | None = None) -> JobLineage:
        """Resolve a job's immediate follow-up lineage: its parent (if any) and its children.

        Ownership is enforced on the anchor job only; the linked jobs always belong to the same user because a follow-up inherits the parent's owner. When `user_id` is supplied a job owned by someone else surfaces as `JobNotFoundError` rather than leaking existence.
        """
        owner_stmt = select(orm.ResearchJob.id).where(orm.ResearchJob.id == job_id)
        if user_id is not None:
            owner_stmt = owner_stmt.where(orm.ResearchJob.user_id == user_id)
        if (await self._session.execute(owner_stmt)).scalar_one_or_none() is None:
            msg = f"research job {job_id} not found"
            raise JobNotFoundError(msg)

        parent_stmt = (
            select(orm.FollowUp, orm.ResearchJob)
            .join(orm.ResearchJob, orm.ResearchJob.id == orm.FollowUp.parent_job_id)
            .where(orm.FollowUp.child_job_id == job_id)
        )
        parent_row = (await self._session.execute(parent_stmt)).first()
        parent = _to_follow_up_link(parent_row[1], parent_row[0]) if parent_row else None

        children_stmt = (
            select(orm.FollowUp, orm.ResearchJob)
            .join(orm.ResearchJob, orm.ResearchJob.id == orm.FollowUp.child_job_id)
            .where(orm.FollowUp.parent_job_id == job_id)
            .order_by(orm.FollowUp.created_at)
        )
        children_rows = (await self._session.execute(children_stmt)).all()
        children = [_to_follow_up_link(job, fu) for fu, job in children_rows]

        return JobLineage(parent=parent, children=children)

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

    async def delete_job(self, job_id: UUID, *, user_id: UUID) -> None:
        """Delete a job and everything hanging off it: sources, report, annotations, events, and the FollowUp edges that reference it.

        Scoped to the owner — a job that exists but belongs to someone else surfaces as `JobNotFoundError` so we don't leak existence across tenants. Every child FK is `ondelete="CASCADE"`, so the DELETE on the job row cascades at the database level (no ORM object load needed). Follow-up children survive: only the FollowUp edge rows are removed, so derived jobs become standalone rather than disappearing.
        """
        owned = select(orm.ResearchJob.id).where(
            orm.ResearchJob.id == job_id,
            orm.ResearchJob.user_id == user_id,
        )
        if (await self._session.execute(owned)).scalar_one_or_none() is None:
            msg = f"research job {job_id} not found"
            raise JobNotFoundError(msg)
        await self._session.execute(delete(orm.ResearchJob).where(orm.ResearchJob.id == job_id))

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


def _to_follow_up_link(job_row: orm.ResearchJob, fu_row: orm.FollowUp) -> FollowUpLink:
    """Build a `FollowUpLink` describing the job on one end of a follow-up edge.

    `job_row` is the linked job (parent or child); `fu_row` carries the question and edge timestamp.
    """
    return FollowUpLink(
        job_id=job_row.id,
        question=fu_row.question,
        topic=job_row.topic,
        status=JobStatus(job_row.status),
        created_at=fu_row.created_at,
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
