"""Contract tests for start_verification and check_answer.

These tests run the FastMCP server in-process using ``Client(mcp)`` — no HTTP,
no network.  They require a live Postgres database and are skipped when
``DATABASE_URL`` is not set.

Run:
    make up  # start postgres
    uv run pytest tests/contracts/test_verification_contract.py -v
"""
from __future__ import annotations

import datetime
import json
import os
import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from fastmcp import Client, FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from mcp_tools.db.models import AuditLog, Base, CoverageSnapshot, Member, Verification
from mcp_tools.db.utils import normalise_db_url
from mcp_tools.tools.verification import register as _reg_verification

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
    """A fresh FastMCP instance with verification tools wired to the test DB."""

    @asynccontextmanager
    async def _get_db(*_args, **_kwargs):
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    test_mcp = FastMCP("test-claims-tools-verification")
    _reg_verification(test_mcp, _get_db)
    return test_mcp


@pytest_asyncio.fixture()
async def db(session_factory):
    """Yield a transactional session for setup/assertion helpers."""
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture()
async def test_member(db):
    """Insert (and yield) a synthetic Member row for Jane Doe.

    Uses a unique member_id per test run to avoid cross-test contamination.
    """
    member = Member(
        id=uuid.uuid4(),
        member_id=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        first_name="Jane",
        last_name="Doe",
        dob=datetime.date(1985, 3, 4),
        zip="95814",
        employer_group="Acme Corp",
        subscriber_name="Jane Doe",
        relationship="self",
        payer_id="MOCKPAYER01",
    )
    db.add(member)
    await db.commit()
    yield member


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
# Test 1 – start_verification: known member, matching name
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_start_verification_known_matching_name(mcp_instance, db, test_member):
    """AC: name_match=true, next_question.id="dob", DB row in expected initial state."""
    session_id = f"s-{uuid.uuid4()}"
    resp = await _call(
        mcp_instance,
        "start_verification",
        {
            "session_id": session_id,
            "member_id": test_member.member_id,
            "full_name": "Jane Doe",
        },
    )
    assert resp["ok"] is True
    data = resp["data"]
    assert data["name_match"] is True
    assert data["next_question"]["id"] == "dob"
    assert data["next_question"]["prompt_hint"] == "date_of_birth"
    v_id = data["verification_id"]
    assert v_id is not None

    # Verify the DB row
    result = await db.execute(
        select(Verification).where(Verification.id == uuid.UUID(v_id))
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.status == "PENDING"
    assert row.attempts == 0
    asked = row.asked_question_ids or []
    assert "name:ok" in asked
    assert "dob" in asked


# ---------------------------------------------------------------------------
# Test 2 – start_verification: name mismatch
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_start_verification_name_mismatch(mcp_instance, db, test_member):
    """AC: name_match=false, next_question still returned, attempts=1."""
    session_id = f"s-{uuid.uuid4()}"
    resp = await _call(
        mcp_instance,
        "start_verification",
        {
            "session_id": session_id,
            "member_id": test_member.member_id,
            "full_name": "Completely Wrong Name",
        },
    )
    assert resp["ok"] is True
    data = resp["data"]
    assert data["name_match"] is False
    # next_question is still returned (no enumeration)
    assert "next_question" in data
    assert data["next_question"]["id"] == "dob"

    # DB row: attempts=1, name:fail
    result = await db.execute(
        select(Verification).where(Verification.id == uuid.UUID(data["verification_id"]))
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.attempts == 1
    asked = row.asked_question_ids or []
    assert "name:fail" in asked
    assert "dob" in asked


# ---------------------------------------------------------------------------
# Test 3 – start_verification: unknown member (no enumeration)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_start_verification_unknown_member(mcp_instance):
    """AC: unknown member_id returns NOT_FOUND_OR_MISMATCH (same code as mismatch)."""
    session_id = f"s-{uuid.uuid4()}"
    resp = await _call(
        mcp_instance,
        "start_verification",
        {
            "session_id": session_id,
            "member_id": "ZZZ000000000",
            "full_name": "Any Name",
        },
    )
    assert resp["ok"] is False
    assert resp["error"]["code"] == "NOT_FOUND_OR_MISMATCH"


# ---------------------------------------------------------------------------
# Test 4 – happy path: correct DOB then correct challenge → PASSED
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_check_answer_happy_path_passed(mcp_instance, db, test_member):
    """AC: correct DOB + correct challenge → PASSED, snapshot verified, audit rows."""
    session_id = f"s-{uuid.uuid4()}"

    # Insert a coverage snapshot so we can verify the status flip
    snap = CoverageSnapshot(
        id=uuid.uuid4(),
        session_id=session_id,
        member_id=test_member.member_id,
        payload={"plan_name": "Gold HMO 1000"},
        source="mock_payer",
        status="unverified",
    )
    db.add(snap)
    await db.commit()

    # Step 1: start verification
    start_resp = await _call(
        mcp_instance,
        "start_verification",
        {
            "session_id": session_id,
            "member_id": test_member.member_id,
            "full_name": "Jane Doe",
        },
    )
    assert start_resp["ok"] is True
    v_id = start_resp["data"]["verification_id"]

    # Step 2: answer DOB correctly
    dob_resp = await _call(
        mcp_instance,
        "check_answer",
        {
            "session_id": session_id,
            "verification_id": v_id,
            "question_id": "dob",
            "answer": "March 4 1985",
        },
    )
    assert dob_resp["ok"] is True
    assert dob_resp["data"]["status"] == "PENDING"
    # next_question should be a challenge question
    assert "next_question" in dob_resp["data"]
    challenge_qid = dob_resp["data"]["next_question"]["id"]
    assert challenge_qid in ("zip", "employer_group", "subscriber_name")

    # Step 3: answer the challenge correctly
    challenge_answers = {
        "zip": "95814",
        "employer_group": "Acme Corp",
        "subscriber_name": "Jane Doe",
    }
    final_resp = await _call(
        mcp_instance,
        "check_answer",
        {
            "session_id": session_id,
            "verification_id": v_id,
            "question_id": challenge_qid,
            "answer": challenge_answers[challenge_qid],
        },
    )
    assert final_resp["ok"] is True
    assert final_resp["data"]["status"] == "PASSED"

    # DB: verification row must be PASSED
    await db.refresh(snap)
    v_result = await db.execute(
        select(Verification).where(Verification.id == uuid.UUID(v_id))
    )
    row = v_result.scalar_one_or_none()
    assert row is not None
    assert row.status == "PASSED"

    # Snapshot must be flipped to 'verified'
    assert snap.status == "verified"

    # Audit row for verification_passed must exist
    audit_result = await db.execute(
        select(AuditLog).where(
            AuditLog.session_id == session_id,
            AuditLog.event == "verification_passed",
        )
    )
    audit = audit_result.scalar_one_or_none()
    assert audit is not None


# ---------------------------------------------------------------------------
# Test 5 – max attempts reached → LOCKED
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_check_answer_max_attempts_locked(mcp_instance, db, test_member):
    """AC: at MAX_VERIFY_ATTEMPTS wrong answers, status becomes LOCKED; audit row written."""
    session_id = f"s-{uuid.uuid4()}"

    # Pre-insert a Verification with 2 wrong answers already recorded
    # (attempts=2, name:ok, dob:fail, zip as next pending question)
    v_id = uuid.uuid4()
    verification = Verification(
        id=v_id,
        session_id=session_id,
        member_id=test_member.member_id,
        status="PENDING",
        attempts=2,
        asked_question_ids=["name:ok", "dob:fail", "zip"],
    )
    db.add(verification)
    await db.commit()

    # Third wrong answer → should lock
    resp = await _call(
        mcp_instance,
        "check_answer",
        {
            "session_id": session_id,
            "verification_id": str(v_id),
            "question_id": "zip",
            "answer": "00000",  # wrong ZIP
        },
    )
    assert resp["ok"] is True
    assert resp["data"]["status"] == "LOCKED"
    assert resp["data"]["remaining_attempts"] == 0

    # DB: row must be LOCKED
    await db.refresh(verification)
    assert verification.status == "LOCKED"
    assert verification.attempts == 3

    # Audit row for verification_locked must exist
    audit_result = await db.execute(
        select(AuditLog).where(
            AuditLog.session_id == session_id,
            AuditLog.event == "verification_locked",
        )
    )
    audit = audit_result.scalar_one_or_none()
    assert audit is not None


# ---------------------------------------------------------------------------
# Test 6 – check_answer after LOCKED: immediate LOCKED, attempts not incremented
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_check_answer_after_locked(mcp_instance, db, test_member):
    """AC: check_answer on a LOCKED verification returns LOCKED; attempts unchanged."""
    session_id = f"s-{uuid.uuid4()}"
    v_id = uuid.uuid4()
    verification = Verification(
        id=v_id,
        session_id=session_id,
        member_id=test_member.member_id,
        status="LOCKED",
        attempts=3,
        asked_question_ids=["name:ok", "dob:fail", "zip:fail", "employer_group:fail"],
    )
    db.add(verification)
    await db.commit()

    resp = await _call(
        mcp_instance,
        "check_answer",
        {
            "session_id": session_id,
            "verification_id": str(v_id),
            "question_id": "zip",
            "answer": "95814",
        },
    )
    assert resp["ok"] is True
    assert resp["data"]["status"] == "LOCKED"
    assert resp["data"]["remaining_attempts"] == 0

    # Attempts must NOT have been incremented
    await db.refresh(verification)
    assert verification.attempts == 3


# ---------------------------------------------------------------------------
# Test 7 – check_answer wrong answer: response contains no PHI
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_check_answer_no_phi_leak(mcp_instance, db, test_member):
    """AC: wrong answer response never contains DOB, ZIP, employer, or subscriber value."""
    session_id = f"s-{uuid.uuid4()}"

    # Start verification (name match)
    start_resp = await _call(
        mcp_instance,
        "start_verification",
        {
            "session_id": session_id,
            "member_id": test_member.member_id,
            "full_name": "Jane Doe",
        },
    )
    v_id = start_resp["data"]["verification_id"]

    # Submit a wrong DOB
    resp = await _call(
        mcp_instance,
        "check_answer",
        {
            "session_id": session_id,
            "verification_id": v_id,
            "question_id": "dob",
            "answer": "January 1 2000",  # wrong DOB
        },
    )
    assert resp["ok"] is True
    # Serialise full response and check no PHI leaks
    resp_text = json.dumps(resp)
    # Expected values that must never appear
    assert "1985" not in resp_text, "DOB year leaked into response"
    assert "03-04" not in resp_text, "DOB month/day leaked into response"
    assert "95814" not in resp_text, "ZIP leaked into response"
    assert "Acme" not in resp_text, "Employer name leaked into response"
    assert "1985-03-04" not in resp_text, "DOB ISO string leaked into response"
