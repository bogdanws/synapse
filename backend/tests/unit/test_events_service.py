"""Unit tests for the Redis pub/sub + DB-persistence helper.

These tests fake the Redis client and the SQLAlchemy session with
`unittest.mock`; they intentionally do not require a live Redis or Postgres.
End-to-end round-trips belong in the integration suite once it gets both
services wired up.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import Delete, Select

from app.models import orm
from app.models.events import JobCompleted, SubQuestionsGenerated
from app.services import events as events_service


class _FakeSession:
    """In-memory stand-in for `AsyncSession` used by the events service.

    Records every `add`/`execute`/`commit` call so individual tests can
    assert on persistence side effects without a live database.
    """

    def __init__(self, history: list[orm.JobEvent] | None = None) -> None:
        # `history` lets a test pre-seed rows that `load_history` will return
        # in order.
        self._history: list[orm.JobEvent] = list(history or [])
        self.added: list[Any] = []
        self.executed: list[Any] = []
        self.commits = 0
        # Auto-assigned ids for `add()`-ed rows, mimicking BIGSERIAL.
        self._next_id = max((r.id for r in self._history), default=0) + 1

    def add(self, obj: Any) -> None:
        if isinstance(obj, orm.JobEvent) and obj.id is None:
            obj.id = self._next_id
            self._next_id += 1
        self.added.append(obj)

    async def execute(self, stmt: Any) -> Any:
        self.executed.append(stmt)
        if isinstance(stmt, Select):
            # Replay the seeded history as `(id, event)` tuples, matching
            # the real query in `load_history`.
            result = MagicMock()
            result.all = MagicMock(return_value=[(row.id, row.event) for row in self._history])
            return result
        if isinstance(stmt, Delete):
            self._history.clear()
        return MagicMock()

    async def commit(self) -> None:
        self.commits += 1

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _install_fake_session(monkeypatch: pytest.MonkeyPatch, session: _FakeSession) -> None:
    """Point the events module at a single-instance `_FakeSession`."""

    def _factory() -> _FakeSession:
        return session

    # `_session_factory` is invoked as `_session_factory()`; the callable just
    # needs to return something usable as an async context manager.
    monkeypatch.setattr(events_service, "_session_factory", _factory)


@pytest.fixture(autouse=True)
def _reset_module_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events_service, "_redis_client", None, raising=False)


def test_channel_for_includes_job_id() -> None:
    job_id = uuid4()
    assert events_service.channel_for(job_id) == f"job:{job_id}:events"


async def test_publish_persists_event_then_publishes_wrapped_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock()
    monkeypatch.setattr(events_service, "_client", lambda: fake_redis)

    session = _FakeSession()
    _install_fake_session(monkeypatch, session)

    job_id = uuid4()
    event = JobCompleted(
        job_id=job_id,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        overall_confidence=0.42,
    )
    await events_service.publish(event)

    # Persistence: one JobEvent row added and committed before the Redis call.
    assert session.commits == 1
    assert len(session.added) == 1
    row = session.added[0]
    assert isinstance(row, orm.JobEvent)
    assert row.job_id == job_id
    assert row.event["type"] == "job_completed"
    assert row.event["overall_confidence"] == 0.42

    # Redis: payload is the envelope `{id, event}`, not the raw event.
    fake_redis.publish.assert_awaited_once()
    channel, payload = fake_redis.publish.await_args.args
    assert channel == f"job:{job_id}:events"
    envelope = json.loads(payload)
    assert envelope["id"] == row.id
    assert envelope["event"]["type"] == "job_completed"
    assert envelope["event"]["job_id"] == str(job_id)
    assert envelope["event"]["overall_confidence"] == 0.42


async def test_publish_skips_redis_when_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the DB write blows up, the Redis publish must not happen.

    Otherwise a client reconnecting later would replay an empty history yet
    still receive the live frame from Redis — silently desynced UI.
    """
    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock()
    monkeypatch.setattr(events_service, "_client", lambda: fake_redis)

    class _BrokenSession(_FakeSession):
        async def commit(self) -> None:
            raise RuntimeError("database is on fire")

    session = _BrokenSession()
    _install_fake_session(monkeypatch, session)

    event = JobCompleted(
        job_id=uuid4(),
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        overall_confidence=0.0,
    )

    with pytest.raises(RuntimeError, match="database is on fire"):
        await events_service.publish(event)

    fake_redis.publish.assert_not_awaited()


