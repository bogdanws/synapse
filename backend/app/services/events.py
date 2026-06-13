"""Durable + real-time event streaming for the research pipeline.

Every `ProgressEvent` produced by the agents is appended to the `job_events`
table and then republished over Redis pub/sub on `job:{job_id}:events`. The
WebSocket bridge consumes both: it replays the persisted log to reconstruct
state for a client that connects mid-run (or refreshes the page), and then
attaches to live pub/sub for events emitted after the replay. The persisted
row's `id` is carried in the Redis envelope so the bridge can drop frames
that overlap between the replay and the live tail.

A single discriminated-union `TypeAdapter` is shared by the producer and the
consumer so a typo in the producer surfaces as a validation error in tests,
not as silent JSON drift in production.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict
from uuid import UUID

import redis.asyncio as redis
import structlog
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.session import async_session_factory as _default_session_factory
from app.models import orm
from app.models.events import ProgressEvent

_settings = get_settings()
_event_adapter: TypeAdapter[ProgressEvent] = TypeAdapter(ProgressEvent)
_log = structlog.get_logger(__name__)

SessionFactory = async_sessionmaker[AsyncSession]

# Lazily constructed module-level client. Eager construction at import time
# would tie test imports to a reachable Redis even when the test never publishes.
_redis_client: redis.Redis | None = None

# Module-level session factory; the default is the application's own
# `async_session_factory`. Tests override via `set_session_factory` so they
# can exercise the persistence path without a live Postgres.
_session_factory: SessionFactory = _default_session_factory


class _Envelope(TypedDict):
    """Wire envelope for Redis pub/sub frames.

    Wrapping the event in `{id, event}` lets the WebSocket bridge dedupe
    frames that overlap between the DB replay and the live tail without
    leaking a synthetic field into the public `ProgressEvent` schema.
    """

    id: int
    event: dict[str, object]


def channel_for(job_id: UUID) -> str:
    return f"job:{job_id}:events"


def _client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(_settings.redis_url, decode_responses=True)
    return _redis_client


def set_session_factory(factory: SessionFactory) -> None:
    """Test seam: swap the session factory used by `publish` / `cleanup_for_job` / `load_history`."""
    global _session_factory
    _session_factory = factory


async def close() -> None:
    """Close the module-level Redis client. Wired to FastAPI lifespan shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def publish(event: ProgressEvent) -> None:
    """Persist a progress event, then announce it on the job's pub/sub channel.

    The DB INSERT happens *before* the Redis PUBLISH so a successful publish
    is a durability guarantee — a client reconnecting after this returns will
    see the event in the replay. If the INSERT fails the Redis side is
    skipped: a half-published event that nobody can replay would silently
    desync the UI.
    """
    payload = _event_adapter.dump_python(event, mode="json")

    async with _session_factory() as session:
        row = orm.JobEvent(job_id=event.job_id, event=payload)
        session.add(row)
        await session.commit()
        event_id = row.id

    envelope: _Envelope = {"id": event_id, "event": payload}
    await _client().publish(channel_for(event.job_id), json.dumps(envelope))


async def cleanup_for_job(job_id: UUID) -> None:
    """Drop all persisted events for a job.

    Called by the orchestrator after the terminal event for `job_id` has been
    published. The user has opted into eager cleanup — completed jobs render
    from their final-artifact tables (`reports`, `critic_annotations`,
    `sources`), not from this log.
    """
    async with _session_factory() as session:
        await session.execute(delete(orm.JobEvent).where(orm.JobEvent.job_id == job_id))
        await session.commit()


async def load_history(job_id: UUID) -> list[tuple[int, ProgressEvent]]:
    """Return persisted events for a job in publish order, oldest first.

    Each tuple is `(id, event)`; the id is the row's `BIGSERIAL` primary key
    and is what the WebSocket bridge uses to dedupe replayed frames against
    the live pub/sub tail.
    """
    async with _session_factory() as session:
        result = await session.execute(
            select(orm.JobEvent.id, orm.JobEvent.event)
            .where(orm.JobEvent.job_id == job_id)
            .order_by(orm.JobEvent.id.asc())
        )
        rows = result.all()
    return [(row_id, _event_adapter.validate_python(payload)) for row_id, payload in rows]


@asynccontextmanager
async def subscribe(
    job_id: UUID,
) -> AsyncIterator[AsyncIterator[tuple[int, ProgressEvent]]]:
    """Subscribe to a job's event channel for the lifetime of the context.

    The iterator yields `(id, event)` pairs. The id is the persisted row's
    primary key (same one returned by `load_history`), which lets callers
    drop frames whose id is below a replay watermark.

    Usage:
        async with subscribe(job_id) as stream:
            async for event_id, event in stream:
                ...

    The context manager owns the underlying pubsub; callers must not keep a
    reference to the inner iterator past `__aexit__`.
    """
    pubsub = _client().pubsub()
    channel = channel_for(job_id)
    await pubsub.subscribe(channel)

    async def _iter() -> AsyncIterator[tuple[int, ProgressEvent]]:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                envelope = json.loads(message["data"])
                event_id = int(envelope["id"])
                event = _event_adapter.validate_python(envelope["event"])
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                # A malformed frame is a bug in the producer, not a transport
                # error. Log and skip rather than tear down the whole stream.
                _log.warning(
                    "events_subscribe_dropped_malformed_frame",
                    job_id=str(job_id),
                    error=str(exc),
                )
                continue
            yield event_id, event

    try:
        yield _iter()
    finally:
        await pubsub.unsubscribe(channel)
        # redis-py's PubSub.aclose is dynamically attached and missing type annotations; suppress the strict-mode complaint.
        await pubsub.aclose()  # type: ignore[no-untyped-call]
