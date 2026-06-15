"""Integration coverage for `JobRepository.delete_job` against Postgres.

Proves the database-level cascade (sources, report, annotation, follow-up edges) fires on a single
job delete, that follow-up *children* survive as standalone jobs, and that the delete is scoped to
the owner so another tenant's job is never touched.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.models.orm import CriticAnnotation, FollowUp, Report, ResearchJob, Source
from app.models.research import JobStatus
from app.services.persistence import JobNotFoundError, JobRepository

pytestmark = pytest.mark.integration


async def _user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"delete-{uuid.uuid4()}@example.com",
        hashed_password="not-a-real-hash",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    session.add(user)
    await session.flush()
    return user


def _job(user_id: uuid.UUID, topic: str) -> ResearchJob:
    now = datetime.now(UTC)
    return ResearchJob(
        id=uuid.uuid4(),
        user_id=user_id,
        topic=topic,
        models={"scout": "x", "scribe": "y", "critic": "z"},
        status=JobStatus.COMPLETED.value,
        created_at=now,
        updated_at=now,
    )


async def _count(session: AsyncSession, model: type, **filters: object) -> int:
    stmt = select(func.count()).select_from(model)
    for attr, value in filters.items():
        stmt = stmt.where(getattr(model, attr) == value)
    return (await session.execute(stmt)).scalar_one()


async def test_delete_job_cascades_and_orphans_children(async_session: AsyncSession) -> None:
    owner = await _user(async_session)
    parent = _job(owner.id, "Parent brief")
    child = _job(owner.id, "Follow-up brief")
    async_session.add_all([parent, child])
    await async_session.flush()

    async_session.add_all([_source_row(parent.id, "s1"), _source_row(parent.id, "s2")])
    report = Report(
        id=uuid.uuid4(),
        job_id=parent.id,
        title="R",
        summary_md="s",
        body={},
        model="scribe-v1",
        generated_at=datetime.now(UTC),
    )
    async_session.add(report)
    await async_session.flush()
    async_session.add(
        CriticAnnotation(
            id=uuid.uuid4(),
            report_id=report.id,
            body={},
            overall_confidence=0.9,
            model="critic-v1",
            generated_at=datetime.now(UTC),
        )
    )
    async_session.add(
        FollowUp(
            id=uuid.uuid4(),
            parent_job_id=parent.id,
            child_job_id=child.id,
            question="And what about exits?",
        )
    )
    await async_session.commit()

    await JobRepository(async_session).delete_job(parent.id, user_id=owner.id)
    await async_session.commit()

    # The parent and everything hanging off it is gone.
    assert await _count(async_session, ResearchJob, id=parent.id) == 0
    assert await _count(async_session, Source, job_id=parent.id) == 0
    assert await _count(async_session, Report, job_id=parent.id) == 0
    assert await _count(async_session, CriticAnnotation, report_id=report.id) == 0
    # The follow-up edge is removed, but the child job survives as a standalone brief.
    assert await _count(async_session, FollowUp, parent_job_id=parent.id) == 0
    assert await _count(async_session, ResearchJob, id=child.id) == 1


async def test_delete_job_is_scoped_to_owner(async_session: AsyncSession) -> None:
    owner = await _user(async_session)
    other = await _user(async_session)
    job = _job(other.id, "Other tenant's brief")
    async_session.add(job)
    await async_session.commit()

    with pytest.raises(JobNotFoundError):
        await JobRepository(async_session).delete_job(job.id, user_id=owner.id)

    # The other tenant's job is untouched.
    assert await _count(async_session, ResearchJob, id=job.id) == 1


def _source_row(job_id: uuid.UUID, short_id: str) -> Source:
    return Source(
        id=uuid.uuid4(),
        job_id=job_id,
        short_id=short_id,
        url=f"http://example.com/{short_id}",
        title=f"Source {short_id}",
        snippet="snippet",
        credibility=0.8,
        relevance=0.9,
    )
