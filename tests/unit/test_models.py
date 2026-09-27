"""Unit tests for SQLAlchemy 2.x mapped models (story 2.1).

No live database required — only imports and metadata inspection.
"""
from __future__ import annotations

import inspect

from sqlalchemy import inspect as sa_inspect

from mcp_tools.db import (
    AuditLog,
    Base,
    Callback,
    Case,
    CoverageSnapshot,
    Member,
    Verification,
    get_engine,
    get_session,
)

# ---------------------------------------------------------------------------
# Table name assertions
# ---------------------------------------------------------------------------


def test_member_tablename() -> None:
    assert Member.__tablename__ == "members"


def test_coverage_snapshot_tablename() -> None:
    assert CoverageSnapshot.__tablename__ == "coverage_snapshots"


def test_verification_tablename() -> None:
    assert Verification.__tablename__ == "verifications"


def test_case_tablename() -> None:
    assert Case.__tablename__ == "cases"


def test_callback_tablename() -> None:
    assert Callback.__tablename__ == "callbacks"


def test_audit_log_tablename() -> None:
    assert AuditLog.__tablename__ == "audit_log"


# ---------------------------------------------------------------------------
# Column presence assertions
# ---------------------------------------------------------------------------


def _col_names(model) -> set[str]:
    return {c.name for c in sa_inspect(model).columns}


def test_member_has_expected_columns() -> None:
    cols = _col_names(Member)
    for expected in (
        "id", "member_id", "first_name", "last_name", "dob", "zip",
        "employer_group", "subscriber_name", "relationship", "payer_id",
        "created_at",
    ):
        assert expected in cols, f"Member missing column: {expected}"


def test_coverage_snapshot_has_expected_columns() -> None:
    cols = _col_names(CoverageSnapshot)
    for expected in ("id", "session_id", "member_id", "payload", "source", "status", "fetched_at"):
        assert expected in cols, f"CoverageSnapshot missing column: {expected}"


def test_verification_has_expected_columns() -> None:
    cols = _col_names(Verification)
    for expected in (
        "id", "session_id", "member_id", "status", "attempts",
        "asked_question_ids", "created_at", "updated_at",
    ):
        assert expected in cols, f"Verification missing column: {expected}"


def test_case_has_missing_fields_and_complete() -> None:
    """A-3 requirement: cases must have missing_fields (ARRAY) and complete (bool)."""
    cols = _col_names(Case)
    assert "missing_fields" in cols, "Case missing 'missing_fields' column (A-3)"
    assert "complete" in cols, "Case missing 'complete' column (A-3)"


def test_case_has_expected_columns() -> None:
    cols = _col_names(Case)
    for expected in (
        "id", "case_number", "session_id", "member_id", "snapshot_id",
        "verification_id", "claim", "missing_fields", "complete", "status",
        "created_at",
    ):
        assert expected in cols, f"Case missing column: {expected}"


def test_callback_has_expected_columns() -> None:
    """A-1 requirement: callbacks table must exist with member_id_hash column."""
    cols = _col_names(Callback)
    for expected in (
        "id", "session_id", "member_id_hash", "contact_number", "status", "created_at",
    ):
        assert expected in cols, f"Callback missing column: {expected}"


def test_audit_log_has_expected_columns() -> None:
    cols = _col_names(AuditLog)
    for expected in ("id", "session_id", "event", "detail", "created_at"):
        assert expected in cols, f"AuditLog missing column: {expected}"


# ---------------------------------------------------------------------------
# Metadata completeness
# ---------------------------------------------------------------------------


def test_all_six_tables_in_metadata() -> None:
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "members",
        "coverage_snapshots",
        "verifications",
        "cases",
        "callbacks",
        "audit_log",
    }
    assert expected == table_names, (
        f"Unexpected tables in metadata.\n  expected: {expected}\n  got: {table_names}"
    )


# ---------------------------------------------------------------------------
# Session / engine exports
# ---------------------------------------------------------------------------


def test_get_engine_is_callable() -> None:
    assert callable(get_engine)


def test_get_session_is_async_context_manager() -> None:
    """get_session must be an async context manager factory.

    @asynccontextmanager wraps an async generator function.  The wrapper
    itself is callable and returns an object with __aenter__/__aexit__.
    The underlying function (.__wrapped__) is an async generator.
    """
    assert callable(get_session)
    # The wrapped function is an async generator function
    wrapped = get_session.__wrapped__  # type: ignore[attr-defined]
    assert inspect.isasyncgenfunction(wrapped)
