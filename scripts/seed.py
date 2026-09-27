"""Seed script — loads members and coverage snapshots into Postgres.

Reads:
  data/seed/members.json   — synthetic member personas
  data/seed/coverage.json  — synthetic coverage payloads (keyed by member_id)

Usage:
  uv run python scripts/seed.py

Idempotent: running twice produces the same row counts.
  - members: ON CONFLICT DO NOTHING on the unique member_id index
  - coverage_snapshots: check before insert (no unique constraint on table)

P6 ("not-found ID") is intentionally absent from members.json — it is the
scenario where an agent looks up a member_id that does not exist in the DB.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths relative to the repo root (not the script's own directory)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
MEMBERS_JSON = REPO_ROOT / "data" / "seed" / "members.json"
COVERAGE_JSON = REPO_ROOT / "data" / "seed" / "coverage.json"


def _build_engine():
    """Build an async SQLAlchemy engine from DATABASE_URL."""
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from mcp_tools.db.utils import normalise_db_url  # noqa: PLC0415

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    return create_async_engine(normalise_db_url(db_url), echo=False, pool_pre_ping=True)


async def _run_seed() -> None:
    from sqlalchemy import func, select  # noqa: PLC0415
    from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

    from mcp_tools.db.models import CoverageSnapshot, Member  # noqa: PLC0415

    members_data: list[dict] = json.loads(MEMBERS_JSON.read_text(encoding="utf-8"))
    coverage_list: list[dict] = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    coverage_by_member_id: dict[str, dict] = {
        c["member_id"]: c for c in coverage_list
    }

    engine = _build_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # ------------------------------------------------------------------
        # Members — idempotent via ON CONFLICT DO NOTHING on member_id
        # ------------------------------------------------------------------
        for m in members_data:
            dob: date | None = None
            if m.get("dob"):
                dob = date.fromisoformat(m["dob"])

            stmt = (
                pg_insert(Member)
                .values(
                    id=uuid.uuid4(),
                    member_id=m["member_id"],
                    first_name=m["first_name"],
                    last_name=m["last_name"],
                    dob=dob,
                    zip=m.get("zip"),
                    employer_group=m.get("employer_group"),
                    subscriber_name=m.get("subscriber_name"),
                    relationship=m.get("relationship"),
                    payer_id=m.get("payer_id"),
                )
                .on_conflict_do_nothing(index_elements=["member_id"])
            )
            await session.execute(stmt)

        # ------------------------------------------------------------------
        # Coverage snapshots — idempotent via pre-insert existence check.
        # A member may have no coverage entry (e.g. the "not-found" scenario);
        # that is silently skipped.
        # ------------------------------------------------------------------
        for m in members_data:
            cov_data = coverage_by_member_id.get(m["member_id"])
            if cov_data is None:
                # Member exists in DB but has no coverage in the seed file — OK.
                continue

            existing = await session.scalar(
                select(func.count())
                .select_from(CoverageSnapshot)
                .where(CoverageSnapshot.member_id == m["member_id"])
                .where(CoverageSnapshot.source == "seed")
            )
            if existing == 0:
                session.add(
                    CoverageSnapshot(
                        id=uuid.uuid4(),
                        session_id=None,
                        member_id=m["member_id"],
                        payload=cov_data,
                        source="seed",
                        status="unverified",
                    )
                )

        await session.commit()

    # ------------------------------------------------------------------
    # Report final counts
    # ------------------------------------------------------------------
    async with session_factory() as session:
        member_count = await session.scalar(
            select(func.count()).select_from(Member)
        )
        cov_count = await session.scalar(
            select(func.count()).select_from(CoverageSnapshot)
        )

    await engine.dispose()
    print(f"Seed complete — {member_count} members, {cov_count} coverage_snapshots")


def main() -> None:
    asyncio.run(_run_seed())


if __name__ == "__main__":
    main()