async def test_load_history_returns_persisted_events_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    first = SubQuestionsGenerated(
        job_id=job_id,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        sub_questions=["q1"],
    )
    second = JobCompleted(
        job_id=job_id,
        timestamp=datetime(2026, 1, 2, tzinfo=UTC),
        overall_confidence=0.7,
    )
    # IDs are intentionally non-sequential to confirm the caller relies on
    # the DB-returned order, not on a `range(len(history))` assumption.
    seeded = [
        orm.JobEvent(id=11, job_id=job_id, event=first.model_dump(mode="json")),
        orm.JobEvent(id=42, job_id=job_id, event=second.model_dump(mode="json")),
    ]
    session = _FakeSession(history=seeded)
    _install_fake_session(monkeypatch, session)

    history = await events_service.load_history(job_id)

    assert [row_id for row_id, _ in history] == [11, 42]
    types = [type(ev).__name__ for _, ev in history]
    assert types == ["SubQuestionsGenerated", "JobCompleted"]


async def test_cleanup_for_job_deletes_persisted_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()
    seeded = [
        orm.JobEvent(
            id=1,
            job_id=job_id,
            event=JobCompleted(
                job_id=job_id,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                overall_confidence=0.5,
            ).model_dump(mode="json"),
        )
    ]
    session = _FakeSession(history=seeded)
    _install_fake_session(monkeypatch, session)

    await events_service.cleanup_for_job(job_id)

    # A DELETE statement was issued and the transaction committed.
    assert any(isinstance(stmt, Delete) for stmt in session.executed)
    assert session.commits == 1
    # The seeded history is empty afterwards.
    assert await events_service.load_history(job_id) == []


async def test_subscribe_yields_id_and_event_from_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = uuid4()

    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()

    envelope = {
        "id": 99,
        "event": SubQuestionsGenerated(
            job_id=job_id,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            sub_questions=["a", "b"],
        ).model_dump(mode="json"),
    }
    raw_message = {"type": "message", "data": json.dumps(envelope)}

    async def _listen() -> object:
        # The subscribe-confirmation messages emitted by Redis use type=="subscribe"; the helper must filter them out.
        yield {"type": "subscribe", "data": 1}
        yield raw_message

    pubsub.listen = _listen

    client = MagicMock()
    client.pubsub = MagicMock(return_value=pubsub)
    monkeypatch.setattr(events_service, "_client", lambda: client)

    received: list[tuple[int, Any]] = []
    async with events_service.subscribe(job_id) as stream:
        async for event_id, event in stream:
            received.append((event_id, event))
            break

    assert len(received) == 1
    event_id, event = received[0]
    assert event_id == 99
    assert isinstance(event, SubQuestionsGenerated)
    assert event.sub_questions == ["a", "b"]
    pubsub.subscribe.assert_awaited_once_with(f"job:{job_id}:events")
    pubsub.unsubscribe.assert_awaited_once_with(f"job:{job_id}:events")
    pubsub.aclose.assert_awaited_once()


async def test_subscribe_skips_malformed_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Garbage on the wire must not poison the subscriber.

    A producer bug shouldn't deadlock every connected client; the helper logs
    and continues so a single bad frame can't take down the stream.
    """
    job_id = uuid4()

    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()

    good_envelope = {
        "id": 7,
        "event": JobCompleted(
            job_id=job_id,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            overall_confidence=0.1,
        ).model_dump(mode="json"),
    }

    async def _listen() -> object:
        # Missing `event` key — malformed envelope.
        yield {"type": "message", "data": json.dumps({"id": 6})}
        # Valid frame that should still get through.
        yield {"type": "message", "data": json.dumps(good_envelope)}

    pubsub.listen = _listen

    client = MagicMock()
    client.pubsub = MagicMock(return_value=pubsub)
    monkeypatch.setattr(events_service, "_client", lambda: client)

    received: list[tuple[int, Any]] = []
    async with events_service.subscribe(job_id) as stream:
        async for event_id, event in stream:
            received.append((event_id, event))
            break

    assert len(received) == 1
    assert received[0][0] == 7
    assert isinstance(received[0][1], JobCompleted)


async def test_close_resets_module_client(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.aclose = AsyncMock()
    monkeypatch.setattr(events_service, "_redis_client", fake, raising=False)

    await events_service.close()

    fake.aclose.assert_awaited_once()
    assert events_service._redis_client is None
