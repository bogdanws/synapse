"""ORM relationship smoke test."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.models.orm import (
    CriticAnnotation,
    FollowUp,
    JobEvent,
    Report,
    ResearchJob,
    Source,
)

pytestmark = pytest.mark.integration


async def test_orm_relationships(async_session: AsyncSession) -> None:
    """Create a full graph of entities and verify relationships reload."""
    user = User(
        id=uuid.uuid4(),
        email=f"orm-test-{uuid.uuid4()}@example.com",
        hashed_password="not-a-real-hash",
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    async_session.add(user)
    await async_session.flush()

    job = ResearchJob(
        id=uuid.uuid4(),
        user_id=user.id,
        topic="ORM smoke test",
        models={"scout": "x", "scribe": "y", "critic": "z"},
    )
    async_session.add(job)
    await async_session.flush()

    source = Source(
        id=uuid.uuid4(),
        job_id=job.id,
        short_id="s1",
        url="http://example.com/s1",
        title="Source One",
        snippet="snippet",
        credibility=0.8,
        relevance=0.9,
    )
    async_session.add(source)

    report = Report(
        id=uuid.uuid4(),
        job_id=job.id,
        title="Report",
        summary_md="summary",
        body={},
        model="scribe-v1",
        generated_at=datetime.now(UTC),
    )
    async_session.add(report)
    await async_session.flush()

    annotation = CriticAnnotation(
        id=uuid.uuid4(),
        report_id=report.id,
        body={},
        overall_confidence=0.85,
        model="critic-v1",
        generated_at=datetime.now(UTC),
    )
    async_session.add(annotation)

    follow_up = FollowUp(
        id=uuid.uuid4(),
        parent_job_id=job.id,
        child_job_id=job.id,
        question="What next?",
    )
    async_session.add(follow_up)

    await async_session.commit()
    async_session.expunge_all()

    # Async SQLAlchemy cannot lazy-load relationships on attribute access; eager
    # load every relationship the assertions touch.
    result = await async_session.execute(
        select(ResearchJob)
        .where(ResearchJob.id == job.id)
        .options(
            selectinload(ResearchJob.sources),
            selectinload(ResearchJob.report).selectinload(Report.critic_annotation),
            selectinload(ResearchJob.follow_ups_as_parent),
        )
    )
    reloaded = result.scalar_one()

    assert len(reloaded.sources) == 1
    assert reloaded.report is not None
    assert reloaded.report.critic_annotation is not None
    assert len(reloaded.follow_ups_as_parent) == 1


async def test_job_events_cascade_delete(async_session: AsyncSession) -> None:
    """Deleting a research job removes its persisted event log too.

    The frontend's resume-on-reconnect path replays `JobEvent` rows; the FK
    cascade is what guarantees we don't leak orphaned events when a user
    deletes a job. Cleanup-on-completion handles the in-flight case; this
    test covers the long-tail one (job deleted long after it finished).
    """
    user = User(
        id=uuid.uuid4(),
        email=f"job-events-test-{uuid.uuid4()}@example.com",
        hashed_password="not-a-real-hash",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_superuser=False,
        is_verified=False,
    )
    async_session.add(user)
    await async_session.flush()

    job = ResearchJob(
        id=uuid.uuid4(),
        user_id=user.id,
        topic="cascade-test",
        models={"scout": "x", "scribe": "y", "critic": "z"},
    )
    async_session.add(job)
    await async_session.flush()

    for n in range(3):
        async_session.add(
            JobEvent(
                job_id=job.id,
                event={"type": "section_drafted", "ordinal": n},
            )
        )
    await async_session.commit()

    existing = (
        (await async_session.execute(select(JobEvent).where(JobEvent.job_id == job.id)))
        .scalars()
        .all()
    )
    assert len(existing) == 3
    # Ascending id ordering matches the replay query in
    # `events_service.load_history`.
    assert [e.id for e in existing] == sorted(e.id for e in existing)

    await async_session.delete(job)
    await async_session.commit()

    remaining = (
        (await async_session.execute(select(JobEvent).where(JobEvent.job_id == job.id)))
        .scalars()
        .all()
    )
    assert remaining == []
