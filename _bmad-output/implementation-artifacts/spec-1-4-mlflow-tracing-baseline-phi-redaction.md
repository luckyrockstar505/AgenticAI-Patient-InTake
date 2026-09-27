---
title: 'MLflow tracing baseline & PHI redaction'
type: 'feature'
created: '2026-09-27'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'fe539920da4e7ff10027ab9a387eaef8ed44164e'
context:
  - docs/tracing.md
  - docs/architecture.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The observability stubs from story 1.1 are no-ops — no traces reach MLflow and PHI flows unmasked through logs and spans. Every later story that adds LLM or MCP calls depends on this foundation being real.

**Approach:** Implement `init_tracing()` with MLflow 3.x GenAI autolog, implement the PHI redactor with regex + known-values masking, wire the redactor as an MLflow span filter and logging formatter, and prove zero PHI leaks with a unit test table and an integration test that scans exported trace JSON.

## Boundaries & Constraints

**Always:**
- MLflow 3.1.0 (installed). Use `mlflow.start_span`, `@mlflow.trace`, `mlflow.langchain.autolog()`, `mlflow.litellm.autolog()` — verify exact API against the installed package before implementing.
- Trace-level tags: `session_id`, `app_env`, `git_sha`, `llm_mode` (from env). Tag names from `docs/tracing.md §3`.
- PHI masking happens at the span processor/exporter level — not inline in business logic. Redactor must intercept all spans regardless of how they were created.
- Known-values masking: `Redactor` holds a per-session set of strings (name, member_id) registered at runtime via `redactor.register(value)`. These are masked as `[NAME]` / `[ID]`.
- `make eval` must stay green (no new eval scenarios).
- `make lint` must stay clean after this story.

**Never:**
- Do not add PHI masking inside individual node or tool functions — the span processor is the single choke point.
- Do not break the `tracing.span()` context manager signature — later stories call it.
- Do not write PHI strings to disk (test fixtures must use fake/synthetic values only).

## I/O & Edge-Case Matrix

| Scenario | Input | Expected Behavior |
|---|---|---|
| Member ID in span input | `{"member_id": "ABC123456789"}` | Replaced with `ABC•••••789` or `[ID]` |
| Name in span output | `{"reply": "Hello Maria Garcia"}` | `[NAME]` if `"Maria Garcia"` was registered |
| DOB in any field | `{"dob": "1985-04-12"}` | `[DOB]` |
| ZIP in verify phase | `{"answer": "94102"}` | `[ZIP]` |
| Phone number | `{"text": "call 415-555-0123"}` | `[PHONE]` |
| Nested dict | `{"claim": {"notes": "ABC123456789"}}` | Deep-redacted recursively |
| Non-string value | `{"amount": 42.50}` | Passed through unchanged |
| Empty / None | `None` or `{}` | Returned as-is |

</frozen-after-approval>

## Code Map

- `observability/tracing.py` — replace stub with real `init_tracing()` + `span()` + `RedactingSpanProcessor`
- `observability/redaction.py` — replace stub with `Redactor` class (regex + known-values), `redact()` module-level function using a default instance
- `tests/unit/test_redaction.py` — NEW: table-driven tests for every I/O matrix row
- `tests/integration/test_trace_no_phi.py` — NEW: run a minimal mock turn, export trace JSON, assert zero seed PHI strings appear
- `api/main.py` — call `init_tracing()` at startup (currently does not)
- `pyproject.toml` — check `asyncio_default_fixture_loop_scope` warning; add `asyncio_mode = "auto"` and `asyncio_default_fixture_loop_scope = "function"` to `[tool.pytest.ini_options]` to silence the pytest-asyncio deprecation warning seen in 1.1 tests

**Do not touch:** `agent/`, `mcp_tools/`, `shared/` — not part of this story.

## Tasks & Acceptance

**Execution:**
- [x] `observability/redaction.py` — implement `Redactor` class: compile regex patterns (member ID, name-list, DOB, ZIP, phone, email, NPI), `register(value)` for known-values, `redact(obj)` handles str/dict/list recursively
- [x] `observability/tracing.py` — implement `init_tracing(tracking_uri, experiment, git_sha, app_env, llm_mode)`: set MLflow tracking URI + experiment, call `mlflow.langchain.autolog()` + `mlflow.litellm.autolog()`, register `RedactingSpanProcessor` that calls `redact()` on span inputs/outputs before export
- [x] `observability/tracing.py` — add `RedactingFormatter` for Python `logging` that calls `redact()` on log record messages
- [x] `api/main.py` — call `init_tracing()` at app startup using env vars (`MLFLOW_TRACKING_URI`, `MLFLOW_EXPERIMENT`, `GIT_SHA`, `APP_ENV`, `LLM_MODE`)
- [x] `tests/unit/test_redaction.py` — table-driven tests covering every I/O matrix row; must all pass with no live MLflow server
- [x] `tests/integration/test_trace_no_phi.py` — in-memory MLflow (sqlite), run a mock agent turn that logs a span with seed PHI strings, export trace JSON, assert no PHI appears; mark with `pytest.mark.integration`
- [x] `pyproject.toml` — add `asyncio_default_fixture_loop_scope = "function"` to silence pytest-asyncio deprecation

**Acceptance Criteria:**
- Given `init_tracing()` is called, when a span is created with PHI in its inputs, then the exported span JSON contains no member IDs, names, DOBs, ZIPs, or phone numbers from the seed set
- Given `redact({"member_id": "ABC123456789"})` is called, then the member ID pattern is masked
- Given a name `"Maria Garcia"` is registered, when it appears in any span attribute, then it is replaced with `[NAME]`
- Given `make test` runs, then all unit and integration-marked tests pass
- Given `make lint` runs, then ruff and mypy both pass with 0 errors

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `uv run pytest tests/unit/test_redaction.py -v` -- expected: all rows pass
- `uv run pytest tests/integration/test_trace_no_phi.py -v` -- expected: zero PHI in trace JSON
- `uv run pytest tests/unit -v` -- expected: all unit tests pass (including 1.1 health tests)
- `uv run ruff check . && uv run mypy . --ignore-missing-imports` -- expected: 0 errors
