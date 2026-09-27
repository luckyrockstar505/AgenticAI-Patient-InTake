"""Alembic environment configuration.

Reads the database URL from the DATABASE_URL environment variable.
Alembic runs synchronously; the psycopg3 driver supports both sync and async
so the same postgresql+psycopg:// URL works for both Alembic and the
async application engine.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import Base so that Alembic can reference the metadata for autogenerate.
# (Autogenerate is disabled per spec — write migrations by hand.)
from mcp_tools.db.models import Base
from mcp_tools.db.utils import normalise_db_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Return the database URL, preferring the DATABASE_URL environment variable."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        url = config.get_main_option("sqlalchemy.url", "") or ""
    if not url:
        raise RuntimeError(
            "DATABASE_URL env var must be set before running Alembic migrations."
        )
    # Alembic uses the sync SQLAlchemy engine.
    # psycopg3 (postgresql+psycopg://) supports sync mode natively — no change needed.
    return normalise_db_url(url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL without a live connection)."""
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to DB and apply changes)."""
    cfg = dict(config.get_section(config.config_ini_section) or {})
    cfg["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
