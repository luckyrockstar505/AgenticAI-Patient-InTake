"""Database engine factory and async session utilities.

Exports:
  get_engine(url)   — create or return the cached AsyncEngine
  get_session(url)  — async context manager yielding an AsyncSession
  reset_engine()    — set the module-level cache to None (for tests)
  Base              — re-exported from models for convenience
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mcp_tools.db.models import Base
from mcp_tools.db.utils import normalise_db_url

__all__ = ["Base", "get_engine", "get_session", "reset_engine"]

# Module-level singleton — created once, reused for the lifetime of the process.
_engine: AsyncEngine | None = None


def get_engine(url: str | None = None) -> AsyncEngine:
    """Return the module-level cached AsyncEngine, creating it on first call.

    Parameters
    ----------
    url:
        SQLAlchemy database URL.  Falls back to the ``DATABASE_URL``
        environment variable when *url* is ``None``.
    """
    global _engine
    if _engine is None:
        db_url = url or os.environ.get("DATABASE_URL", "")
        if not db_url:
            raise ValueError(
                "A database URL must be supplied via the url parameter or DATABASE_URL env var."
            )
        _engine = create_async_engine(
            normalise_db_url(db_url), echo=False, pool_pre_ping=True
        )
    return _engine


def reset_engine() -> None:
    """Reset the module-level engine singleton to None.

    Intended for use in tests that need a fresh engine between test cases.
    """
    global _engine
    _engine = None


@asynccontextmanager
async def get_session(url: str | None = None) -> AsyncGenerator[AsyncSession]:
    """Async context manager that yields a committed-or-rolled-back AsyncSession.

    Example::

        async with get_session() as session:
            result = await session.execute(select(Member))
    """
    engine = get_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
