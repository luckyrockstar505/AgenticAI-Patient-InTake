"""Database engine factory and async session utilities.

Exports:
  get_engine(url)  — create an AsyncEngine from a DATABASE_URL
  get_session(url) — async context manager yielding an AsyncSession
  Base             — re-exported from models for convenience
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

__all__ = ["Base", "get_engine", "get_session"]


def _normalise_url(url: str) -> str:
    """Ensure the URL uses the psycopg3 async driver prefix."""
    if url.startswith("postgresql://"):
        # plain URL → psycopg3
        return "postgresql+psycopg" + url[len("postgresql"):]
    if url.startswith("postgresql+psycopg2://"):
        # legacy psycopg2 → psycopg3
        return "postgresql+psycopg" + url[len("postgresql+psycopg2"):]
    # already has the correct prefix (postgresql+psycopg://)
    return url


def get_engine(url: str | None = None) -> AsyncEngine:
    """Create and return a new AsyncEngine.

    Parameters
    ----------
    url:
        SQLAlchemy database URL.  Falls back to the ``DATABASE_URL``
        environment variable when *url* is ``None``.
    """
    db_url = url or os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise ValueError(
            "A database URL must be supplied via the url parameter or DATABASE_URL env var."
        )
    return create_async_engine(_normalise_url(db_url), echo=False, pool_pre_ping=True)


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
        finally:
            await engine.dispose()
