"""Unit tests for the Redis pubsub helper.

These tests fake the Redis client with `unittest.mock`; they intentionally do
not require a live Redis. End-to-end pubsub round-trips belong in the
integration suite once it gets a Redis service.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.events import JobCompleted, SubQuestionsGenerated
from app.services import events as events_service


@pytest.fixture(autouse=True)
def _reset_module_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(events_service, "_redis_client", None, raising=False)


def test_channel_for_includes_job_id() -> None:
    job_id = uuid4()
    assert events_service.channel_for(job_id) == f"job:{job_id}:events"


async def test_publish_serialises_event_to_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.publish = AsyncMock()
    monkeypatch.setattr(events_service, "_client", lambda: fake)

    job_id = uuid4()
    event = JobCompleted(
        job_id=job_id,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        overall_confidence=0.42,
    )
    await events_service.publish(event)

    fake.publish.assert_awaited_once()
    channel, payload = fake.publish.await_args.args
    assert channel == f"job:{job_id}:events"
    decoded = json.loads(payload)
    assert decoded["type"] == "job_completed"
    assert decoded["job_id"] == str(job_id)
    assert decoded["overall_confidence"] == 0.42


async def test_subscribe_yields_decoded_events(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = uuid4()

    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()

    raw_message = {
        "type": "message",
        "data": SubQuestionsGenerated(
            job_id=job_id,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            sub_questions=["a", "b"],
        ).model_dump_json(),
    }

    async def _listen() -> object:
        # The subscribe-confirmation messages emitted by Redis use type=="subscribe"; the helper must filter them out.
        yield {"type": "subscribe", "data": 1}
        yield raw_message

    pubsub.listen = _listen

    client = MagicMock()
    client.pubsub = MagicMock(return_value=pubsub)
    monkeypatch.setattr(events_service, "_client", lambda: client)

    received = []
    async with events_service.subscribe(job_id) as stream:
        async for event in stream:
            received.append(event)
            break

    assert len(received) == 1
    assert isinstance(received[0], SubQuestionsGenerated)
    assert received[0].sub_questions == ["a", "b"]
    pubsub.subscribe.assert_awaited_once_with(f"job:{job_id}:events")
    pubsub.unsubscribe.assert_awaited_once_with(f"job:{job_id}:events")
    pubsub.aclose.assert_awaited_once()


async def test_close_resets_module_client(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = MagicMock()
    fake.aclose = AsyncMock()
    monkeypatch.setattr(events_service, "_redis_client", fake, raising=False)

    await events_service.close()

    fake.aclose.assert_awaited_once()
    assert events_service._redis_client is None
