"""Integration tests: DB migrations + seed (story 2.1).

Requirements:
  - A running Postgres instance accessible via DATABASE_URL env var.
  - Run with: uv run pytest tests/integration/test_seed.py -v -m integration

What is tested:
  1. Alembic migrations run to head without error.
  2. After seed, members table has the expected count (6: P1–P5, P7).
     Note: P6 is the "not-found" persona and is intentionally absent.
  3. After a second seed run, row counts are unchanged (idempotency).
  4. coverage_snapshots count ≤ members count (no orphan coverage rows).
  5. alembic_version table exists and head revision is "0001".
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_MEMBER_COUNT = 6  # P1, P2, P3, P4, P5, P7 — P6 is "not-found", not seeded


def _normalise_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return "postgresql+psycopg" + url[len("postgresql"):]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg" + url[len("postgresql+psycopg2"):]
    return url


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set — skipping DB integration tests")
    return _normalise_url(url)


@pytest.fixture(scope="module")
def repo_root() -> str:
    """Return the absolute path to the repository root."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module", autouse=True)
def run_migrations(db_url: str, repo_root: str) -> None:
    """Run alembic upgrade head once before all tests in this module."""
    env = {**os.environ, "DATABASE_URL": db_url}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            os.path.join(repo_root, "mcp_tools", "db", "migrations", "alembic.ini"),
            "upgrade",
            "head",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo_root,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Alembic migration failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


@pytest.fixture(scope="module", autouse=True)
def run_seed(run_migrations, db_url: str, repo_root: str) -> None:
    """Run seed script once before all tests in this module."""
    env = {**os.environ, "DATABASE_URL": db_url}
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "scripts", "seed.py")],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo_root,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Seed script failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_alembic_version_at_head(db_url: str) -> None:
    """alembic_version table must exist and contain the head revision."""
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        row = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        version = row.scalar()
    await engine.dispose()
    assert version == "0001", f"Expected head revision '0001', got {version!r}"


@pytest.mark.integration
async def test_members_count_after_seed(db_url: str) -> None:
    """Seed must produce exactly EXPECTED_MEMBER_COUNT member rows."""
    from mcp_tools.db.models import Member  # noqa: PLC0415

    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        count = await session.scalar(select(func.count()).select_from(Member))
    await engine.dispose()
    assert count == EXPECTED_MEMBER_COUNT, (
        f"Expected {EXPECTED_MEMBER_COUNT} members after seed, got {count}"
    )


@pytest.mark.integration
async def test_coverage_snapshots_count_after_seed(db_url: str) -> None:
    """coverage_snapshots count must be ≤ EXPECTED_MEMBER_COUNT after seed."""
    from mcp_tools.db.models import CoverageSnapshot  # noqa: PLC0415

    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        count = await session.scalar(select(func.count()).select_from(CoverageSnapshot))
    await engine.dispose()
    assert count <= EXPECTED_MEMBER_COUNT, (
        f"coverage_snapshots count ({count}) exceeds members count ({EXPECTED_MEMBER_COUNT})"
    )
    assert count > 0, "Expected at least one coverage_snapshot row after seed"


@pytest.mark.integration
async def test_seed_idempotent(db_url: str, repo_root: str) -> None:
    """Running seed a second time must not change row counts."""
    from mcp_tools.db.models import CoverageSnapshot, Member  # noqa: PLC0415

    engine = create_async_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Capture counts before second seed run
    async with factory() as session:
        members_before = await session.scalar(select(func.count()).select_from(Member))
        cov_before = await session.scalar(
            select(func.count()).select_from(CoverageSnapshot)
        )

    # Second seed run
    env = {**os.environ, "DATABASE_URL": db_url}
    result = subprocess.run(
        [sys.executable, os.path.join(repo_root, "scripts", "seed.py")],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo_root,
    )
    assert result.returncode == 0, (
        f"Second seed run failed:\n{result.stdout}\n{result.stderr}"
    )

    # Counts must be unchanged
    async with factory() as session:
        members_after = await session.scalar(select(func.count()).select_from(Member))
        cov_after = await session.scalar(
            select(func.count()).select_from(CoverageSnapshot)
        )

    await engine.dispose()

    assert members_after == members_before, (
        f"members count changed after second seed: {members_before} → {members_after}"
    )
    assert cov_after == cov_before, (
        f"coverage_snapshots count changed after second seed: {cov_before} → {cov_after}"
    )


@pytest.mark.integration
async def test_all_tables_exist(db_url: str) -> None:
    """All six application tables must exist after migration."""
    expected_tables = {
        "members",
        "coverage_snapshots",
        "verifications",
        "cases",
        "callbacks",
        "audit_log",
    }
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        actual_tables = await conn.run_sync(
            lambda sync_conn: set(inspect(sync_conn).get_table_names())
        )
    await engine.dispose()
    missing = expected_tables - actual_tables
    assert not missing, f"Tables missing after migration: {missing}"
