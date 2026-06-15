"""Eval-only pytest fixtures.

Kept separate from the root `tests/conftest.py` so these session-heavy fixtures
(recorder, http client) are only instantiated when running eval tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from tests.evals._harness import EvalConfig, load_eval_config
from tests.evals._reporting import EvalRecorder


@pytest.fixture(scope="session")
def eval_config() -> EvalConfig:
    """Session-scoped eval configuration read from environment variables."""
    return load_eval_config()


@pytest.fixture(scope="session")
def eval_recorder() -> Iterator[EvalRecorder]:
    """Session-scoped recorder that writes artifacts at teardown.

    Using a generator fixture ensures `.dump()` is called even when individual
    eval tests error — pytest finalizers run regardless of test outcome.
    """
    recorder = EvalRecorder()
    yield recorder
    recorder.dump()


@pytest.fixture
async def http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Managed async client used only to satisfy ScoutAgent's constructor.

    The scout eval exercises `decompose`, which makes no HTTP calls; this client
    is wired into an unauthenticated `ExaSearchClient` purely so the agent can be
    built without reading EXA_API_KEY. No requests are issued through it.
    """
    async with httpx.AsyncClient() as client:
        yield client
