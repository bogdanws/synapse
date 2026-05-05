"""Tests for POST /api/research (Sprint 1)."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient


async def test_start_research_returns_job(client: AsyncClient) -> None:
    response = await client.post("/api/research", json={"topic": "Quantum computing"})
    assert response.status_code == 202
    body = response.json()
    # job id is a valid UUID
    UUID(body["id"])
    assert body["topic"] == "Quantum computing"
    assert body["status"] == "pending"
    assert body["progress"] == 0.0


@pytest.mark.parametrize("bad_topic", ["", "a", "no"])
async def test_start_research_rejects_short_topic(client: AsyncClient, bad_topic: str) -> None:
    response = await client.post("/api/research", json={"topic": bad_topic})
    assert response.status_code == 422
