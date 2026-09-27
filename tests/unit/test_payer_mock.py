"""Unit tests for mcp_tools/payer_mock.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_tools.payer_mock import MockPayerClient, PayerClient, PayerUnavailable, RealPayerClient

_SEED = [
    {
        "member_id": "TST000000001",
        "plan_name": "Test Plan Gold",
        "plan_type": "PPO",
        "status": "active",
        "deductible": {"individual": 1000, "met": 0, "remaining": 1000},
        "oop_max": {"individual": 5000, "met": 0, "remaining": 5000},
        "copays": {"pcp": 10, "specialist": 20, "urgent_care": 30, "er": 100},
        "coinsurance_pct": 20,
    }
]


@pytest.fixture
def seed_path(tmp_path: Path) -> Path:
    p = tmp_path / "coverage.json"
    p.write_text(json.dumps(_SEED), encoding="utf-8")
    return p


async def test_found_member_returns_coverage_dict(seed_path: Path) -> None:
    client = MockPayerClient(seed_path=seed_path)
    result = await client.get_eligibility("TST000000001")
    assert result is not None
    assert result["plan_name"] == "Test Plan Gold"
    assert "deductible" in result
    assert "copays" in result


async def test_unknown_member_returns_none(seed_path: Path) -> None:
    client = MockPayerClient(seed_path=seed_path)
    result = await client.get_eligibility("ZZZ999999999")
    assert result is None


async def test_injected_failure_raises_payer_unavailable(
    seed_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAYER_MOCK_FAIL_RATE", "1.0")
    client = MockPayerClient(seed_path=seed_path)
    with pytest.raises(PayerUnavailable, match="injected failure"):
        await client.get_eligibility("TST000000001")


async def test_latency_injection_still_returns_result(
    seed_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAYER_MOCK_LATENCY_MS", "10")
    client = MockPayerClient(seed_path=seed_path)
    result = await client.get_eligibility("TST000000001")
    assert result is not None


async def test_malformed_env_vars_fall_back_to_defaults(
    seed_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAYER_MOCK_LATENCY_MS", "fast")
    monkeypatch.setenv("PAYER_MOCK_FAIL_RATE", "never")
    client = MockPayerClient(seed_path=seed_path)
    result = await client.get_eligibility("TST000000001")
    assert result is not None


def test_mock_payer_satisfies_protocol(seed_path: Path) -> None:
    # runtime_checkable verifies method existence only, not async signature.
    # Sufficient for isinstance() guards in calling code.
    assert isinstance(MockPayerClient(seed_path=seed_path), PayerClient)


def test_real_payer_satisfies_protocol() -> None:
    # Same caveat: checks method existence only.
    assert isinstance(RealPayerClient(), PayerClient)
