"""Tests for POST /api/research (Sprint 1)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import current_active_user
from app.main import app


@pytest.fixture
async def authed_client() -> AsyncIterator[AsyncClient]:
    async def _fake_current_active_user() -> SimpleNamespace:
        return SimpleNamespace(id="test-user-id")

    app.dependency_overrides[current_active_user] = _fake_current_active_user
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(current_active_user, None)


async def test_start_research_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/research", json={"topic": "Quantum computing"})
    assert response.status_code == 401


async def test_start_research_returns_job(authed_client: AsyncClient) -> None:
    response = await authed_client.post("/api/research", json={"topic": "Quantum computing"})
    assert response.status_code == 202
    body = response.json()
    # job id is a valid UUID
    UUID(body["id"])
    assert body["topic"] == "Quantum computing"
    assert body["status"] == "pending"
    assert body["progress"] == 0.0


@pytest.mark.parametrize("bad_topic", ["", "a", "no"])
async def test_start_research_rejects_short_topic(
    authed_client: AsyncClient, bad_topic: str
) -> None:
    response = await authed_client.post("/api/research", json={"topic": bad_topic})
    assert response.status_code == 422
