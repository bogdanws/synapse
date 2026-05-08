"""Redis pubsub bridge for ProgressEvent streaming.

The worker publishes events on `job:{job_id}:events`; the WebSocket bridge
subscribes to the same channel and forwards them to clients. Keeping the
helpers in a single module means the discriminated-union (de)serialisation
lives in one place — both sides go through the same `TypeAdapter` so a typo
in the producer surfaces as a validation error in the consumer test, not as
silent JSON drift in production.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import redis.asyncio as redis
from pydantic import TypeAdapter

from app.config import get_settings
from app.models.events import ProgressEvent

_settings = get_settings()
_event_adapter: TypeAdapter[ProgressEvent] = TypeAdapter(ProgressEvent)

# Lazily constructed module-level client. Eager construction at import time
# would tie test imports to a reachable Redis even when the test never publishes.
_redis_client: redis.Redis | None = None


def channel_for(job_id: UUID) -> str:
    return f"job:{job_id}:events"


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(_settings.redis_url, decode_responses=True)
    return _redis_client


async def close() -> None:
    """Close the module-level Redis client. Wired to FastAPI lifespan shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def publish(event: ProgressEvent) -> None:
    """Publish a progress event to its job's pubsub channel."""
    payload = _event_adapter.dump_json(event).decode()
    await _client().publish(channel_for(event.job_id), payload)


@asynccontextmanager
async def subscribe(job_id: UUID) -> AsyncIterator[AsyncIterator[ProgressEvent]]:
    """Subscribe to a job's event channel for the lifetime of the context.

    Usage:
        async with subscribe(job_id) as stream:
            async for event in stream:
                ...

    The context manager owns the underlying pubsub; callers must not keep a
    reference to the inner iterator past `__aexit__`.
    """
    pubsub = _client().pubsub()
    channel = channel_for(job_id)
    await pubsub.subscribe(channel)

    async def _iter() -> AsyncIterator[ProgressEvent]:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            yield _event_adapter.validate_json(message["data"])

    try:
        yield _iter()
    finally:
        await pubsub.unsubscribe(channel)
        # redis-py's PubSub.aclose is dynamically attached and missing type annotations; suppress the strict-mode complaint.
        await pubsub.aclose()  # type: ignore[no-untyped-call]
