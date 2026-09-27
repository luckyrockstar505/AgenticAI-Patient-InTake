"""PHI redaction for MLflow spans and Python log records.

Story 1.4: implements the real redaction patterns.

Masks: member IDs, DOB, ZIP, phone, email, NPI, and per-session known values
(names, member IDs) registered via Redactor.register().

Usage
-----
    from observability.redaction import redact, get_redactor

    # One-off redaction (uses the process-wide default instance):
    clean = redact({"member_id": "ABC123456789", "note": "Hello Maria"})

    # Per-session known-value registration:
    get_redactor().register("Maria Garcia")
    get_redactor().register("ABC123456789")
"""
from __future__ import annotations

import re
import threading
from typing import Any

# ---------------------------------------------------------------------------
# Compiled regex patterns
# ---------------------------------------------------------------------------
# Member ID: 3 uppercase letters + 9 digits  (e.g. ABC123456789)
_MEMBER_ID_RE = re.compile(r"[A-Z]{3}\d{9}")

# ISO-8601 dates that could be DOBs (YYYY-MM-DD)
_DOB_RE = re.compile(r"\b\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b")

# US 5-digit ZIP codes (standalone tokens)
_ZIP_RE = re.compile(r"\b\d{5}\b")

# US phone numbers in common formats: 415-555-0123 / 415.555.0123 / 415 555 0123
_PHONE_RE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")

# Email addresses
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

# SSN: 123-45-6789
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# NPI: exactly 10 consecutive digits (not surrounded by other digits)
_NPI_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")


class Redactor:
    """Thread-safe PHI redactor.

    Combines compiled regex patterns with a per-session set of known values
    (names, member IDs) registered at runtime via :meth:`register`.

    Known-value masking always runs before regex masking so that a name like
    "ABC123456789" isn't partially obscured by the member-ID regex before the
    full known-value replacement fires.
    """

    def __init__(self) -> None:
        self._known_values: set[str] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, value: str) -> None:
        """Register a known PHI string for exact-match masking.

        Registered values are replaced with ``[NAME]`` or ``[ID]`` depending
        on whether they match the member-ID pattern.  Callers may register
        full names, member IDs, or any other per-session sensitive string.
        """
        if value and isinstance(value, str):
            with self._lock:
                self._known_values.add(value)

    def redact(self, obj: Any) -> Any:
        """Recursively redact PHI from *obj*.

        * ``str``  — regex + known-value masking applied
        * ``dict`` — all values (not keys) redacted recursively
        * ``list`` — all elements redacted recursively
        * anything else (int, float, bool, None, …) — returned unchanged
        """
        if obj is None or isinstance(obj, bool | int | float):
            return obj
        if isinstance(obj, str):
            return self._redact_string(obj)
        if isinstance(obj, dict):
            return {k: self.redact(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.redact(item) for item in obj]
        return obj

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _redact_string(self, s: str) -> str:
        # 1. Known-value masking (longest values first to avoid partial hits)
        # Copy the set under the lock to avoid holding the lock during regex ops.
        with self._lock:
            known = frozenset(self._known_values)

        for val in sorted(known, key=len, reverse=True):
            if val.lower() in s.lower():
                replacement = "[ID]" if _MEMBER_ID_RE.fullmatch(val) else "[NAME]"
                s = re.sub(re.escape(val), replacement, s, flags=re.IGNORECASE)

        # 2. SSN (before phone so ###-##-#### isn't consumed by phone RE)
        s = _SSN_RE.sub("[SSN]", s)

        # 3. Phone numbers
        s = _PHONE_RE.sub("[PHONE]", s)

        # 4. Email
        s = _EMAIL_RE.sub("[EMAIL]", s)

        # 5. NPI (10-digit standalone – before generic member-ID so no double-hit)
        s = _NPI_RE.sub("[NPI]", s)

        # 6. Member ID (regex-only fallback for un-registered IDs)
        s = _MEMBER_ID_RE.sub("[ID]", s)

        # 7. DOB
        s = _DOB_RE.sub("[DOB]", s)

        # 8. ZIP (last, so dates/NPIs/IDs parsed above don't leave stray 5-digit runs)
        s = _ZIP_RE.sub("[ZIP]", s)

        return s


# ---------------------------------------------------------------------------
# Module-level default instance + convenience functions
# ---------------------------------------------------------------------------

#: Process-wide default redactor.  ``init_tracing()`` in ``tracing.py``
#: attaches this to the MLflow span processor.  Call
#: ``get_redactor().register(value)`` per session to add known values.
_default_redactor = Redactor()


def get_redactor() -> Redactor:
    """Return the process-wide default :class:`Redactor` instance."""
    return _default_redactor


def clear_default_redactor() -> None:
    """Replace the default redactor with a fresh instance.

    Intended for session cleanup and test teardown to prevent known-value
    bleed between sessions or test cases.
    """
    global _default_redactor
    _default_redactor = Redactor()


def redact(value: Any) -> Any:
    """Redact PHI from *value* using the process-wide :data:`_default_redactor`.

    Handles ``str``, ``dict``, ``list``, and nested combinations thereof.
    Non-string scalars are returned unchanged.
    """
    return _default_redactor.redact(value)
