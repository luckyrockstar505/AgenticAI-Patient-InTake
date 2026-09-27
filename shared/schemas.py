"""Shared contract models — imported by both agent and mcp_tools.

Story 1.1: placeholder definitions that establish the correct import structure.
Story 4.1 will replace ClaimDraft with the full extraction model.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

# Required fields for a complete claim submission
REQUIRED: list[str] = [
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


class ClaimDraft(BaseModel):
    """Partial claim that accumulates across turns.  None = not yet provided."""

    claim_type: Literal["medical", "pharmacy", "dental", "vision"] | None = None
    patient_is_member: bool | None = None
    date_of_service: str | None = None  # ISO date string; validated in story 4.1
    provider_name: str | None = None
    provider_npi: str | None = None  # optional, 10-digit NPI
    place_of_service: (
        Literal[
            "office",
            "hospital_inpatient",
            "hospital_outpatient",
            "emergency_room",
            "urgent_care",
            "telehealth",
            "pharmacy",
            "other",
        ]
        | None
    ) = None
    reason_for_visit: str | None = None
    services: list[str] = []
    amount_billed: Decimal | None = None
    amount_paid_by_member: Decimal | None = None
    is_accident_related: bool | None = None
    accident_type: Literal["auto", "work", "other"] | None = None
    has_other_insurance: bool | None = None
    notes: str | None = None
