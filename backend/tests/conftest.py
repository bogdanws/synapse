"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET", "test-secret-min-32-chars-for-pytest-runs")
# httpx ASGITransport runs over plain http://test, so the cookie's Secure flag
# would prevent it from being echoed back. Disable it for the test client only.
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("APP_ENV", "test")
# Agent unit tests instantiate `ChatOpenAI` (under `langchain-openai`); the
# underlying `openai` SDK refuses to construct a client without credentials,
# even when respx is intercepting every HTTP call. A dummy non-empty value is
# enough to satisfy the constructor without leaking real keys into tests.
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("EXA_API_KEY", "test-exa-key")

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
