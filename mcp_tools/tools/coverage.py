"""FastMCP coverage tools: fetch_coverage, get_policy_view, end_session.

These three tools form the coverage-query side of the claims-intake MCP server.
All three conform to the JSON envelope contract in docs/contracts/mcp-tools.md §1, §4, §7.

PHI invariant: member_id, DOBs, and challenge answers must NEVER appear in span
attributes, log lines, or error messages.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_tools.db.models import AuditLog, CoverageSnapshot, Verification
from mcp_tools.payer_mock import PayerClient, PayerUnavailable
from observability import tracing

# Valid reason codes for end_session (§7)
_VALID_REASONS = frozenset(
    {
        "cancelled",
        "handoff_user",
        "handoff_locked",
        "handoff_clarify_cap",
        "handoff_error",
        "completed",
    }
)

# ---------------------------------------------------------------------------
# Response-envelope helpers
# ---------------------------------------------------------------------------


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _err(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# register() factory
# ---------------------------------------------------------------------------

GetDb = Callable[..., AbstractAsyncContextManager[AsyncSession]]


def register(mcp: FastMCP, payer: PayerClient, get_db: GetDb) -> None:
    """Register fetch_coverage, get_policy_view, and end_session on *mcp*.

    Parameters
    ----------
    mcp:
        The FastMCP instance to register tools on.
    payer:
        A PayerClient implementation (MockPayerClient in development/demo / test doubles in tests).
    get_db:
        An async context manager factory that yields an AsyncSession.
        Matches the signature of ``mcp_tools.db.session.get_session``.
    """

    @mcp.tool()
    async def fetch_coverage(session_id: str, member_id: str) -> dict[str, Any]:
        """Fetch eligibility from the payer and store an unverified snapshot.

        Returns {ok: true, data: {snapshot_id: <uuid|null>, found: <bool>}}.
        The coverage payload is NEVER returned to the caller.
        Audit event: coverage_fetched.
        """
        # Always call payer first — even for unknown IDs — to equalise timing (AC4).
        try:
            eligibility = await payer.get_eligibility(member_id)
        except PayerUnavailable:
            return _err("PAYER_UNAVAILABLE", "Payer service unavailable.")

        found = eligibility is not None
        snap_id: uuid.UUID | None = uuid.uuid4() if found else None

        with tracing.span(
            "mcp.fetch_coverage",
            found=found,
            snapshot_id=str(snap_id) if snap_id else None,
        ):
            try:
                if found:
                    async with get_db() as session:
                        snapshot = CoverageSnapshot(
                            id=snap_id,
                            session_id=session_id,
                            member_id=member_id,
                            payload=eligibility,
                            source="mock_payer",
                            status="unverified",
                        )
                        session.add(snapshot)
                        audit = AuditLog(
                            session_id=session_id,
                            event="coverage_fetched",
                            detail={"found": True, "snapshot_id": str(snap_id)},
                        )
                        session.add(audit)
                else:
                    async with get_db() as session:
                        audit = AuditLog(
                            session_id=session_id,
                            event="coverage_fetched",
                            detail={"found": False},
                        )
                        session.add(audit)
            except Exception:
                return _err("INTERNAL", "An internal error occurred.")

            return _ok({"snapshot_id": str(snap_id) if snap_id else None, "found": found})

    @mcp.tool()
    async def get_policy_view(session_id: str, verification_id: str) -> dict[str, Any]:
        """Return the coverage policy for a verified member.

        Returns NOT_VERIFIED for any non-PASSED verification status, including
        unknown IDs (no enumeration).
        Audit event: policy_viewed on success; policy_view_denied on NOT_VERIFIED.
        """
        try:
            v_uuid = uuid.UUID(verification_id)
        except ValueError:
            # Treat malformed UUID identically to unknown/unverified — no enumeration.
            async with get_db() as session:
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="policy_view_denied",
                        detail={"reason": "malformed_verification_id"},
                    )
                )
            return _err("NOT_VERIFIED", "Verification not found or not passed.")

        async with get_db() as session:
            # Look up verification scoped to this session — return NOT_VERIFIED for
            # any missing, wrong-session, or non-PASSED record (no enumeration).
            v_result = await session.execute(
                select(Verification).where(
                    Verification.id == v_uuid,
                    Verification.session_id == session_id,
                )
            )
            verification = v_result.scalar_one_or_none()

            if verification is None or verification.status != "PASSED":
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="policy_view_denied",
                        detail={"reason": "not_verified"},
                    )
                )
                return _err("NOT_VERIFIED", "Verification not found or not passed.")

            # Fetch the most recent non-discarded snapshot for this session.
            snap_result = await session.execute(
                select(CoverageSnapshot)
                .where(
                    CoverageSnapshot.session_id == session_id,
                    CoverageSnapshot.status != "discarded",
                )
                .order_by(CoverageSnapshot.fetched_at.desc())
                .limit(1)
            )
            snapshot = snap_result.scalar_one_or_none()

            if snapshot is None or snapshot.payload is None:
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="policy_view_denied",
                        detail={"reason": "snapshot_unavailable"},
                    )
                )
                return _err("NOT_VERIFIED", "Coverage snapshot not available.")

            # Strip PHI (member_id) before returning.
            policy = {k: v for k, v in snapshot.payload.items() if k != "member_id"}

            # Write success audit row.
            session.add(
                AuditLog(
                    session_id=session_id,
                    event="policy_viewed",
                    detail={"verification_id": str(v_uuid)},
                )
            )

        return _ok(policy)

    @mcp.tool()
    async def end_session(session_id: str, reason: str) -> dict[str, Any]:
        """Close a session: discard unverified snapshots and write audit.

        Idempotent — calling twice returns {ok: true, data: {closed: true}}.
        Audit event: session_ended.
        """
        if reason not in _VALID_REASONS:
            valid = ", ".join(sorted(_VALID_REASONS))
            return _err("VALIDATION", f"Invalid reason. Must be one of: {valid}")

        try:
            async with get_db() as session:
                # Discard any unverified snapshots for this session.
                snap_result = await session.execute(
                    select(CoverageSnapshot).where(
                        CoverageSnapshot.session_id == session_id,
                        CoverageSnapshot.status == "unverified",
                    )
                )
                for snapshot in snap_result.scalars().all():
                    snapshot.status = "discarded"

                # Idempotent: audit row written every call (re-calling is a no-op from
                # the caller's perspective, but we still record the event).
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="session_ended",
                        detail={"reason": reason},
                    )
                )
        except Exception:
            return _err("INTERNAL", "An internal error occurred.")

        return _ok({"closed": True})
