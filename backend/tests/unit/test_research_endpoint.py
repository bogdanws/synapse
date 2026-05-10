"""Tests for POST /api/research."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import current_active_user
from app.db.session import get_db
from app.main import app
from app.models import orm

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
