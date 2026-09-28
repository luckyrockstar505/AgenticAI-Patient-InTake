"""FastMCP verification tools: start_verification, check_answer.

These two tools form the identity-verification side of the claims-intake MCP
server. They conform to the JSON envelope contract in docs/contracts/mcp-tools.md
§2–3.

PHI invariant: DOBs, ZIP codes, employer names, and challenge answers must NEVER
appear in span attributes, log lines, or error messages.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import random
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from dateutil import parser as _dateutil_parser
from dateutil.parser import ParserError
from fastmcp import FastMCP
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_tools.db.models import AuditLog, CoverageSnapshot, Member, Verification
from observability import tracing

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_VERIFY_ATTEMPTS: int = int(os.environ.get("MAX_VERIFY_ATTEMPTS", "3"))

# Challenge questions (DOB is always first; challenge is drawn from this pool)
_CHALLENGE_QUESTIONS = ["zip", "employer_group", "subscriber_name"]

# All valid question IDs
_VALID_QUESTION_IDS = frozenset(["dob"] + _CHALLENGE_QUESTIONS)

# Mapping from question_id to prompt_hint value returned to the agent
_PROMPT_HINTS: dict[str, str] = {
    "dob": "date_of_birth",
    "zip": "zip_code",
    "employer_group": "employer_group",
    "subscriber_name": "subscriber_name",
}

# The not-found response shape (identical to name-mismatch — no enumeration)
_NOT_FOUND_RESPONSE: dict[str, Any] = {
    "verification_id": None,
    "name_match": False,
    "next_question": {"id": "dob", "prompt_hint": "date_of_birth"},
}

# ---------------------------------------------------------------------------
# Response-envelope helpers
# ---------------------------------------------------------------------------


def _ok(data: dict[str, Any]) -> dict:
    return {"ok": True, "data": data}


def _err(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Normalizers / matchers  (PHI: expected values must never appear in output)
# ---------------------------------------------------------------------------


def _name_match(full_name: str, first: str, last: str) -> bool:
    """Rapidfuzz token-sort ratio >= 90 against first + last name."""
    expected = f"{first} {last}".strip()
    score = fuzz.token_sort_ratio(full_name.strip().lower(), expected.lower())
    return score >= 90


def _dob_match(answer: str, expected_dob: datetime.date | None) -> bool:
    """Parse *answer* as a date and compare to *expected_dob*.

    Uses dateutil.parser.parse with dayfirst=False.
    Rejects 2-digit years that resolve to a future year.
    Returns False on any parse error or mismatch.  Never raises.
    """
    if expected_dob is None:
        return False
    try:
        parsed = _dateutil_parser.parse(answer, dayfirst=False)
    except (ParserError, ValueError, OverflowError, TypeError):
        return False
    # Reject 2-digit years that resolve to a future year
    if parsed.year > datetime.date.today().year:
        return False
    return parsed.date() == expected_dob


def _zip_match(answer: str, expected_zip: str | None) -> bool:
    """Compare first 5 digits of *answer* to the first 5 digits of *expected_zip*."""
    if expected_zip is None:
        return False
    ans_digits = "".join(c for c in answer if c.isdigit())[:5]
    exp_digits = "".join(c for c in expected_zip if c.isdigit())[:5]
    return bool(ans_digits) and ans_digits == exp_digits


def _fuzzy_match(answer: str, expected: str | None) -> bool:
    """Token-sort ratio >= 85 for employer/subscriber name comparison."""
    if expected is None:
        return False
    score = fuzz.token_sort_ratio(answer.strip().lower(), expected.strip().lower())
    return score >= 85


# ---------------------------------------------------------------------------
# Question selection
# ---------------------------------------------------------------------------


def _pick_question(asked_ids: list[str], seed: int | str) -> str | None:
    """Pick the next unused challenge question.

    Filters ``_CHALLENGE_QUESTIONS`` to those not already present in
    *asked_ids* in any form (pending, :ok, or :fail), then uses a seeded
    ``random.Random`` for reproducibility.  Returns ``None`` when all
    challenge questions have been exhausted.
    """
    # Extract the base name from each asked entry (e.g. "zip:ok" → "zip")
    asked_base = {entry.split(":")[0] for entry in asked_ids}
    available = [q for q in _CHALLENGE_QUESTIONS if q not in asked_base]
    if not available:
        return None
    rng = random.Random(seed)
    return rng.choice(available)


# ---------------------------------------------------------------------------
# Pass criteria
# ---------------------------------------------------------------------------


def _check_pass(asked_ids: list[str]) -> bool:
    """Return True iff all three pass criteria are satisfied.

    Pass = name:ok AND dob:ok AND at least one challenge question :ok
    """
    challenge_ok = any(f"{q}:ok" in asked_ids for q in _CHALLENGE_QUESTIONS)
    return "name:ok" in asked_ids and "dob:ok" in asked_ids and challenge_ok


# ---------------------------------------------------------------------------
# register() factory
# ---------------------------------------------------------------------------

GetDb = Callable[..., AbstractAsyncContextManager[AsyncSession]]


def register(mcp: FastMCP, get_db: GetDb) -> None:
    """Register ``start_verification`` and ``check_answer`` on *mcp*.

    Parameters
    ----------
    mcp:
        The FastMCP instance to register tools on.
    get_db:
        An async context manager factory that yields an ``AsyncSession``.
        Matches the signature of ``mcp_tools.db.session.get_session``.
    """

    @mcp.tool()
    async def start_verification(
        session_id: str,
        member_id: str,
        full_name: str,
    ) -> dict:
        """Create a verification record and perform identity pre-checks.

        Returns ``{ok: true, data: {verification_id, name_match, next_question}}``.
        Unknown member IDs return the same response shape as a name mismatch
        (verification_id=None) so that callers cannot enumerate valid IDs.
        Audit event: ``verification_started``.
        """
        async with get_db() as session:
            result = await session.execute(
                select(Member).where(Member.member_id == member_id)
            )
            member = result.scalar_one_or_none()

            if member is None:
                # No enumeration: return same shape as mismatch, with verification_id=None
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="verification_started",
                        detail={"member_found": False},
                    )
                )
                with tracing.span("mcp.start_verification", name_match=False):
                    pass
                return _ok(_NOT_FOUND_RESPONSE)

            name_ok = _name_match(full_name, member.first_name, member.last_name)
            name_marker = "name:ok" if name_ok else "name:fail"
            initial_attempts = 0 if name_ok else 1

            # DOB is always the first question (§2 — pending marker "dob")
            asked_ids: list[str] = [name_marker, "dob"]
            v_id = uuid.uuid4()
            verification = Verification(
                id=v_id,
                session_id=session_id,
                member_id=member_id,
                status="PENDING",
                attempts=initial_attempts,
                asked_question_ids=asked_ids,
            )
            session.add(verification)
            session.add(
                AuditLog(
                    session_id=session_id,
                    event="verification_started",
                    detail={
                        "verification_id": str(v_id),
                        "name_match": name_ok,
                        "attempts": initial_attempts,
                    },
                )
            )

        with tracing.span("mcp.start_verification", name_match=name_ok):
            pass

        return _ok(
            {
                "verification_id": str(v_id),
                "name_match": name_ok,
                "next_question": {"id": "dob", "prompt_hint": _PROMPT_HINTS["dob"]},
            }
        )

    @mcp.tool()
    async def check_answer(
        session_id: str,
        verification_id: str,
        question_id: str,
        answer: str,
    ) -> dict:
        """Evaluate an answer to a verification question.

        Returns ``{ok: true, data: {status, attempts, remaining_attempts, next_question?}}``.
        Expected answers are never returned in any field.
        Span ``mcp.check_answer`` records ``question_id``, ``status``, ``attempts`` only.
        Audit events: ``verification_answer`` (every answer), ``verification_passed``,
        ``verification_locked``.
        """
        # Validate UUID early — return VALIDATION, no DB access needed
        try:
            v_uuid = uuid.UUID(verification_id)
        except ValueError:
            return _err("VALIDATION", "Invalid verification_id format.")

        # Validate question_id before touching the DB
        if question_id not in _VALID_QUESTION_IDS:
            return _err("VALIDATION", "Unknown question_id.")

        # Stable seed: explicit env var (for evals/tests) or SHA-256-based fallback
        verify_seed: str = os.environ.get(
            "VERIFY_SEED",
            hashlib.sha256(verification_id.encode()).hexdigest(),
        )

        max_attempts = int(os.environ.get("MAX_VERIFY_ATTEMPTS", str(MAX_VERIFY_ATTEMPTS)))

        async with get_db() as session:
            v_result = await session.execute(
                select(Verification).where(
                    Verification.id == v_uuid,
                    Verification.session_id == session_id,
                )
            )
            verification = v_result.scalar_one_or_none()

            if verification is None:
                return _err("NOT_FOUND_OR_MISMATCH", "Verification not found.")

            # Already LOCKED — return immediately, no processing, no attempt increment
            if verification.status == "LOCKED":
                outcome_attempts = verification.attempts
                with tracing.span(
                    "mcp.check_answer",
                    question_id=question_id,
                    status="LOCKED",
                    attempts=outcome_attempts,
                ):
                    pass
                return _ok(
                    {
                        "status": "LOCKED",
                        "attempts": outcome_attempts,
                        "remaining_attempts": 0,
                    }
                )

            # Already PASSED — return immediately
            if verification.status == "PASSED":
                outcome_attempts = verification.attempts
                with tracing.span(
                    "mcp.check_answer",
                    question_id=question_id,
                    status="PASSED",
                    attempts=outcome_attempts,
                ):
                    pass
                return _ok(
                    {
                        "status": "PASSED",
                        "attempts": outcome_attempts,
                        "remaining_attempts": max(0, max_attempts - outcome_attempts),
                    }
                )

            # Load the member to evaluate the answer (PHI: never log member fields)
            m_result = await session.execute(
                select(Member).where(Member.member_id == verification.member_id)
            )
            member = m_result.scalar_one_or_none()
            if member is None:
                return _err("INTERNAL", "An internal error occurred.")

            # Guard: reject a question that has already been answered in this session
            current_ids: list[str] = list(verification.asked_question_ids or [])
            if any(entry.startswith(question_id + ":") for entry in current_ids):
                return _err("VALIDATION", "Question already answered.")

            # ----------------------------------------------------------------
            # Evaluate the answer
            # ----------------------------------------------------------------
            correct = False
            if question_id == "dob":
                correct = _dob_match(answer, member.dob)
            elif question_id == "zip":
                correct = _zip_match(answer, member.zip)
            elif question_id == "employer_group":
                correct = _fuzzy_match(answer, member.employer_group)
            elif question_id == "subscriber_name":
                correct = _fuzzy_match(answer, member.subscriber_name)

            # ----------------------------------------------------------------
            # Update asked_question_ids: replace the pending marker with :ok/:fail
            # ----------------------------------------------------------------
            suffix = ":ok" if correct else ":fail"
            new_ids: list[str] = []
            replaced = False
            for entry in current_ids:
                # Replace the first occurrence of the bare question_id (pending)
                if entry == question_id and not replaced:
                    new_ids.append(f"{question_id}{suffix}")
                    replaced = True
                else:
                    new_ids.append(entry)
            if not replaced:
                # question_id was not pending in the list — append result anyway
                new_ids.append(f"{question_id}{suffix}")

            # Wrong answers increment the attempt counter
            if not correct:
                verification.attempts += 1

            current_attempts = verification.attempts

            # ----------------------------------------------------------------
            # Determine outcome
            # ----------------------------------------------------------------
            if _check_pass(new_ids):
                verification.status = "PASSED"
                verification.asked_question_ids = new_ids

                # Flip the most-recent non-discarded snapshot to 'verified'
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
                if snapshot is not None:
                    snapshot.status = "verified"

                # Audit: every answer + passed
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="verification_answer",
                        detail={
                            "verification_id": str(v_uuid),
                            "question_id": question_id,
                            "correct": correct,
                            "attempts": current_attempts,
                        },
                    )
                )
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="verification_passed",
                        detail={
                            "verification_id": str(v_uuid),
                            "attempts": current_attempts,
                        },
                    )
                )

                with tracing.span(
                    "mcp.check_answer",
                    question_id=question_id,
                    status="PASSED",
                    attempts=current_attempts,
                ):
                    pass

                return _ok(
                    {
                        "status": "PASSED",
                        "attempts": current_attempts,
                        "remaining_attempts": max(0, max_attempts - current_attempts),
                    }
                )

            if current_attempts >= max_attempts:
                verification.status = "LOCKED"
                verification.asked_question_ids = new_ids

                # Audit: every answer + locked
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="verification_answer",
                        detail={
                            "verification_id": str(v_uuid),
                            "question_id": question_id,
                            "correct": correct,
                            "attempts": current_attempts,
                        },
                    )
                )
                session.add(
                    AuditLog(
                        session_id=session_id,
                        event="verification_locked",
                        detail={
                            "verification_id": str(v_uuid),
                            "attempts": current_attempts,
                        },
                    )
                )

                with tracing.span(
                    "mcp.check_answer",
                    question_id=question_id,
                    status="LOCKED",
                    attempts=current_attempts,
                ):
                    pass

                return _ok(
                    {
                        "status": "LOCKED",
                        "attempts": current_attempts,
                        "remaining_attempts": 0,
                    }
                )

            # ----------------------------------------------------------------
            # Still PENDING — pick next question when needed
            # ----------------------------------------------------------------
            next_q: dict[str, str] | None = None

            # After DOB or a wrong challenge answer, offer the next unused question
            if question_id == "dob" or (question_id in _CHALLENGE_QUESTIONS and not correct):
                next_qid = _pick_question(new_ids, verify_seed)
                if next_qid is not None:
                    next_q = {"id": next_qid, "prompt_hint": _PROMPT_HINTS[next_qid]}
                    new_ids.append(next_qid)  # mark as pending
                else:
                    # All challenge questions exhausted, pass criteria unmet → lock
                    verification.status = "LOCKED"
                    verification.asked_question_ids = new_ids

                    session.add(
                        AuditLog(
                            session_id=session_id,
                            event="verification_answer",
                            detail={
                                "verification_id": str(v_uuid),
                                "question_id": question_id,
                                "correct": correct,
                                "attempts": current_attempts,
                            },
                        )
                    )
                    session.add(
                        AuditLog(
                            session_id=session_id,
                            event="verification_locked",
                            detail={
                                "verification_id": str(v_uuid),
                                "attempts": current_attempts,
                                "reason": "questions_exhausted",
                            },
                        )
                    )

                    with tracing.span(
                        "mcp.check_answer",
                        question_id=question_id,
                        status="LOCKED",
                        attempts=current_attempts,
                    ):
                        pass

                    return _ok(
                        {
                            "status": "LOCKED",
                            "attempts": current_attempts,
                            "remaining_attempts": 0,
                        }
                    )

            verification.status = "PENDING"
            verification.asked_question_ids = new_ids

            session.add(
                AuditLog(
                    session_id=session_id,
                    event="verification_answer",
                    detail={
                        "verification_id": str(v_uuid),
                        "question_id": question_id,
                        "correct": correct,
                        "attempts": current_attempts,
                        # PHI: answer value is intentionally omitted
                    },
                )
            )

            with tracing.span(
                "mcp.check_answer",
                question_id=question_id,
                status="PENDING",
                attempts=current_attempts,
            ):
                pass

        response_data: dict[str, Any] = {
            "status": "PENDING",
            "attempts": current_attempts,
            "remaining_attempts": max(0, max_attempts - current_attempts),
        }
        if next_q is not None:
            response_data["next_question"] = next_q
        return _ok(response_data)
