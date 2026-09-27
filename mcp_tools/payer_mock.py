"""Mock payer eligibility client.

Implements the ``PayerClient`` protocol backed by ``data/seed/coverage.json``.
Story 2.3 (``fetch_coverage`` tool) uses this as its payer layer.

``RealPayerClient`` is a stub documenting the X12 270/271 mapping for when
a clearinghouse integration replaces the mock.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from pathlib import Path
from typing import Protocol, runtime_checkable

from observability import tracing

_DEFAULT_SEED_PATH = Path(__file__).parent.parent / "data" / "seed" / "coverage.json"


class PayerUnavailable(Exception):
    """Raised when the payer service times out or injects a failure."""


@runtime_checkable
class PayerClient(Protocol):
    """Protocol satisfied by both MockPayerClient and RealPayerClient."""

    async def get_eligibility(self, member_id: str) -> dict | None:
        """Return coverage dict for *member_id*, or ``None`` if not found.

        Raises ``PayerUnavailable`` on timeout or service error.
        """
        ...


class MockPayerClient:
    """In-process mock that reads ``data/seed/coverage.json`` at startup.

    Environment variables:
      ``PAYER_MOCK_LATENCY_MS``  — simulated round-trip latency (default 0).
      ``PAYER_MOCK_FAIL_RATE``   — probability [0.0, 1.0] of injected failure (default 0).
    """

    def __init__(self, seed_path: str | Path = _DEFAULT_SEED_PATH) -> None:
        raw = Path(seed_path).read_text(encoding="utf-8")
        records: list[dict] = json.loads(raw)
        self._index: dict[str, dict] = {r["member_id"]: r for r in records}

    async def get_eligibility(self, member_id: str) -> dict | None:
        # PHI invariant: member_id must never appear in log lines, span attrs,
        # or exception messages. The exporter-level redactor is a safety net, not a
        # substitute for keeping it out of all text payloads here.
        try:
            latency_ms = float(os.environ.get("PAYER_MOCK_LATENCY_MS", "0"))
        except ValueError:
            latency_ms = 0.0
        try:
            fail_rate = float(os.environ.get("PAYER_MOCK_FAIL_RATE", "0"))
        except ValueError:
            fail_rate = 0.0

        result = self._index.get(member_id)
        with tracing.span("payer.get_eligibility", found=result is not None, latency_ms=latency_ms):
            if latency_ms > 0:
                await asyncio.sleep(latency_ms / 1000)
            if fail_rate > 0 and random.random() < fail_rate:
                raise PayerUnavailable("injected failure")
            return result


class RealPayerClient:
    """Stub for a future clearinghouse integration — not implemented.

    X12 270 outbound (subscriber eligibility inquiry):
      ISA/GS/ST envelope → NM1*IL loop (subscriber name/ID) →
      DTP*291 (eligibility date) → EQ*30 (medical service type code).

    X12 271 inbound (eligibility response) field mapping:
      EB*1 (active coverage)        → ``status = "active"``
      EB*C*30 (deductible)          → ``deductible.individual / met / remaining``
      EB*G*30 (out-of-pocket max)   → ``oop_max.individual / met / remaining``
      EB*B*30 (copay by POS code)   → ``copays.{pcp,specialist,urgent_care,er}``
      DTP*291 (coverage period)     → ``coverage_period.start / end``

    Replace this stub with an SFTP/API client pointing to your clearinghouse.
    """

    async def get_eligibility(self, member_id: str) -> dict | None:
        raise NotImplementedError("RealPayerClient is not implemented")
