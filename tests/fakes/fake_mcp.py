"""In-memory fake of the MCP tool contracts (`docs/contracts/mcp-tools.md`).

Implements the same async method surface as `agent.mcp_client.MCPClient`
(structurally: `agent.mcp_client.MCPClientProtocol`), backed by
`data/seed/members.json` / `data/seed/coverage.json` instead of a live
FastMCP server + Postgres. Story 2.x lands the real server; this fake lets
agent-side tests (story 3.1+) run with no network and no database.

Deliberately faithful to the contract's safety invariants:
  - unknown member IDs behave identically to known-but-wrong-answers members
    (no enumeration) — see `fetch_coverage` and `start_verification`.
  - `check_answer` never returns expected answers.
  - `get_policy_view` / `create_case` only succeed when verification PASSED.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

MAX_VERIFY_ATTEMPTS = 3
NAME_MATCH_THRESHOLD = 90
CHALLENGE_MATCH_THRESHOLD = 85

_SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"

_PROMPT_HINTS = {
    "dob": "date_of_birth",
    "zip": "zip_code",
}

_DOB_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%b %d, %Y",
)


def _load_seed(filename: str) -> list[dict[str, Any]]:
    with open(_SEED_DIR / filename, encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
    return data


def _parse_dob(raw: str) -> date | None:
    text = raw.strip()
    for fmt in _DOB_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message, **extra}}


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": data}


@dataclass
class _Snapshot:
    snapshot_id: str
    session_id: str
    member_id: str
    status: str  # unverified | verified | discarded


@dataclass
class _Verification:
    verification_id: str
    session_id: str
    member_id: str
    full_name: str
    name_match: bool
    attempts: int = 0
    status: str = "PENDING"  # PENDING | PASSED | FAILED | LOCKED
    dob_confirmed: bool = False
    current_question_id: str = "dob"
    asked_question_ids: list[str] = field(default_factory=list)


@dataclass
class _Case:
    case_number: str
    session_id: str
    member_id: str
    verification_id: str
    claim: dict[str, Any]
    status: str = "NEW"


class FakeMCPClient:
    """Same async surface as `MCPClient`, in-memory, from seed JSON.

    One instance is meant to live for the lifetime of a test / fake session
    store — attempt-tracking is keyed by `verification_id` and kept on the
    instance.
    """

    def __init__(self) -> None:
        members = _load_seed("members.json")
        coverage = _load_seed("coverage.json")
        self._members: dict[str, dict[str, Any]] = {m["member_id"]: m for m in members}
        self._coverage: dict[str, dict[str, Any]] = {c["member_id"]: c for c in coverage}

        self._snapshots: dict[str, _Snapshot] = {}
        self._verifications: dict[str, _Verification] = {}
        self._cases: dict[str, _Case] = {}
        self._cases_by_session: dict[str, str] = {}
        self._closed_sessions: set[str] = set()
        self._case_seq = 0

        # Test/debug introspection only — not part of the contract surface.
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.audit_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _record_call(self, name: str, **kwargs: Any) -> None:
        self.calls.append((name, kwargs))

    def _audit(self, session_id: str, event: str, detail: dict[str, Any]) -> None:
        self.audit_log.append({"session_id": session_id, "event": event, "detail": detail})

    def _answer_correct(self, question_id: str, answer: str, member: dict[str, Any] | None) -> bool:
        if member is None:
            return False
        if question_id == "dob":
            parsed = _parse_dob(answer)
            if parsed is None:
                return False
            return parsed.isoformat() == member["dob"]
        if question_id == "zip":
            digits = "".join(ch for ch in answer if ch.isdigit())[:5]
            return digits == member["zip"]
        return False

    # ------------------------------------------------------------------
    # 1. fetch_coverage
    # ------------------------------------------------------------------
    async def fetch_coverage(self, session_id: str, member_id: str) -> dict[str, Any]:
        self._record_call("fetch_coverage", session_id=session_id, member_id=member_id)
        member = self._members.get(member_id)
        self._audit(session_id, "coverage_fetched", {"member_id": member_id, "found": member is not None})
        if member is None:
            # Deliberately indistinguishable from a found-but-not-yet-verified member.
            return _ok({"snapshot_id": None, "found": False})
        snapshot_id = str(uuid.uuid4())
        self._snapshots[snapshot_id] = _Snapshot(
            snapshot_id=snapshot_id, session_id=session_id, member_id=member_id, status="unverified"
        )
        return _ok({"snapshot_id": snapshot_id, "found": True})

    # ------------------------------------------------------------------
    # 2. start_verification
    # ------------------------------------------------------------------
    async def start_verification(
        self, session_id: str, member_id: str, full_name: str
    ) -> dict[str, Any]:
        self._record_call(
            "start_verification", session_id=session_id, member_id=member_id, full_name=full_name
        )
        member = self._members.get(member_id)
        if member is not None:
            expected = f"{member['first_name']} {member['last_name']}"
            name_match = fuzz.token_sort_ratio(full_name, expected) >= NAME_MATCH_THRESHOLD
        else:
            name_match = False

        verification_id = str(uuid.uuid4())
        self._verifications[verification_id] = _Verification(
            verification_id=verification_id,
            session_id=session_id,
            member_id=member_id,
            full_name=full_name,
            name_match=name_match,
        )
        return _ok(
            {
                "verification_id": verification_id,
                "name_match": name_match,
                "next_question": {"id": "dob", "prompt_hint": _PROMPT_HINTS["dob"]},
            }
        )

    # ------------------------------------------------------------------
    # 3. check_answer
    # ------------------------------------------------------------------
    async def check_answer(
        self, session_id: str, verification_id: str, question_id: str, answer: str
    ) -> dict[str, Any]:
        self._record_call(
            "check_answer",
            session_id=session_id,
            verification_id=verification_id,
            question_id=question_id,
        )  # note: `answer` deliberately not recorded — never let PHI-ish answers leak into introspection
        record = self._verifications.get(verification_id)
        if record is None:
            return _error("NOT_FOUND_OR_MISMATCH", "unknown verification_id")

        if record.status in ("PASSED", "LOCKED", "FAILED"):
            return _ok(
                {
                    "status": record.status,
                    "attempts": record.attempts,
                    "remaining_attempts": max(MAX_VERIFY_ATTEMPTS - record.attempts, 0),
                    "next_question": None,
                }
            )

        member = self._members.get(record.member_id)
        correct = self._answer_correct(question_id, answer, member)
        record.asked_question_ids.append(question_id)

        if not correct:
            record.attempts += 1
            if record.attempts >= MAX_VERIFY_ATTEMPTS:
                record.status = "LOCKED"
                self._audit(session_id, "verification_locked", {"verification_id": verification_id})
                return _ok(
                    {"status": "LOCKED", "attempts": record.attempts, "remaining_attempts": 0, "next_question": None}
                )
            return _ok(
                {
                    "status": "PENDING",
                    "attempts": record.attempts,
                    "remaining_attempts": MAX_VERIFY_ATTEMPTS - record.attempts,
                    "next_question": {"id": question_id, "prompt_hint": _PROMPT_HINTS[question_id]},
                }
            )

        # Correct answer.
        if question_id == "dob":
            record.dob_confirmed = True
            record.current_question_id = "zip"
            return _ok(
                {
                    "status": "PENDING",
                    "attempts": record.attempts,
                    "remaining_attempts": MAX_VERIFY_ATTEMPTS - record.attempts,
                    "next_question": {"id": "zip", "prompt_hint": _PROMPT_HINTS["zip"]},
                }
            )

        # Single challenge question (zip) answered correctly: pass requires
        # name_match AND dob_confirmed AND this challenge correct.
        if record.dob_confirmed and record.name_match:
            record.status = "PASSED"
            snapshot = next(
                (
                    s
                    for s in self._snapshots.values()
                    if s.session_id == session_id and s.member_id == record.member_id
                ),
                None,
            )
            if snapshot is not None:
                snapshot.status = "verified"
            self._audit(session_id, "verification_passed", {"verification_id": verification_id})
            return _ok(
                {
                    "status": "PASSED",
                    "attempts": record.attempts,
                    "remaining_attempts": MAX_VERIFY_ATTEMPTS - record.attempts,
                    "next_question": None,
                }
            )

        # name mismatch: correct answers alone don't pass — counts as a failed attempt.
        record.attempts += 1
        if record.attempts >= MAX_VERIFY_ATTEMPTS:
            record.status = "LOCKED"
            self._audit(session_id, "verification_locked", {"verification_id": verification_id})
            return _ok(
                {"status": "LOCKED", "attempts": record.attempts, "remaining_attempts": 0, "next_question": None}
            )
        return _ok(
            {
                "status": "PENDING",
                "attempts": record.attempts,
                "remaining_attempts": MAX_VERIFY_ATTEMPTS - record.attempts,
                "next_question": {"id": "zip", "prompt_hint": _PROMPT_HINTS["zip"]},
            }
        )

    # ------------------------------------------------------------------
    # 4. get_policy_view
    # ------------------------------------------------------------------
    async def get_policy_view(self, session_id: str, verification_id: str) -> dict[str, Any]:
        self._record_call("get_policy_view", session_id=session_id, verification_id=verification_id)
        record = self._verifications.get(verification_id)
        if record is None or record.status != "PASSED":
            return _error("NOT_VERIFIED", "verification is not PASSED")
        coverage = self._coverage.get(record.member_id)
        if coverage is None:
            return _error("INTERNAL", "no coverage snapshot for verified member")
        self._audit(session_id, "policy_viewed", {"verification_id": verification_id})
        data = {k: v for k, v in coverage.items() if k != "member_id"}
        return _ok(data)

    # ------------------------------------------------------------------
    # 5. create_case
    # ------------------------------------------------------------------
    async def create_case(
        self, session_id: str, verification_id: str, claim: dict[str, Any]
    ) -> dict[str, Any]:
        self._record_call("create_case", session_id=session_id, verification_id=verification_id)
        record = self._verifications.get(verification_id)
        if record is None or record.status != "PASSED":
            return _error("NOT_VERIFIED", "verification is not PASSED")

        existing_case_number = self._cases_by_session.get(session_id)
        if existing_case_number is not None:
            existing = self._cases[existing_case_number]
            return _ok({"case_number": existing.case_number, "status": existing.status})

        required = [
            "claim_type",
            "patient_is_member",
            "date_of_service",
            "provider_name",
            "place_of_service",
            "reason_for_visit",
            "services",
            "amount_billed",
            "is_accident_related",
            "has_other_insurance",
        ]
        # booleans (False) and 0 amounts are valid values — only flag truly absent/empty fields.
        missing = [f for f in required if claim.get(f) in (None, [], "")]
        if missing:
            return _error("VALIDATION", "required claim fields are missing", fields=missing)

        self._case_seq += 1
        case_number = f"CLM-{date.today():%Y%m%d}-{self._case_seq:05d}"
        case = _Case(
            case_number=case_number,
            session_id=session_id,
            member_id=record.member_id,
            verification_id=verification_id,
            claim=claim,
        )
        self._cases[case_number] = case
        self._cases_by_session[session_id] = case_number
        self._audit(session_id, "case_created", {"case_number": case_number})
        return _ok({"case_number": case_number, "status": case.status})

    # ------------------------------------------------------------------
    # 6. get_case
    # ------------------------------------------------------------------
    async def get_case(self, case_number: str) -> dict[str, Any]:
        self._record_call("get_case", case_number=case_number)
        case = self._cases.get(case_number)
        if case is None:
            return _error("NOT_FOUND_OR_MISMATCH", "unknown case_number")
        return _ok(
            {
                "case_number": case.case_number,
                "session_id": case.session_id,
                "member_id": case.member_id,
                "verification_id": case.verification_id,
                "claim": case.claim,
                "status": case.status,
            }
        )

    # ------------------------------------------------------------------
    # 7. end_session
    # ------------------------------------------------------------------
    async def end_session(self, session_id: str, reason: str) -> dict[str, Any]:
        self._record_call("end_session", session_id=session_id, reason=reason)
        for snapshot in self._snapshots.values():
            if snapshot.session_id == session_id and snapshot.status == "unverified":
                snapshot.status = "discarded"
        self._closed_sessions.add(session_id)
        self._audit(session_id, "session_ended", {"reason": reason})
        return _ok({"closed": True})

    async def ping(self) -> dict[str, bool]:
        return {"pong": True}
