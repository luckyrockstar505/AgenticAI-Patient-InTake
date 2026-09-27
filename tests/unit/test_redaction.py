"""Table-driven unit tests for the PHI redactor.

Covers every row in the I/O matrix defined in the story-1.4 spec.
No live MLflow server required — these tests are pure-Python.
"""
from __future__ import annotations

import pytest

from observability.redaction import Redactor, redact

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fresh() -> Redactor:
    """Return a new Redactor without any registered known values."""
    return Redactor()


# ---------------------------------------------------------------------------
# I/O matrix from the spec (parameterised)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "description, input_obj, expected_contains, expected_excludes",
    [
        # ---- Member ID in span input ----------------------------------------
        (
            "member_id_in_dict",
            {"member_id": "ABC123456789"},
            ["[ID]"],
            ["ABC123456789"],
        ),
        # ---- DOB in any field -----------------------------------------------
        (
            "dob_in_dict",
            {"dob": "1985-04-12"},
            ["[DOB]"],
            ["1985-04-12"],
        ),
        # ---- Phone number ----------------------------------------------------
        (
            "phone_in_text",
            {"text": "call 415-555-0123"},
            ["[PHONE]"],
            ["415-555-0123"],
        ),
        # ---- Nested dict (deep redaction) ------------------------------------
        (
            "member_id_nested",
            {"claim": {"notes": "ABC123456789"}},
            ["[ID]"],
            ["ABC123456789"],
        ),
        # ---- Non-string value passed through unchanged ----------------------
        (
            "numeric_amount_unchanged",
            {"amount": 42.50},
            [],
            [],  # just verify it doesn't raise; checked separately
        ),
        # ---- None / empty input returned as-is ------------------------------
        (
            "none_value",
            None,
            [],
            [],
        ),
        (
            "empty_dict",
            {},
            [],
            [],
        ),
        # ---- Email -----------------------------------------------------------
        (
            "email_in_string",
            "contact patient@example.com please",
            ["[EMAIL]"],
            ["patient@example.com"],
        ),
        # ---- Phone with dots -------------------------------------------------
        (
            "phone_dot_format",
            "reach me at 800.555.1234",
            ["[PHONE]"],
            ["800.555.1234"],
        ),
    ],
)
def test_redact_matrix(
    description: str,
    input_obj: object,
    expected_contains: list[str],
    expected_excludes: list[str],
) -> None:
    result = redact(input_obj)
    result_str = str(result)

    for token in expected_contains:
        assert token in result_str, (
            f"[{description}] Expected '{token}' in result: {result!r}"
        )
    for token in expected_excludes:
        assert token not in result_str, (
            f"[{description}] Expected '{token}' to be redacted from result: {result!r}"
        )


# ---------------------------------------------------------------------------
# Known-values masking (spec rows: Name, ZIP)
# ---------------------------------------------------------------------------


def test_known_name_registered() -> None:
    """Registered name is replaced with [NAME]."""
    r = fresh()
    r.register("Maria Garcia")
    result = r.redact({"reply": "Hello Maria Garcia"})
    assert "[NAME]" in str(result)
    assert "Maria Garcia" not in str(result)


def test_known_name_zip_also_redacted() -> None:
    """ZIP code in a string is redacted to [ZIP]."""
    r = fresh()
    result = r.redact({"answer": "94102"})
    assert "[ZIP]" in str(result)
    assert "94102" not in str(result)


def test_known_member_id_registered() -> None:
    """Registered member ID yields [ID], not [NAME]."""
    r = fresh()
    r.register("ABC123456789")
    result = r.redact({"reply": "Your ID is ABC123456789"})
    assert "[ID]" in str(result)
    assert "ABC123456789" not in str(result)


# ---------------------------------------------------------------------------
# Structural correctness
# ---------------------------------------------------------------------------


def test_non_string_scalar_unchanged() -> None:
    """Non-string scalars pass through unchanged."""
    assert redact(42.50) == 42.50
    assert redact(True) is True
    assert redact(0) == 0


def test_none_returned_as_is() -> None:
    assert redact(None) is None


def test_empty_dict_returned_as_is() -> None:
    assert redact({}) == {}


def test_list_redacted_recursively() -> None:
    """Lists are redacted element-by-element."""
    result = redact(["ABC123456789", 42, None])
    assert "[ID]" in result[0]
    assert result[1] == 42
    assert result[2] is None


def test_nested_dict_deep_redaction() -> None:
    """Nested dicts have all string values redacted recursively."""
    payload = {"outer": {"inner": {"member_id": "XYZ987654321"}}}
    result = redact(payload)
    inner_str = str(result["outer"]["inner"]["member_id"])
    assert "[ID]" in inner_str
    assert "XYZ987654321" not in inner_str


def test_register_empty_string_noop() -> None:
    """Registering an empty string should not cause errors."""
    r = fresh()
    r.register("")
    r.register("valid name")
    result = r.redact("valid name appears here")
    assert "[NAME]" in result
    assert "valid name" not in result


def test_multiple_phi_in_one_string() -> None:
    """Multiple PHI patterns in a single string are all redacted."""
    s = "member ABC123456789 born 1990-01-15 phone 206-555-0199"
    result = redact(s)
    assert "[ID]" in result
    assert "[DOB]" in result
    assert "[PHONE]" in result
    assert "ABC123456789" not in result
    assert "1990-01-15" not in result
    assert "206-555-0199" not in result
