---
title: 'LangGraph skeleton, state & checkpointer (Story 3.1)'
type: 'feature'
created: '2026-09-27'
status: 'in-progress'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '6d53ddf545ae40dc52181384b06de4ed01f7a9ef'
context: ['{project-root}/CLAUDE.md', '{project-root}/docs/architecture.md', '{project-root}/docs/contracts/mcp-tools.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `agent/` only has story-1.1 placeholders — `graph.py` raises `NotImplementedError`, `mcp_client.py` has no per-tool methods, `agent/nodes/` is empty. Nothing downstream (stories 3.2–3.5) can be built until the graph, state, checkpointer, and a fake MCP client actually exist.

**Approach:** Wire the full LangGraph skeleton — state, phase enum, one stub node per phase returning a canned message, and phase/intent-based conditional routing — backed by a Postgres checkpointer for cross-restart session resume, a typed async MCP client with an in-memory fake for tests, and a terminal CLI. Every later node story fills in exactly one stub.

## Boundaries & Constraints

**Always:** nodes and `mcp_client` are async end-to-end (`agent/llm.py:complete()` stays sync — call it normally from inside async nodes); stub nodes return canned messages only, no real verification/extraction/LLM calls; `fake_mcp.py` implements the same async method surface the real MCP tools will, reading from `data/seed/members.json`/`coverage.json`, so later stories swap in the real server as a drop-in; checkpointer is `AsyncPostgresSaver`, `thread_id=session_id`, tables created via `.setup()` (not Alembic).

**Never:** no real verification/extraction logic, no `mcp_tools/` server code, no `request_callback` tool (not yet in the contract — later story); no Makefile or CI changes.

**Decision:** the 3rd-failed-verification Phase value is `LOCKED` — matches `docs/architecture.md` §3.1 and `docs/contracts/mcp-tools.md` exactly as they stand today. No doc updates needed for this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal dispatch | `phase=INTAKE`, no special intent | Routes to `intake` node, canned reply | N/A |
| Cancel fast-path | any phase, message matches `cancel\|stop\|quit` | Routes to `cancelled`, ends turn, bypasses phase logic | N/A |
| Handoff fast-path | any phase, message matches `agent\|human\|representative\|person` | Routes to `handoff`, ends turn | N/A |
| Checkpoint resume | same `thread_id`, new process | All previously-set `AgentState` fields restored, nothing re-asked | Missing checkpoint → treated as a fresh session |
| Fake MCP unknown member | `fetch_coverage(member_id)` not in seed data | `{"ok": true, "data": {"snapshot_id": null, "found": false}}` | Never a differential error (no enumeration) |

</frozen-after-approval>

## Code Map

- `agent/state.py` -- all 16 `AgentState` fields and the `Phase` enum (including `LOCKED`) already correct as-is — no change needed.
- `agent/graph.py` -- stub `build_graph() -> Any: raise NotImplementedError`; rewrite to `build_graph(mcp, llm, checkpointer)` wiring router + 8 nodes per architecture §3.2.
- `agent/mcp_client.py` -- stub `MCPClient(base_url)` has only generic `call_tool`/`ping`; add 7 typed async methods (`fetch_coverage`, `start_verification`, `check_answer`, `get_policy_view`, `create_case`, `get_case`, `end_session`) per the contract doc.
- `agent/nodes/` -- currently only `__init__.py`; add one stub file per architecture §2's listed nodes: `router.py`, `intake.py`, `verify.py`, `policy.py`, `claim.py`, `clarify.py`, `confirm.py`, `handoff.py`.
- `agent/llm.py` -- reuse as-is; `complete()` confirmed sync, no wrapper needed since no node calls it with real logic yet.
- `agent/cli.py` -- new; `python -m agent.cli` interactive loop over `graph.astream`/`ainvoke`.
- `tests/fakes/fake_mcp.py` -- new; same async method surface as `MCPClient`, backed by seed JSON, in-memory attempt-tracking keyed by `verification_id`.
- `data/seed/members.json` / `coverage.json` -- read-only; confirmed fields (`member_id, dob, zip, employer_group, subscriber_name` / `plan_name, deductible{...}, oop_max{...}, copays{...}, status`).
- `tests/unit/test_graph_routing.py` -- new; table-driven phase+intent→node tests.
- `tests/integration/test_checkpoint_resume.py` -- new; resume-across-process test against compose Postgres.
- `docs/graph.mmd` -- new; committed static export of `build_graph(...).get_graph().draw_mermaid()`.
- Verified: `langgraph-checkpoint-postgres==2.0.17` exposes `AsyncPostgresSaver` at `langgraph.checkpoint.postgres.aio`; pattern is `async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as saver: await saver.setup()`.

## Tasks & Acceptance

**Execution:**
- [ ] `agent/mcp_client.py` -- add 7 typed async tool methods -- shared typed surface for nodes + fake
- [ ] `tests/fakes/fake_mcp.py` -- implement the 7 tools in-memory from seed JSON -- AC4, no real server needed for tests
- [ ] `agent/nodes/{router,intake,verify,policy,claim,clarify,confirm,handoff}.py` -- stub nodes, canned messages, `mcp`/`llm` injected -- AC2
- [ ] `agent/graph.py` -- `build_graph(mcp, llm, checkpointer)`, conditional edges per architecture §3.2 -- AC2
- [ ] `agent/cli.py` -- interactive terminal chat -- AC5
- [ ] Checkpointer wiring (`AsyncPostgresSaver`, `thread_id=session_id`) -- AC3
- [ ] `docs/graph.mmd` -- export via `draw_mermaid()`, commit -- AC6
- [ ] `tests/unit/test_graph_routing.py` -- table-driven routing tests -- Dev Notes testing requirement
- [ ] `tests/integration/test_checkpoint_resume.py` -- resume test -- Dev Notes testing requirement
- [ ] `docs/stories/3.1.langgraph-skeleton-state-checkpointer.md` -- tick tasks, Dev Agent Record, File List, Change Log

**Acceptance Criteria:**
- Given a fresh session with no checkpoint, when invoked with `phase=INTAKE`, then it routes to `intake` and returns a canned message without calling any MCP tool.
- Given any phase, when the message matches the cancel/handoff regex fast-path, then the graph ends the turn at `cancelled`/`handoff` regardless of phase.
- Given a `session_id` with prior checkpointed state, when the process restarts and the graph is invoked again with the same `thread_id`, then all previously-set fields are restored.
- Given `python -m agent.cli` run with `LLM_MODE=mock`, when a message is typed, then a reply prints with no network/AWS calls.

## Implementation Notes

## Design Notes

**Turn boundary:** use plain graph `END`, not LangGraph's `interrupt()` primitive. Architecture allows either; this repo's API shape is one `POST /sessions/{id}/messages` call per user message (architecture §8), so "end of turn" is simply the graph finishing its `ainvoke` — the next user message is a fresh invocation with the same `thread_id`, and the checkpointer restores state. `interrupt()` is for pausing *mid*-execution for human input inside one invocation, which this API shape doesn't need.

## Verification

**Commands:**
- `uv run pytest tests/unit/test_graph_routing.py -v` -- expect all routing cases pass
- `uv run pytest tests/integration -v -m integration` -- expect checkpoint resume test passes (needs `make up` postgres running)
- `LLM_MODE=mock uv run python -m agent.cli` -- expect interactive prompt accepts input, prints a reply
- `make lint` -- expect clean
- `make eval` -- expect stays green (no new scenarios)

**Manual checks (if no CLI):**
- Open `docs/graph.mmd` in a Mermaid viewer and confirm it matches the architecture §3.2 shape.
