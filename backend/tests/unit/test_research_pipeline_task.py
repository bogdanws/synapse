"""Tests for the research-pipeline taskiq task wiring.

The task itself is a thin shim that delegates to `app.agents.orchestrator.run_pipeline`; the orchestrator's behaviour is covered by `tests/unit/test_orchestrator.py`. These tests verify the taskiq plumbing — that the test environment uses the in-memory broker, that the task hands the job id and the configured session factory to the orchestrator, and that the HTTP route enqueues the task on success.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from taskiq import InMemoryBroker

from app.auth.dependencies import current_active_user
from app.db.session import async_session_factory, get_db
from app.main import app
from app.models import orm
from app.tasks import research as research_module
from app.tasks.broker import broker
from app.tasks.research import run_research_pipeline

_VALID_MODELS = {
    "scout": "openai/gpt-4o-mini",
    "scribe": "openai/gpt-4o",
    "critic": "openai/gpt-4o",
}


def test_test_environment_uses_in_memory_broker() -> None:
    # Guards against an accidental config change that would cause unit tests
    # to try to talk to a real Redis.
    assert isinstance(broker, InMemoryBroker)


async def test_task_invokes_run_pipeline_with_job_id_and_session_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, Any]] = []

    async def fake_run_pipeline(*, job_id: UUID, session_factory: Any, **kwargs: Any) -> None:
        seen.append({"job_id": job_id, "session_factory": session_factory})

    monkeypatch.setattr(research_module, "run_pipeline", fake_run_pipeline)

    job_id = uuid4()
    result = await run_research_pipeline.kiq(job_id)
    awaited = await result.wait_result(timeout=2)
    assert awaited.is_err is False
    assert len(seen) == 1
    assert seen[0]["job_id"] == job_id
    # The shim hands the production session factory through unchanged so the
    # orchestrator opens its own per-write transactions.
    assert seen[0]["session_factory"] is async_session_factory


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: Any) -> None:
        if isinstance(obj, orm.ResearchJob):
            if obj.id is None:
                obj.id = uuid4()
            now = datetime.now(UTC)
            if obj.created_at is None:
                obj.created_at = now
            if obj.updated_at is None:
                obj.updated_at = now


@pytest.fixture
async def authed_client_with_db() -> AsyncIterator[tuple[AsyncClient, _FakeSession]]:
    fake_session = _FakeSession()
    user_id = uuid4()

    async def _fake_current_active_user() -> Any:
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
            yield ac, fake_session
    finally:
        app.dependency_overrides.pop(current_active_user, None)
        app.dependency_overrides.pop(get_db, None)


async def test_post_research_enqueues_pipeline_task_with_persisted_job_id(
    authed_client_with_db: tuple[AsyncClient, _FakeSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The task is enqueued with the id of the row that was just persisted."""
    client, _ = authed_client_with_db
    seen: list[tuple[Any, ...]] = []

    original_kiq = run_research_pipeline.kiq

    async def _spy_kiq(*args: object, **kwargs: object) -> object:
        seen.append(args)
        return await original_kiq(*args, **kwargs)

    # Stop the actual task body from running so we don't reach into an empty DB.
    async def _noop_pipeline(**kwargs: Any) -> None:
        return None

    monkeypatch.setattr(run_research_pipeline, "kiq", _spy_kiq)
    monkeypatch.setattr(research_module, "run_pipeline", _noop_pipeline)

    response = await client.post(
        "/api/research",
        json={"topic": "Quantum computing", "models": _VALID_MODELS},
    )
    assert response.status_code == 202
    assert len(seen) == 1
    assert str(seen[0][0]) == response.json()["id"]
