"""Integration test: PHI must not appear in exported MLflow trace JSON.

Story 1.4 acceptance criterion:
  Given init_tracing() is called, when a span is created with PHI in its
  inputs, then the exported span JSON contains no member IDs, names, DOBs,
  ZIPs, or phone numbers from the seed set.

The test:
1. Spins up a temporary file-based MLflow store (no external server needed).
2. Calls init_tracing() to wire the RedactingSpanExporter.
3. Creates a span whose inputs/outputs contain a seed set of known PHI values.
4. Reads the artifacts/traces.json written to disk.
5. Asserts that none of the raw PHI strings appear in the file.

Marked ``pytest.mark.integration`` so it can be run in isolation with
    uv run pytest tests/integration/test_trace_no_phi.py -v -m integration
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import mlflow
import mlflow.tracing.provider as _mlflow_prov
import pytest

from observability.redaction import _default_redactor
from observability.tracing import init_tracing

# ---------------------------------------------------------------------------
# PHI seed set – synthetic values only (never real PHI)
# ---------------------------------------------------------------------------

SEED_MEMBER_ID = "TST000000001"  # matches [A-Z]{3}\d{9}
SEED_NAME = "Jane Testpatient"
SEED_DOB = "1980-06-15"
SEED_ZIP = "94103"
SEED_PHONE = "415-555-0101"


def _find_traces_json(mlruns_dir: str) -> Path | None:
    """Walk the mlruns directory and return the first traces.json found."""
    for root, _dirs, files in os.walk(mlruns_dir):
        for fname in files:
            if fname == "traces.json":
                return Path(root) / fname
    return None


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_no_phi_in_exported_trace(tmp_path: pytest.TempPathFactory) -> None:
    """Exported trace JSON must not contain any seed PHI strings."""
    mlruns_dir = str(tmp_path / "mlruns")
    tracking_uri = f"file://{mlruns_dir}"

    # Reset the MLflow tracer provider so init_tracing() takes effect cleanly
    _mlflow_prov._MLFLOW_TRACER_PROVIDER_INITIALIZED.done = False

    # Register known values with the process-wide default redactor
    _default_redactor.register(SEED_NAME)
    _default_redactor.register(SEED_MEMBER_ID)

    try:
        init_tracing(
            tracking_uri=tracking_uri,
            experiment="test-phi-redaction",
            git_sha="test-sha",
            app_env="test",
            llm_mode="mock",
        )

        # Create a span that deliberately contains every seed PHI value
        with mlflow.start_span("api.message") as root_span:
            root_span.set_inputs(
                {
                    "member_id": SEED_MEMBER_ID,
                    "full_name": SEED_NAME,
                    "dob": SEED_DOB,
                    "zip": SEED_ZIP,
                    "phone": SEED_PHONE,
                    "nested": {
                        "id": SEED_MEMBER_ID,
                        "info": f"Patient {SEED_NAME} born {SEED_DOB}",
                    },
                }
            )
            root_span.set_outputs({"status": "ok", "member": SEED_MEMBER_ID})

        # Allow synchronous export to complete
        time.sleep(0.2)

        # Locate the exported trace JSON
        traces_json_path = _find_traces_json(mlruns_dir)
        assert traces_json_path is not None, (
            "traces.json was not written to the MLflow store. "
            f"Searched under: {mlruns_dir}"
        )

        raw = traces_json_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        # Assert no seed PHI values appear anywhere in the serialised trace
        phi_seeds = [SEED_MEMBER_ID, SEED_NAME, SEED_DOB, SEED_ZIP, SEED_PHONE]
        for phi_value in phi_seeds:
            assert phi_value not in raw, (
                f"PHI value {phi_value!r} found in trace JSON:\n{raw}"
            )

        # Sanity check: the trace has at least one span
        assert "spans" in data, "traces.json missing 'spans' key"
        assert len(data["spans"]) >= 1, "No spans found in exported trace"

    finally:
        # Clean up: remove registered known values so other tests aren't affected
        _default_redactor._known_values.discard(SEED_NAME)
        _default_redactor._known_values.discard(SEED_MEMBER_ID)
        # Reset provider so subsequent test runs start fresh
        _mlflow_prov._MLFLOW_TRACER_PROVIDER_INITIALIZED.done = False
