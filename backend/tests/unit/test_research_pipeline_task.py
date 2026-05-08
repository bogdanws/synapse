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
from app.models.events import JobCompleted
from app.services import events as events_service
from app.tasks import broker
from app.tasks.research import run_research_pipeline


@pytest.fixture(autouse=True)
def _stub_publish(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Capture published events instead of hitting Redis.

    The stub task publishes a JobCompleted; without this fixture the test would either fail (no Redis) or hang (waiting for a connection).
    """
    captured: list[object] = []

    async def _record(event: object) -> None:
        captured.append(event)

    monkeypatch.setattr(events_service, "publish", _record)
    # The task imported `publish` by name, so patch the bound reference too.
    import app.tasks.research as research_module

    monkeypatch.setattr(research_module, "publish", _record)
    return captured


def test_test_environment_uses_in_memory_broker() -> None:
    # Guards against an accidental config change that would cause unit tests to try to talk to a real Redis.
    assert isinstance(broker, InMemoryBroker)


async def test_run_research_pipeline_publishes_job_completed(
    _stub_publish: list[object],
) -> None:
    job_id = uuid4()
    result = await run_research_pipeline.kiq(job_id)
    awaited = await result.wait_result(timeout=2)
    assert awaited.is_err is False
    assert len(_stub_publish) == 1
    event = _stub_publish[0]
    assert isinstance(event, JobCompleted)
    assert event.job_id == job_id


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
