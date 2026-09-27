# Test Strategy

## Pyramid

| Level | Location | Tools | What | Runs |
|---|---|---|---|---|
| Unit | `tests/unit/` | pytest, pytest-asyncio | Pure functions: matchers, normalizers, redaction, routing tables, node logic with fakes | every PR |
| Contract | `tests/contracts/` | pytest + jsonschema | Each MCP tool response matches `docs/contracts/mcp-tools.md`. Runs against **both** the real FastMCP server (in-memory client) and `tests/fakes/fake_mcp.py` | every PR |
| Integration | `tests/integration/` (`-m integration`) | pytest, Postgres service | DB migrations, seed, tools against real DB, checkpoint resume, API via TestClient, trace PHI scan | every PR |
| Conversation evals | `evals/` | runner + scorers | Multi-turn scenarios (see eval-plan.md) | every PR (mock), nightly (Bedrock) |
| E2E / UI smoke | `tests/e2e/` | Playwright (Chromium) | Browser happy path against compose stack | PRs touching `api/static` + nightly |
| Deploy smoke | `scripts/smoke_e2e.py` | httpx | Happy path against the deployed URL | after each deploy |

## Rules

1. **No network in unit tests.** LLM calls use `LLM_MODE=mock`, and MCP uses the fake or an in-memory FastMCP client.
2. **One fixture home:** `tests/conftest.py` provides `mock_llm`, `fake_mcp`, `db_session`, `graph` and `seed_personas`.
3. **Table-driven tests** for matchers, normalizers, intents and routing.
4. **Safety invariant tests** (must never be deleted, only extended):
   - `test_policy_gate_blocks_unverified`
   - `test_create_case_requires_passed_verification` (tool level)
   - `test_no_case_without_confirm_intent` (graph level)
   - `test_prompts_never_contain_expected_answers`
   - `test_trace_no_phi`
5. **Coverage:** at least 80% on `mcp_tools/` and `agent/nodes/`. This is reported in CI but not enforced until story 6.2.
6. **Bug fixes:** every bug fix adds a failing test first, plus an eval scenario if the bug was conversational.

## Commands

```bash
make test                 # unit + contract
make test-int             # integration (needs docker compose up postgres)
make eval                 # conversation evals, mock
pytest -k verify -vv      # focus
```

## Reviewer QA checklist (fill in "QA Results" in the story)

- [ ] Every AC has a test or eval that covers it (list them)
- [ ] Negative paths tested
- [ ] No PHI in logs or traces (redaction test green)
- [ ] Contract unchanged, or version bumped with both devs' approval
- [ ] Trace screenshot / ID attached
- [ ] Verdict: PASS / CONCERNS (non-blocking follow-ups filed) / FAIL
