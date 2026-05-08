"""taskiq broker singleton.

Picks an in-memory broker for tests (so `kiq()` does not require a live Redis)
and a Redis-backed list queue everywhere else. The broker is also wired to the
FastAPI app via `taskiq_fastapi.init` so tasks can use `Depends(...)` to access
request-scoped resources (DB sessions, settings) the same way HTTP routes do.
"""

from __future__ import annotations

from taskiq import AsyncBroker, InMemoryBroker
from taskiq_fastapi import init as _taskiq_fastapi_init
from taskiq_redis import ListQueueBroker

from app.config import get_settings

_settings = get_settings()


def _build_broker() -> AsyncBroker:
    if _settings.app_env == "test":
        # InMemoryBroker runs tasks in the same event loop as the caller, so unit tests can exercise enqueue paths without a Redis service.
        return InMemoryBroker()
    return ListQueueBroker(url=_settings.redis_url)


broker: AsyncBroker = _build_broker()

# Wires FastAPI's dependency-injection container into the broker so `Depends(get_db)` and similar work inside tasks. The app is referenced by import path to avoid a circular import here.
_taskiq_fastapi_init(broker, "app.main:app")
