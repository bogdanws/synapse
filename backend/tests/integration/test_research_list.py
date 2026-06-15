"""Integration coverage for `JobRepository.list_jobs` against Postgres.

Exercises the real joins (sources count, critic annotation confidence, the follow-up parent edge),
user scoping, newest-first ordering, and offset pagination. The endpoint's query-param clamping is
unit-tested separately in `tests/unit/test_research_endpoint.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.models.orm import CriticAnnotation, FollowUp, Report, ResearchJob, Source
from app.models.research import JobStatus
from app.services.persistence import JobRepository

pytestmark = pytest.mark.integration


async def _user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"history-{uuid.uuid4()}@example.com",
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


def _job(
    user_id: uuid.UUID,
    topic: str,
    *,
    status: JobStatus,
    created_at: datetime,
) -> ResearchJob:
    return ResearchJob(
        id=uuid.uuid4(),
        user_id=user_id,
        topic=topic,
        models={"scout": "x", "scribe": "y", "critic": "z"},
        status=status.value,
        created_at=created_at,
        updated_at=created_at,
    )


def _source(job_id: uuid.UUID, short_id: str) -> Source:
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


async def test_list_jobs_scoping_ordering_and_derived_fields(async_session: AsyncSession) -> None:
    owner = await _user(async_session)
    other = await _user(async_session)

    failed = _job(
        owner.id,
        "Failed brief",
        status=JobStatus.FAILED,
        created_at=datetime(2026, 6, 10, tzinfo=UTC),
    )
    in_progress = _job(
        owner.id,
        "Scouting brief",
        status=JobStatus.SCOUTING,
        created_at=datetime(2026, 6, 11, tzinfo=UTC),
    )
    completed = _job(
        owner.id,
        "Completed brief",
        status=JobStatus.COMPLETED,
        created_at=datetime(2026, 6, 12, tzinfo=UTC),
    )
    child = _job(
        owner.id,
        "Follow-up brief",
        status=JobStatus.COMPLETED,
        created_at=datetime(2026, 6, 13, tzinfo=UTC),
    )
    others_job = _job(
        other.id,
        "Other tenant",
        status=JobStatus.COMPLETED,
        created_at=datetime(2026, 6, 14, tzinfo=UTC),
    )
    async_session.add_all([failed, in_progress, completed, child, others_job])
    await async_session.flush()

    # completed: report + annotation (confidence) + 2 sources; in_progress: 1 source; failed: none.
    async_session.add_all([_source(completed.id, "s1"), _source(completed.id, "s2")])
    async_session.add(_source(in_progress.id, "s1"))
    report = Report(
        id=uuid.uuid4(),
        job_id=completed.id,
        title="R",
        summary_md="s",
        body={"follow_ups": ["How did exits change in 2024?", "Which sectors recovered first?"]},
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
            parent_job_id=completed.id,
            child_job_id=child.id,
            question="And what about exits?",
        )
    )
    await async_session.commit()

    result = await JobRepository(async_session).list_jobs(owner.id, limit=20, offset=0)

    # Only the owner's four jobs, newest first.
    assert result.total == 4
    assert [i.topic for i in result.items] == [
        "Follow-up brief",
        "Completed brief",
        "Scouting brief",
        "Failed brief",
    ]

    by_topic = {i.topic: i for i in result.items}
    assert by_topic["Completed brief"].source_count == 2
    assert by_topic["Completed brief"].overall_confidence == pytest.approx(0.9)
    assert by_topic["Scouting brief"].source_count == 1
    assert by_topic["Scouting brief"].overall_confidence is None
    assert by_topic["Failed brief"].source_count == 0
    assert by_topic["Failed brief"].overall_confidence is None

    # Follow-up edge surfaces the parent for the badge/link; roots have no parent.
    assert by_topic["Follow-up brief"].parent_job_id == completed.id
    assert by_topic["Follow-up brief"].parent_topic == "Completed brief"
    assert by_topic["Completed brief"].parent_job_id is None
    assert by_topic["Completed brief"].follow_ups == [
        "How did exits change in 2024?",
        "Which sectors recovered first?",
    ]
    assert by_topic["Failed brief"].follow_ups == []


async def test_list_jobs_pagination(async_session: AsyncSession) -> None:
    owner = await _user(async_session)
    for n in range(5):
        async_session.add(
            _job(
                owner.id,
                f"Brief {n}",
                status=JobStatus.COMPLETED,
                created_at=datetime(2026, 6, 10 + n, tzinfo=UTC),
            )
        )
    await async_session.commit()

    repo = JobRepository(async_session)
    first = await repo.list_jobs(owner.id, limit=2, offset=0)
    second = await repo.list_jobs(owner.id, limit=2, offset=2)

    assert first.total == 5
    assert second.total == 5
    assert len(first.items) == 2
    assert len(second.items) == 2
    # No overlap between consecutive pages.
    assert {i.id for i in first.items}.isdisjoint({i.id for i in second.items})
    # Newest-first: page 1 starts at the most recent.
    assert first.items[0].topic == "Brief 4"
