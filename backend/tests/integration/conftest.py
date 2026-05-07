"""Integration-test fixtures that require a live Postgres instance."""

from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

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
