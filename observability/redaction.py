"""PHI redaction stub.

Story 1.1: placeholder with correct interface from architecture §10.
Story 1.4 implements the real redaction patterns.

Masks: member IDs, names, DOB, ZIP, phone, email, NPI, dollar amounts (optional).
Applied to log records and MLflow span inputs/outputs.
"""
from __future__ import annotations

from typing import Any


def redact(value: Any) -> Any:
    """Redact PHI from a value (string, dict, or list).

    Story 1.4 provides the real implementation.
    """
    return value


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Redact PHI from all values in a dict.

    Story 1.4 provides the real implementation.
    """
    return data
