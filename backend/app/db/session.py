"""Async SQLAlchemy engine and session dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# pytest-asyncio (asyncio_mode=auto) creates a new event loop per test
# asyncpg connections are bound to the loop that created them, so a pooled connection surfaced in a later test raises "Future attached to a different loop"
# NullPool avoids this by never caching connections between requests.
_engine_kwargs = {"poolclass": NullPool} if settings.app_env == "test" else {"pool_pre_ping": True}
engine: AsyncEngine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield an async DB session for request-scoped dependencies."""
    async with async_session_factory() as session:
        yield session
