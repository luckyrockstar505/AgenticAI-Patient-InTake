"""Contract tests for fetch_coverage, get_policy_view, and end_session.

These tests run the FastMCP server in-process using ``Client(mcp)`` — no HTTP,
no network.  They require a live Postgres database and are skipped when
``DATABASE_URL`` is not set.

Run:
    make up  # start postgres
    uv run pytest tests/contracts/test_coverage_contract.py -v
"""
from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from fastmcp import Client, FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_tools.db.models import AuditLog, Base, CoverageSnapshot, Verification
from mcp_tools.db.utils import normalise_db_url
from mcp_tools.payer_mock import MockPayerClient
from mcp_tools.tools.coverage import register as _reg_coverage

DATABASE_URL = os.environ.get("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set — skipping contract tests that require postgres",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture(scope="module")
async def engine():
    e = create_async_engine(normalise_db_url(DATABASE_URL), echo=False, pool_pre_ping=True)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest_asyncio.fixture()
async def session_factory(engine):
    """Return a session factory scoped to the test engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture()
async def mcp_instance(session_factory):
    """A fresh FastMCP instance with coverage tools wired to the test DB."""

    @asynccontextmanager
    async def _get_db(*_args, **_kwargs):
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    test_mcp = FastMCP("test-claims-tools")
    _reg_coverage(test_mcp, MockPayerClient(), _get_db)
    return test_mcp


@pytest_asyncio.fixture()
async def db(session_factory):
    """Yield a transactional session for setup/assertion helpers."""
    async with session_factory() as s:
        yield s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(result) -> dict:
    """Extract the JSON dict from a FastMCP call_tool result."""
    assert len(result) > 0, "tool returned empty result list"
    return json.loads(result[0].text)


async def _call(mcp_instance: FastMCP, tool: str, args: dict) -> dict:
    async with Client(mcp_instance) as c:
        result = await c.call_tool(tool, args)
    return _parse(result)


# ---------------------------------------------------------------------------
# Test 1 – fetch_coverage: known member
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fetch_coverage_known_member(mcp_instance, db):
    session_id = f"s-{uuid.uuid4()}"
    resp = await _call(
        mcp_instance,
        "fetch_coverage",
        {"session_id": session_id, "member_id": "ABC100000001"},
    )
    assert resp["ok"] is True
    assert resp["data"]["found"] is True
    snap_id = resp["data"]["snapshot_id"]
    assert snap_id is not None

    # Verify DB row exists with status='unverified'
    result = await db.execute(
        select(CoverageSnapshot).where(CoverageSnapshot.id == uuid.UUID(snap_id))
    )
    snap = result.scalar_one_or_none()
    assert snap is not None
    assert snap.status == "unverified"
    # Payload must NOT be in the response envelope
    assert "payload" not in resp["data"]


# ---------------------------------------------------------------------------
# Test 2 – fetch_coverage: unknown member (found: false, no snapshot row)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fetch_coverage_unknown_member(mcp_instance, db):
    session_id = f"s-{uuid.uuid4()}"
    resp = await _call(
        mcp_instance,
        "fetch_coverage",
        {"session_id": session_id, "member_id": "ZZZ999999999"},
    )
    assert resp["ok"] is True
    assert resp["data"]["found"] is False
    assert resp["data"]["snapshot_id"] is None

    # No snapshot row should exist for this session
    result = await db.execute(
        select(CoverageSnapshot).where(CoverageSnapshot.session_id == session_id)
    )
    snaps = result.scalars().all()
    assert len(snaps) == 0

    # Audit row must exist with found=False
    audit_result = await db.execute(
        select(AuditLog).where(
            AuditLog.session_id == session_id,
            AuditLog.event == "coverage_fetched",
        )
    )
    audit = audit_result.scalar_one_or_none()
    assert audit is not None
    assert audit.detail is not None
    assert audit.detail.get("found") is False


# ---------------------------------------------------------------------------
# Test 3 – get_policy_view: verification not PASSED (PENDING status)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_policy_view_not_passed(mcp_instance, db):
    session_id = f"s-{uuid.uuid4()}"
    v = Verification(id=uuid.uuid4(), session_id=session_id, status="PENDING")
    db.add(v)
    await db.commit()

    resp = await _call(
        mcp_instance,
        "get_policy_view",
        {"session_id": session_id, "verification_id": str(v.id)},
    )
    assert resp["ok"] is False
    assert resp["error"]["code"] == "NOT_VERIFIED"


# ---------------------------------------------------------------------------
# Test 4 – get_policy_view: unknown verification_id (no enumeration)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_policy_view_unknown_verification(mcp_instance):
    session_id = f"s-{uuid.uuid4()}"
    resp = await _call(
        mcp_instance,
        "get_policy_view",
        {"session_id": session_id, "verification_id": str(uuid.uuid4())},
    )
    assert resp["ok"] is False
    assert resp["error"]["code"] == "NOT_VERIFIED"


# ---------------------------------------------------------------------------
# Test 5 – get_policy_view: PASSED verification returns policy (no member_id)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_policy_view_passed(mcp_instance, db):
    session_id = f"s-{uuid.uuid4()}"

    # Insert PASSED verification
    v = Verification(id=uuid.uuid4(), session_id=session_id, status="PASSED")
    db.add(v)

    # Insert a coverage snapshot with a realistic payload
    payload = {
        "member_id": "ABC100000001",
        "plan_name": "Silver PPO 2500",
        "plan_type": "PPO",
        "group_name": "Acme Corp",
        "effective_date": "2026-01-01",
        "termination_date": "2026-12-31",
        "status": "active",
        "network": "in-network required for full benefits",
        "deductible": {"individual": 2500, "met": 800, "remaining": 1700},
        "oop_max": {"individual": 7000, "met": 1200, "remaining": 5800},
        "copays": {"pcp": 25, "specialist": 50, "urgent_care": 75, "er": 300},
        "coinsurance_pct": 20,
        "coverage_period": {"start": "2026-01-01", "end": "2026-12-31"},
    }
    snap = CoverageSnapshot(
        id=uuid.uuid4(),
        session_id=session_id,
        member_id="ABC100000001",
        payload=payload,
        status="unverified",
    )
    db.add(snap)
    await db.commit()

    resp = await _call(
        mcp_instance,
        "get_policy_view",
        {"session_id": session_id, "verification_id": str(v.id)},
    )
    assert resp["ok"] is True
    data = resp["data"]
    assert "plan_name" in data
    assert "deductible" in data
    # PHI: member_id must NOT be in the response
    assert "member_id" not in data

    # Audit row must exist with event="policy_viewed"
    audit_result = await db.execute(
        select(AuditLog).where(
            AuditLog.session_id == session_id,
            AuditLog.event == "policy_viewed",
        )
    )
    audit = audit_result.scalar_one_or_none()
    assert audit is not None


# ---------------------------------------------------------------------------
# Test 6 – end_session: valid reason closes session and discards snapshots
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_end_session_discards_snapshots(mcp_instance, db):
    session_id = f"s-{uuid.uuid4()}"
    snap = CoverageSnapshot(
        id=uuid.uuid4(),
        session_id=session_id,
        member_id="ABC100000001",
        payload={},
        status="unverified",
    )
    db.add(snap)
    await db.commit()

    resp = await _call(
        mcp_instance,
        "end_session",
        {"session_id": session_id, "reason": "cancelled"},
    )
    assert resp["ok"] is True
    assert resp["data"]["closed"] is True

    # Snapshot should now be discarded
    await db.refresh(snap)
    assert snap.status == "discarded"

    # Audit row must exist
    result = await db.execute(
        select(AuditLog).where(
            AuditLog.session_id == session_id,
            AuditLog.event == "session_ended",
        )
    )
    audit = result.scalar_one_or_none()
    assert audit is not None


# ---------------------------------------------------------------------------
# Test 7 – end_session: idempotent (second call returns closed: true)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_end_session_idempotent(mcp_instance):
    session_id = f"s-{uuid.uuid4()}"
    args = {"session_id": session_id, "reason": "completed"}

    resp1 = await _call(mcp_instance, "end_session", args)
    resp2 = await _call(mcp_instance, "end_session", args)
    assert resp1["ok"] is True
    assert resp2["ok"] is True
    assert resp2["data"]["closed"] is True


# ---------------------------------------------------------------------------
# Test 8 – end_session: invalid reason returns VALIDATION error
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_end_session_invalid_reason(mcp_instance):
    session_id = f"s-{uuid.uuid4()}"
    resp = await _call(
        mcp_instance,
        "end_session",
        {"session_id": session_id, "reason": "banana"},
    )
    assert resp["ok"] is False
    assert resp["error"]["code"] == "VALIDATION"
