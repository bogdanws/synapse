"""Integration-test fixtures that require a live Postgres instance."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("JWT_SECRET", "test-secret-min-32-chars-for-pytest-runs")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("APP_ENV", "test")

import app.auth.models  # noqa: F401 - register User table with Base.metadata
import app.models.orm  # noqa: F401 - register research domain tables
from app.config import get_settings
from app.db.base import Base


@pytest.fixture(autouse=True, scope="session")
def create_tables() -> Generator[None]:
    """Create all tables once for the test session against the real DB.

    NullPool is used so the temporary engine does not keep connections open
    after setup; the app's own engine pool takes over during the tests.
    """

    async def _setup() -> None:
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, checkfirst=True))
        await engine.dispose()

    asyncio.run(_setup())
    yield


@pytest.fixture
async def async_session() -> AsyncIterator[AsyncSession]:
    """Yield an async SQLAlchemy session bound to a per-test engine.

    A fresh engine with NullPool is built per test so that asyncpg connections
    are not cached across pytest-asyncio's per-test event loops (which would
    raise "got Future attached to a different loop").
    """
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()
