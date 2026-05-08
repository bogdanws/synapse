"""Tests for the research-pipeline task wiring.

These tests run against the InMemoryBroker selected by `app.tasks.broker` when
`APP_ENV=test` (set in `conftest.py`). The goal is to verify that the HTTP
route enqueues the task and that the task itself completes without error;
they do not exercise the real LangGraph pipeline because that lives behind a
stub for now.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from taskiq import InMemoryBroker

from app.auth.dependencies import current_active_user
from app.main import app
from app.tasks import broker
from app.tasks.research import run_research_pipeline


def test_test_environment_uses_in_memory_broker() -> None:
    # Guards against an accidental config change that would cause unit tests to try to talk to a real Redis.
    assert isinstance(broker, InMemoryBroker)


async def test_run_research_pipeline_runs_to_completion() -> None:
    result = await run_research_pipeline.kiq(uuid4())
    awaited = await result.wait_result(timeout=2)
    assert awaited.is_err is False


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


async def test_post_research_enqueues_pipeline_task(
    authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[object, ...]] = []

    original_kiq = run_research_pipeline.kiq

    async def _spy_kiq(*args: object, **kwargs: object) -> object:
        seen.append(args)
        return await original_kiq(*args, **kwargs)

    monkeypatch.setattr(run_research_pipeline, "kiq", _spy_kiq)

    response = await authed_client.post("/api/research", json={"topic": "Quantum computing"})
    assert response.status_code == 202
    assert len(seen) == 1
    # First positional arg is the job_id passed to the task.
    assert str(seen[0][0]) == response.json()["id"]
