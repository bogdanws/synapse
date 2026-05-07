"""ORM relationship smoke test."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.models.orm import CriticAnnotation, FollowUp, Report, ResearchJob, Source

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
