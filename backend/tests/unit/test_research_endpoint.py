"""Tests for POST /api/research, POST /api/research/preview, and GET /api/research/{job_id}/report."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.scout import ScoutValidationError
from app.auth.dependencies import current_active_user
from app.db.session import get_db
from app.main import app
from app.models import orm
from app.models.research import (
    ClaimFlag,
    CriticAnnotations,
    Depth,
    JobStatus,
    ResearchJob,
    ScribeReport,
    SectionConfidence,
    Source,
    Verdict,
    VerifiedReport,
)
from app.models.research import ReportSection as ReportSectionModel
from app.services.persistence import JobNotFoundError, ReportNotFoundError

_VALID_MODELS = {
    "scout": "openai/gpt-4o-mini",
    "scribe": "openai/gpt-4o",
    "critic": "openai/gpt-4o",
}


class _FakeSession:
    """Minimal async session that records adds, commits, and refreshes.

    Stamps an id and timestamps onto the row at flush time so the route can
    return the persisted view without hitting a real database.
    """

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: Any) -> None:
        # Real SQLAlchemy populates the server-default columns at this point;
        # the route only reads `id`, `topic`, `language`, `models`, `status`,
        # `progress`, `created_at`, `updated_at` afterwards, so stamp those.
        if isinstance(obj, orm.ResearchJob):
            if obj.id is None:
                obj.id = uuid4()
            now = datetime.now(UTC)
            if obj.created_at is None:
                obj.created_at = now
            if obj.updated_at is None:
                obj.updated_at = now


@pytest.fixture
def fake_session() -> _FakeSession:
    return _FakeSession()


@pytest.fixture
async def authed_client(fake_session: _FakeSession) -> AsyncIterator[AsyncClient]:
    """Authenticated client wired to a fake DB session and a real fastapi-users User shape."""
    user_id = uuid4()

    async def _fake_current_active_user() -> Any:
        # Real users carry a UUID id; the route persists it as the FK on the
        # research_jobs row, so the test fixture must match.
        return type(
            "FakeUser",
            (),
            {"id": user_id, "email": "test@example.com", "is_active": True},
        )()

    async def _fake_get_db() -> AsyncIterator[_FakeSession]:
        yield fake_session

    app.dependency_overrides[current_active_user] = _fake_current_active_user
    app.dependency_overrides[get_db] = _fake_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(current_active_user, None)
        app.dependency_overrides.pop(get_db, None)


async def test_start_research_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/research", json={"topic": "Quantum computing", "models": _VALID_MODELS}
    )
    assert response.status_code == 401


async def test_start_research_persists_row_and_returns_pending_job(
    authed_client: AsyncClient, fake_session: _FakeSession
) -> None:
    response = await authed_client.post(
        "/api/research",
        json={"topic": "Quantum computing", "models": _VALID_MODELS},
    )
    assert response.status_code == 202
    body = response.json()

    UUID(body["id"])
    assert body["topic"] == "Quantum computing"
    assert body["status"] == "pending"
    assert body["progress"] == 0.0
    assert body["models"] == _VALID_MODELS

    # The row was committed exactly once before the response went out.
    assert fake_session.commits == 1
    assert len(fake_session.added) == 1
    persisted = fake_session.added[0]
    assert isinstance(persisted, orm.ResearchJob)
    assert persisted.topic == "Quantum computing"
    assert persisted.status == "pending"
    assert persisted.models == _VALID_MODELS


async def test_start_research_marks_job_failed_when_enqueue_fails(
    authed_client: AsyncClient, fake_session: _FakeSession
) -> None:
    """A broker failure after the row is committed must not leave the job stuck
    in `pending` — the route marks it failed and returns 503."""
    with (
        patch(
            "app.api.routes.run_research_pipeline.kiq",
            new=AsyncMock(side_effect=ConnectionError("broker down")),
        ),
        patch(
            "app.api.routes.JobRepository.mark_failed", new=AsyncMock()
        ) as mark_failed,
    ):
        response = await authed_client.post(
            "/api/research",
            json={"topic": "Quantum computing", "models": _VALID_MODELS},
        )

    assert response.status_code == 503
    mark_failed.assert_awaited_once()
    persisted = fake_session.added[0]
    assert mark_failed.await_args.args[0] == persisted.id
    # One commit for the row, one for the failed-status update.
    assert fake_session.commits == 2


@pytest.mark.parametrize("bad_topic", ["", "a", "no"])
async def test_start_research_rejects_short_topic(
    authed_client: AsyncClient, bad_topic: str
) -> None:
    response = await authed_client.post(
        "/api/research", json={"topic": bad_topic, "models": _VALID_MODELS}
    )
    assert response.status_code == 422


async def test_start_research_rejects_missing_models(
    authed_client: AsyncClient,
) -> None:
    response = await authed_client.post("/api/research", json={"topic": "Quantum computing"})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "incomplete_models",
    [
        {"scout": "m"},
        {"scout": "m", "scribe": "m"},
        {"scout": "", "scribe": "m", "critic": "m"},
    ],
)
async def test_start_research_rejects_incomplete_models(
    authed_client: AsyncClient, incomplete_models: dict[str, str]
) -> None:
    response = await authed_client.post(
        "/api/research", json={"topic": "Quantum computing", "models": incomplete_models}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/research/preview
# ---------------------------------------------------------------------------

_PREVIEW_BODY = {"topic": "Quantum computing", "models": _VALID_MODELS}


@pytest.fixture
async def authed_client_stub_db() -> AsyncIterator[AsyncClient]:
    """Authenticated client whose DB dependency yields a stub session.

    The /report and /export routes still depend on `get_db` — even when the
    repository method is patched out — so we must override it or FastAPI will
    open a real connection. Tests that need to inspect repository calls patch
    `JobRepository` directly; the session yielded here is intentionally a sentinel
    that should never receive a method call.
    """

    async def _fake_current_active_user() -> Any:
        return type(
            "FakeUser",
            (),
            {"id": uuid4(), "email": "test@example.com", "is_active": True},
        )()

    async def _fake_get_db() -> AsyncIterator[object]:
        # The patched JobRepository never touches this object; using a bare
        # sentinel makes any accidental DB I/O fail loudly.
        yield object()

    app.dependency_overrides[current_active_user] = _fake_current_active_user
    app.dependency_overrides[get_db] = _fake_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(current_active_user, None)
        app.dependency_overrides.pop(get_db, None)


async def test_preview_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/research/preview", json=_PREVIEW_BODY)
    assert response.status_code == 401


async def test_preview_returns_sub_questions(authed_client_stub_db: AsyncClient) -> None:
    with patch(
        "app.api.routes.ScoutAgent.decompose",
        new=AsyncMock(return_value=["Q1?", "Q2?", "Q3?"]),
    ):
        response = await authed_client_stub_db.post("/api/research/preview", json=_PREVIEW_BODY)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["sub_questions"], list)
    assert len(body["sub_questions"]) > 0
    assert all(isinstance(q, str) for q in body["sub_questions"])


async def test_preview_handles_scout_validation_error(authed_client_stub_db: AsyncClient) -> None:
    with patch(
        "app.api.routes.ScoutAgent.decompose",
        new=AsyncMock(side_effect=ScoutValidationError("bad")),
    ):
        response = await authed_client_stub_db.post("/api/research/preview", json=_PREVIEW_BODY)

    assert response.status_code == 422
    assert "sub-questions" in response.json()["detail"]


async def test_preview_rejects_missing_models(authed_client_stub_db: AsyncClient) -> None:
    response = await authed_client_stub_db.post(
        "/api/research/preview", json={"topic": "Quantum computing"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/research/{job_id}/report
# ---------------------------------------------------------------------------

_JOB_ID = uuid4()
_REPORT_ID = uuid4()
_ANNOTATION_ID = uuid4()
_NOW = datetime.now(UTC)


def _make_verified_report() -> VerifiedReport:
    job = ResearchJob(
        id=_JOB_ID,
        topic="Eastern European VC trends",
        language="en",
        depth=Depth.STANDARD,
        models=_VALID_MODELS,
        status=JobStatus.COMPLETED,
        progress=1.0,
        created_at=_NOW,
        updated_at=_NOW,
    )
    section = ReportSectionModel(
        id="sec1",
        heading="The 2023 inflection",
        body_md="CEE deal volume fell 41% YoY in [^s1].",
    )
    source = Source(
        id="s1",
        url="https://example.com/report",  # type: ignore[arg-type]
        title="Dealroom Q1 2026",
        credibility=0.9,
        relevance=0.85,
        snippet="CEE deal volume fell 41% YoY.",
    )
    report = ScribeReport(
        id=_REPORT_ID,
        job_id=_JOB_ID,
        topic="Eastern European VC trends",
        title="Why has Eastern European VC diverged?",
        summary_md="LP withdrawal, not founder behaviour, explains the gap.",
        sections=[section],
        sources=[source],
        contradictions=[],
        follow_ups=[],
        generated_at=_NOW,
        model="openai/gpt-4o",
    )
    section_confidence = SectionConfidence(
        section_id="sec1",
        score=0.94,
        reasoning="Both anchor figures cross-check independently.",
    )
    claim_flag = ClaimFlag(
        claim_id="sec1.c1",
        section_id="sec1",
        verdict=Verdict.SUPPORTED,
        rationale="Verified against Dealroom data.",
        supporting_source_ids=["s1"],
    )
    annotations = CriticAnnotations(
        id=_ANNOTATION_ID,
        report_id=_REPORT_ID,
        section_confidence=[section_confidence],
        claim_flags=[claim_flag],
        overall_confidence=0.92,
        model="openai/gpt-4o",
        generated_at=_NOW,
    )
    return VerifiedReport(job=job, report=report, annotations=annotations)


async def test_get_report_requires_auth(client: AsyncClient) -> None:
    response = await client.get(f"/api/research/{_JOB_ID}/report")
    assert response.status_code == 401


async def test_get_report_not_found(authed_client_stub_db: AsyncClient) -> None:
    with patch(
        "app.api.routes.JobRepository.get_report",
        new=AsyncMock(side_effect=JobNotFoundError("not found")),
    ):
        response = await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/report")
    assert response.status_code == 404


async def test_get_report_not_ready(authed_client_stub_db: AsyncClient) -> None:
    with patch(
        "app.api.routes.JobRepository.get_report",
        new=AsyncMock(side_effect=ReportNotFoundError("not ready")),
    ):
        response = await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/report")
    assert response.status_code == 404
    assert "not yet available" in response.json()["detail"]


async def test_get_report_returns_verified_report(authed_client_stub_db: AsyncClient) -> None:
    verified = _make_verified_report()
    with patch(
        "app.api.routes.JobRepository.get_report",
        new=AsyncMock(return_value=verified),
    ):
        response = await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/report")
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["title"] == verified.report.title
    assert body["annotations"]["overall_confidence"] == pytest.approx(0.92)


async def test_export_markdown_returns_file(authed_client_stub_db: AsyncClient) -> None:
    verified = _make_verified_report()
    with patch(
        "app.api.routes.JobRepository.get_report",
        new=AsyncMock(return_value=verified),
    ):
        response = await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/export/markdown")
    assert response.status_code == 200
    assert "Content-Disposition" in response.headers
    # The title appears as the H1 heading in the exported file.
    assert verified.report.title in response.text


async def test_export_pdf_returns_pdf(authed_client_stub_db: AsyncClient) -> None:
    verified = _make_verified_report()
    fake_pdf = b"%PDF-1.4 fake"
    with (
        patch("app.api.routes.JobRepository.get_report", new=AsyncMock(return_value=verified)),
        patch("app.api.routes.render_pdf", new=AsyncMock(return_value=fake_pdf)),
    ):
        response = await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/export/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "Content-Disposition" in response.headers
    assert response.content == fake_pdf


async def test_export_pdf_passes_user_id_to_repo(authed_client_stub_db: AsyncClient) -> None:
    mock_repo = AsyncMock(return_value=_make_verified_report())
    with (
        patch("app.api.routes.JobRepository.get_report", new=mock_repo),
        patch("app.api.routes.render_pdf", new=AsyncMock(return_value=b"%PDF")),
    ):
        await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/export/pdf")
    _, kwargs = mock_repo.await_args
    assert "user_id" in kwargs and isinstance(kwargs["user_id"], UUID)


async def test_export_markdown_strips_claim_spans(authed_client_stub_db: AsyncClient) -> None:
    verified = _make_verified_report()
    with patch(
        "app.api.routes.JobRepository.get_report",
        new=AsyncMock(return_value=verified),
    ):
        response = await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/export/markdown")
    assert response.status_code == 200
    assert "<span" not in response.text


async def test_get_report_passes_user_id_to_repo(authed_client_stub_db: AsyncClient) -> None:
    """The route must scope the repo lookup to the current user so other tenants' jobs surface as 404."""
    mock = AsyncMock(return_value=_make_verified_report())
    with patch("app.api.routes.JobRepository.get_report", new=mock):
        await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/report")
    assert mock.await_count == 1
    _, kwargs = mock.await_args
    assert "user_id" in kwargs and isinstance(kwargs["user_id"], UUID)


async def test_export_markdown_passes_user_id_to_repo(authed_client_stub_db: AsyncClient) -> None:
    mock = AsyncMock(return_value=_make_verified_report())
    with patch("app.api.routes.JobRepository.get_report", new=mock):
        await authed_client_stub_db.get(f"/api/research/{_JOB_ID}/export/markdown")
    assert mock.await_count == 1
    _, kwargs = mock.await_args
    assert "user_id" in kwargs and isinstance(kwargs["user_id"], UUID)
