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
    """Function-scoped async HTTP client for Scout's Exa search calls."""
    async with httpx.AsyncClient() as client:
        yield client
