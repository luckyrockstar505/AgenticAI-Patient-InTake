# Epic 3 Context: Identity & Policy Flow

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Build the LangGraph flow that captures a member's identity, verifies it deterministically (never by LLM judgment), and reveals policy details only after verification succeeds. This is Track A's (Bharath's) critical-path epic: it stands up the graph skeleton and state model every later agent story builds on, and it implements the two highest-stakes safety invariants in the whole system — no policy before verification, and a graceful callback path (not a dead-end lockout) when verification fails three times.

## Stories

- Story 3.1: LangGraph skeleton, state & checkpointer
- Story 3.2: Phase-based stub router — ✅ Done, delivered inside 3.1 (`agent/nodes/router.py`); full intent classification deferred, see `deferred-work.md`
- Story 3.3: Intake node (member ID + name)
- Story 3.4: Verify node — challenge loop & PENDING_CALLBACK
- Story 3.5: Policy display node (verified gate)

## Requirements & Constraints

- Member ID + full name accepted via free text in one or two turns; member ID format `^[A-Z]{3}\d{9}$`, validated before any fetch.
- Unknown member ID and a known-but-mismatched member ID must produce **identical** responses — no enumeration, no hint that an ID does or doesn't exist. Member ID is echoed back masked (first 3 chars + `****`, e.g. `ABC•••••6789`).
- Verification challenge: DOB plus one of ZIP / employer name / subscriber ID. Pass/fail is decided entirely by the deterministic `check_answer` tool — the LLM never sees expected answers and never decides pass/fail.
- After 3 consecutive failed attempts: **not** a hard lockout. Collect a callback contact number, call `request_callback`, set `state.phase = PENDING_CALLBACK`, tell the member: "I wasn't able to verify your identity. Leave me a number and our team will call you back." Session ends — no policy shown, no case created.
- Policy data (`policy_view`) may be written only by the policy node, and only when `state.verified is True`. All rendered values (plan name, effective dates, deductible met/remaining, OOP max met/remaining, copays) come from `get_policy_view` output — never LLM-generated text or numbers.
- If the policy node is ever entered with `state.verified is False`, raise a `VerificationInvariantError` and route to handoff (fail closed, not silently).
- Member may cancel or request a human from any phase/turn — this must not depend on full intent classification; a stub, phase-based router with regex fast-paths is sufficient for this epic.
- No case is created and no policy is exposed for any session that hasn't passed verification (hard eval gate, 0 tolerance).
- Session must resume from checkpoint without re-asking for information already collected.
- Every tool call in this epic (`fetch_coverage`, `start_verification`, `check_answer`, `get_policy_view`, `request_callback`) writes an audit log entry; expected answers, DOBs, and full member IDs must never appear in prompts, messages, logs, or traces.

## Technical Decisions

- **State** (`agent/state.py`): `AgentState` is a `TypedDict` carrying `session_id`, `messages`, `phase`, `member_id`, `full_name`, `snapshot_id` (never raw coverage payload before verify), `verification_id`, `verified: bool`, `failed_attempts`, `pending_question_id`, `policy_view: dict | None`, `claim`, `missing_fields`, `clarify_turns`, `last_intent`, `case_number`.
- **Phase enum**: `INTAKE, VERIFY, POLICY, CLAIM, CLARIFY, CONFIRM, DONE, PENDING_CALLBACK, HANDOFF, CANCELLED`. `PENDING_CALLBACK` replaces the `LOCKED` phase named in the architecture doc — this is a party-mode decision (A-1) that postdates the architecture doc's `Phase` listing, so implement `PENDING_CALLBACK`, not `LOCKED`.
- **Graph shape**: `START → router` dispatches by intent first (cancel/handoff override any phase), then by `state.phase`. Flow: `intake → fetch_coverage → verify` (loop on fail with attempts remaining; on 3rd fail → `PENDING_CALLBACK` → END) `→ policy → claim_extract → ...` (claim/confirm nodes are Epic 4's concern, out of scope here except as the hand-off point).
- Nodes that need user input end the turn (return an AI message, halt via checkpoint) and resume on the next message with the same `thread_id = session_id`.
- **Checkpointer**: `PostgresSaver` (`langgraph-checkpoint-postgres`), `thread_id = session_id`, tables created by `PostgresSaver.setup()` — not Alembic.
- **Nodes call tools directly** (deterministic control flow) via `agent/mcp_client.py`; the LLM does not choose tools in this demo. Nodes receive `mcp` and `llm` by dependency injection.
- Relevant MCP tool contracts (`docs/contracts/mcp-tools.md`), all taking `session_id` and writing audit rows:
  - `fetch_coverage(session_id, member_id)` → `{snapshot_id, found}`; unknown ID returns `found: false` with a null snapshot, not an error — payload itself is never returned to the agent.
  - `start_verification(session_id, member_id, full_name)` → `{verification_id, name_match, next_question: {id, prompt_hint}}`. `prompt_hint` is one of `date_of_birth | zip_code | employer_group | subscriber_name`; the node turns it into natural wording. A name mismatch still returns a `next_question` (no enumeration) but counts as a failed attempt.
  - `check_answer(session_id, verification_id, question_id, answer)` → `{status: PENDING|PASSED|FAILED|LOCKED, attempts, remaining_attempts, next_question}`. Any wrong answer increments attempts; at `MAX_VERIFY_ATTEMPTS` (env, default 3) status is `LOCKED` server-side.
  - `get_policy_view(session_id, verification_id)` → policy fields only when verification `PASSED`, else `NOT_VERIFIED` error.
  - `request_callback` — referenced by the epics/story docs for the PENDING_CALLBACK flow but **not yet present** in `docs/contracts/mcp-tools.md` (see Cross-Story Dependencies).
- **Intent routing** (`docs/intents.md`, full classifier is a later story — 3.2 ships only a phase-based stub): regex fast-paths run before any LLM call — `cancel|stop|quit` → cancel, `agent|human|representative|person` → request_human, member-ID regex → provide_identity. Allowed intents per phase: `intake` defaults to `provide_identity`; `verify` defaults to `answer_challenge`; `policy` defaults to `acknowledge`. Persona/tone: warm, concise, one question per turn, ≤ ~60 words, never reveal whether a member ID exists, never read back DOB or full member ID.
- Data model touched by this epic: `coverage_snapshots` (status `unverified` → `verified`), `verifications` (status `PENDING|PASSED|FAILED|LOCKED`, `attempts`, `asked_question_ids`), `audit_log`.

## Cross-Story Dependencies

- 3.1 depends on Story 1.3 (LLM gateway) and 2.1 (DB schema/checkpointer tables); it must land before 3.2–3.5 since every later node fills in a stub the skeleton wires.
- 3.2 (stub router) blocks 3.3, 3.4, 3.5 — must not be deferred even though it's small.
- 3.3 depends on 2.3 (coverage MCP tools); 3.4 depends on 2.4 (verification MCP tools); 3.5 depends on 2.3 (`get_policy_view`).
- Epic 4 (Claim Intake & Case) begins at the exit point of 3.5 (`Phase.POLICY → CLAIM`).
- **Known gap:** `docs/contracts/mcp-tools.md` (v1, dated 2026-09-27) has not been updated for the A-1 PENDING_CALLBACK decision — it still documents verification `LOCKED` status and an `end_session` reason of `handoff_locked`, and has no `request_callback` tool entry at all (Story 2.5 in the epics file adds `request_callback`, writing to a `callbacks` table, but the contract doc doesn't reflect it yet). Per repo rules, the contract file is the seam of record and must be updated first via a reviewed PR before or alongside Story 3.4/2.4/2.5 work — don't silently code against one version while the doc says another.
