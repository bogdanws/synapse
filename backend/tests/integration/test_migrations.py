"""Integration test: migrations apply cleanly and produce expected tables."""

from __future__ import annotations

import asyncio

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.config import get_settings

pytestmark = pytest.mark.integration


async def test_migration_roundtrip() -> None:
    """Drop the public schema, run alembic upgrade head, and assert all
    expected tables exist.

    We do not assert an empty autogenerate diff because the project does not
    include a synchronous Postgres driver (psycopg), and Alembic's compare
    metadata requires a sync connection.
    """
    settings = get_settings()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    # alembic env.py calls asyncio.run() internally; invoke upgrade from a
    # thread that has no running event loop so asyncio.run() can create one.
    config = Config("alembic.ini")
    await asyncio.to_thread(command.upgrade, config, "head")

    expected_tables = {
        "user",
        "research_jobs",
        "sources",
        "reports",
        "critic_annotations",
        "follow_ups",
        "alembic_version",
    }
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = {row[0] for row in result.fetchall()}

    assert expected_tables <= tables, f"Missing tables: {expected_tables - tables}"

    await engine.dispose()
