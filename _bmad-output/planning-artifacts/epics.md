---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories", "step-04-final-validation"]
status: ready-for-development
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-AgenticAI-Patient-InTake-2026-09-27/prd.md
  - docs/architecture.md
  - docs/contracts/mcp-tools.md
  - docs/intents.md
  - docs/tracing.md
  - docs/qa/eval-plan.md
project: AgenticAI-Patient-InTake
created: 2026-09-27
updated: 2026-09-27
developers:
  trackA: Bharath   # Agent track: LangGraph, conversation nodes, verification, claim intake
  trackB: Srimaan   # Platform track: MCP tools, FastAPI, DB, CI/CD, deploy
---

# Claims Intake Agent — Epic Breakdown

> Source: PRD v1.0 (2026-09-27) + Architecture v1.0 + party-mode decisions (A-1 → A-4)
> Developers: **Bharath** (Track A — Agent) · **Srimaan** (Track B — Platform)
> Deploy target: **AWS AgentCore** (Bedrock AgentCore Runtime) — replaces ECS Fargate + Terraform

---

## Developer Tracks

| Developer | Track | Focus areas |
|---|---|---|
| **Bharath** | A — Agent | `agent/` — LangGraph graph, state machine, conversation nodes, prompts, LLM gateway, intent classifier |
| **Srimaan** | B — Platform | `mcp_tools/`, `api/`, `shared/`, `evals/`, `infra/`, CI/CD, Docker, DB, AgentCore deploy |

---

## Requirements Inventory

### Functional Requirements (from PRD + party-mode decisions)

```
FR-1.1: Accept member ID (9-digit alphanumeric) and full name via text input
FR-1.2: Validate member ID format before any fetch; reject with plain-language message; no hint whether ID exists

FR-2.1: Call fetch_coverage MCP tool; store snapshot with status=unverified
FR-2.2: Never expose policy data until verification status=verified
FR-2.3: If payer tool returns no record, same behaviour as verification failure (no differential error)

FR-3.1: Challenge with date of birth + one of: ZIP code, employer name, subscriber ID
FR-3.2: Evaluate each answer via verify_answer deterministic tool; LLM never makes pass/fail decision
FR-3.3: [UPDATED A-1] After 3 failures: collect callback contact number via request_callback tool,
         write to callbacks queue (member_id, session_id, contact_number), state=PENDING_CALLBACK;
         message: "I wasn't able to verify your identity. Leave me a number and our team will call you back."
FR-3.4: Never hint which answer was wrong or whether member ID exists

FR-4.1: After verified=True: display plan name, effective dates, deductible (met/remaining),
         OOP max (met/remaining), relevant copays
FR-4.2: All values rendered from coverage snapshot — no LLM-generated policy text

FR-5.1: Accept free-text claim description; extract structured fields:
         date_of_service, place_of_service, provider_name, diagnosis_reason (required);
         provider_npi, amounts, accident_related, other_insurance (optional)
FR-5.2: [UPDATED A-3] Ask targeted clarification per missing required field; if still missing,
         proceed and create case with missing_fields[] flag and complete=False; member informed
         ops will follow up; no hard turn limit
FR-5.3: Never ask for a field the member already provided in the same session
FR-5.4: [CONFIRMED A-4] Required: date_of_service, place_of_service, provider_name, diagnosis_reason,
         patient_name (when patient≠subscriber). Optional: amounts, npi, accident_related, other_insurance
FR-5.5: [ADDED A-2] Subscriber may file on behalf of minor dependents; patient_name required when
         patient≠subscriber; adult dependent authorization is OUT OF SCOPE

FR-6.1: Present complete structured summary before case creation
FR-6.2: Create case only after explicit member confirmation
FR-6.3: Return case_number and status=NEW; create_case tool owns creation decision (not LLM)
FR-6.4: Write audit log entry per session: member_id (hashed), verification outcome, case_id or null

FR-7.1: Offer cancel at any turn; confirm before discarding; no case created on cancel
FR-7.2: Offer human handoff at any turn (member-initiated)
FR-7.3: Resume checkpointed session without re-asking fields already collected

FR-8.1: Trace every agent turn to MLflow; mask PHI at span exporter
FR-8.2: Golden dataset: eval/labelled_claims.csv — 20+ human-labelled rows (build set) +
         10-row holdout; columns: input, expected_answer, expected_tools, why
FR-8.3: CI gate: deterministic code checks on every push; no model calls in CI
FR-8.4: Export eval run to results.json (decision, code-check, judge score, token counts)

FR-9: [ADDED A-1] Human handoff experience: on PENDING_CALLBACK, agent displays callback
       confirmation message + reference; request_callback tool writes to callbacks table;
       member does not need to repeat member_id to the human agent
```

### Non-Functional Requirements

```
NFR-1: p95 agent turn latency ≤ 4s (text, streaming)
NFR-2: Hard gates (100% enforced by eval):
         0 cases created for unverified sessions
         0 policy data shown before verification
         0 PHI in logs or traces
NFR-3: Synthetic data only; no real PHI in demo environment
NFR-4: LiteLLM over AWS Bedrock Claude; mock mode for CI (no real model calls)
NFR-5: 2 developers (Bharath — Track A, Srimaan — Track B); deploy via AWS AgentCore
NFR-6: Concurrent sessions: ≥ 5 simultaneous without degradation (workshop demo safety)
```

### Additional Requirements (Architecture)

```
- LangGraph state machine phases: INTAKE, VERIFY, POLICY, CLAIM, CLARIFY, CONFIRM,
  DONE, PENDING_CALLBACK (replaces LOCKED per A-1), HANDOFF, CANCELLED
- Postgres checkpointer (PostgresSaver) for session resume (or AgentCore Memory)
- FastMCP server on :8765/mcp, streamable-http transport
- PHI redaction in observability/redaction.py applied before MLflow spans and logs
- MCP contracts in docs/contracts/mcp-tools.md are source of truth (version-locked)
- Deploy: AWS AgentCore Runtime (not ECS Fargate + Terraform) — single command deploy
- AgentCore Memory: evaluate as replacement for Postgres checkpointer in cloud deploy
- LangGraph checkpoint tables created by PostgresSaver.setup(), NOT by Alembic
- Payer mock reads from data/seed/coverage.json; members seeded from data/seed/members.json
- ClaimDraft in shared/schemas.py is the canonical claim schema (both tracks import it)
- Two-track GitHub workflow: CODEOWNERS, contracts-first, no direct push to main
```

### UX Design Requirements

```
UX-DR1: Chat UI renders streaming SSE tokens as they arrive (typing effect)
UX-DR2: Structured summary before confirmation displayed as a readable formatted block
UX-DR3: Policy display uses clear labels: "Deductible: $X met of $Y" not raw JSON
UX-DR4: Callback confirmation message includes a reference number the member can quote
UX-DR5: Error/lockout messages use plain language; no technical jargon exposed to member
```

---

## FR Coverage Map

| FR | Epic | Story |
|---|---|---|
| FR-1.1, FR-1.2 | E3 | 3.3 |
| FR-2.1, FR-2.2, FR-2.3 | E2 | 2.3 |
| FR-3.1–FR-3.4, FR-9 | E3 | 3.4 |
| FR-4.1, FR-4.2 | E3 | 3.5 |
| FR-5.1–FR-5.5 | E4 | 4.1, 4.2 |
| FR-6.1–FR-6.4 | E4 | 4.3 |
| FR-7.1, FR-7.2 | E4 | 4.4 |
| FR-7.3 | E3 | 3.1 |
| FR-8.1 | E1 | 1.4 |
| FR-8.2–FR-8.4 | E6 | 6.1 |
| NFR-1, NFR-2 | E6 | 6.2, 6.3 |

---

## Epic List

| # | Epic | Track | Owner | Sprint | Workshop critical path |
|---|---|---|---|---|---|
| E1 | Foundation & DevEx | B | **Srimaan** | 1 | ⚡ Stories 1.1, 1.3, 1.4 |
| E2 | Data & MCP Tools | B | **Srimaan** | 1–2 | ⚡ Stories 2.1–2.5 |
| E3 | Identity & Policy Flow | A | **Bharath** | 2 | ⚡ Stories 3.1, 3.4, 3.5 |
| E4 | Claim Intake & Case | A | **Bharath** | 2–3 | ⚡ Stories 4.1, 4.3, 4.4 |
| E5 | API & Chat UI | B | **Srimaan** | 3 | ⚡ Story 5.1 |
| E6 | Evals & Quality | Both | **Both** | 3 | ⚡ Story 6.1 |
| E7 | Deploy & Demo | B | **Srimaan** | 4 | ⚡ Story 7.1 (AgentCore) |
| E8 | Voice (stretch) | A | **Bharath** | 5 | — post-workshop |
| E9 | Presentation & Demo | Both | **Both** | 4 | ⚡ All 3 stories |

> ⚡ = workshop critical path (build these first in the 2.5hr window)

---

## Epic 1: Foundation & DevEx

**Track:** B — **Owner: Srimaan**
**Goal:** Stand up the repo, local stack, CI, LLM gateway and tracing so both tracks can build in parallel from day one.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| [1.1](../../docs/stories/1.1.repo-scaffold-local-docker-stack.md) | Repo scaffold & local docker stack | **Srimaan** | Bharath | — | M | ⚡ |
| [1.2](../../docs/stories/1.2.ci-pipeline-lint-type-test-build.md) | CI pipeline (lint, type, test, build) | **Srimaan** | Bharath | 1.1 | S | defer |
| [1.3](../../docs/stories/1.3.llm-gateway-via-litellm-bedrock-mock.md) | LLM gateway via LiteLLM (Bedrock + mock) | **Bharath** | Srimaan | 1.1 | S | ⚡ |
| [1.4](../../docs/stories/1.4.mlflow-tracing-baseline-phi-redaction.md) | MLflow tracing baseline & PHI redaction | **Srimaan** | Bharath | 1.1 | M | ⚡ |

### Epic 1 done when
- `make test` green on main · Docker stack up with `make up` · LLM mock returns scripted responses · MLflow traces visible with PHI masked

---

## Epic 2: Data & MCP Tools

**Track:** B — **Owner: Srimaan**
**Goal:** DB schema, synthetic members, mock payer service, and FastMCP tool server implementing `docs/contracts/mcp-tools.md`.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| 2.0 | **Golden dataset** (`eval/labelled_claims.csv` — 20 build + 10 holdout rows) | **Both** | Both | 1.1 | S | ⚡ |
| [2.1](../../docs/stories/2.1.db-schema-migrations-synthetic-seed.md) | DB schema, migrations & synthetic seed | **Srimaan** | Bharath | 2.0 | M | ⚡ |
| [2.2](../../docs/stories/2.2.mock-payer-eligibility-service.md) | Mock payer eligibility service | **Srimaan** | Bharath | 2.1 | S | ⚡ |
| [2.3](../../docs/stories/2.3.fastmcp-coverage-tools.md) | FastMCP coverage tools | **Srimaan** | Bharath | 2.2 | M | ⚡ |
| [2.4](../../docs/stories/2.4.fastmcp-verification-tools.md) | FastMCP verification tools | **Srimaan** | Bharath | 2.3 | M | ⚡ |
| [2.5](../../docs/stories/2.5.fastmcp-case-tools.md) | FastMCP case & callback tools | **Srimaan** | Bharath | 2.1 | S | ⚡ |

> **2.0 (NEW — party mode fix):** golden dataset created HERE, not in E6. Human-labelled by Srimaan + Bharath before any agent code runs. Columns: `input`, `expected_answer`, `expected_tools`, `why`. Must cover: happy path, PENDING_CALLBACK, partial case, minor dependent, no-repeat-questions, cancel. Never generated by the agent.
> **2.5 updated:** add `request_callback` tool (writes to callbacks table) per A-1 decision.

### Epic 2 done when
- `make seed` loads 7 personas idempotently · All MCP tools pass contract tests · `make eval` green

---

## Epic 3: Identity & Policy Flow

**Track:** A — **Owner: Bharath**
**Goal:** LangGraph skeleton, intent router, member intake node, verification node (callback flow), and policy display node.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| [3.1](../../docs/stories/3.1.langgraph-skeleton-state-checkpointer.md) | LangGraph skeleton, state & checkpointer | **Bharath** | Srimaan | 1.3, 2.1 | M | ⚡ |
| [3.2](../../docs/stories/3.2.intent-classifier-global-router.md) | Phase-based stub router (intent classifier enhancement later) | **Bharath** | Srimaan | 3.1 | S | ⚡ |
| [3.3](../../docs/stories/3.3.intake-node-member-id-name.md) | Intake node (member ID + name) | **Bharath** | Srimaan | 3.1 | S | ⚡ |
| [3.4](../../docs/stories/3.4.verify-node-challenge-loop-lockout.md) | Verify node — challenge loop & callback | **Bharath** | Srimaan | 3.3, 2.4 | M | ⚡ |
| [3.5](../../docs/stories/3.5.policy-display-node-verified-gate.md) | Policy display node (verified gate) | **Bharath** | Srimaan | 3.4, 2.3 | S | ⚡ |

> **3.2 updated (party mode fix):** stub router (routes by `state.phase`) ships with E3 to unblock 3.3, 3.4, 3.5. Full intent classification (cancel/handoff/edit detection) is a follow-up story within E3. Do NOT defer 3.2 — it is required for the graph to dispatch.
> **3.4 updated (A-1):** verification failure after 3 attempts → `PENDING_CALLBACK` state, calls `request_callback` tool, NOT hard lock. State enum: rename `LOCKED` → `PENDING_CALLBACK`.

### Epic 3 done when
- Scripted member verified end-to-end · Policy display only after verification · PENDING_CALLBACK path tested · Hard safety invariants pass eval

---

## Epic 4: Claim Intake & Case

**Track:** A — **Owner: Bharath**
**Goal:** NL claim extraction, gap-detection clarify loop (partial case flag), confirm-and-create-case, handoff/cancel paths. Minor dependent support.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| [4.1](../../docs/stories/4.1.claim-schema-nl-extraction.md) | Claim schema & NL extraction | **Bharath** | Srimaan | 3.5 | M | ⚡ |
| [4.2](../../docs/stories/4.2.gap-detection-clarify-loop.md) | Gap detection & clarify loop | **Bharath** | Srimaan | 4.1 | M | ⚡ |
| [4.3](../../docs/stories/4.3.confirm-create-case.md) | Confirm & create case | **Bharath** | Srimaan | 4.2, 2.5 | S | ⚡ |
| [4.4](../../docs/stories/4.4.human-handoff-cancel-paths.md) | Human handoff & cancel paths | **Bharath** | Srimaan | 3.1 | S | ⚡ |

> **4.2 updated (A-3):** no hard turn limit; if fields still missing after prompting, call `create_case` with `missing_fields=[...]` and `complete=False`; inform member ops will follow up.
> **4.1 updated (A-2, A-4):** `patient_is_member` field required; `patient_name` required when `patient_is_member=False` (minor dependent). Adult dependent auth is OUT OF SCOPE.
> **4.4 updated (A-1):** human handoff (member-initiated) is distinct from PENDING_CALLBACK (system-initiated after 3 verify failures).

### Epic 4 done when
- Happy path creates a case · Partial case with missing_fields[] persisted · Minor dependent path (patient_name populated) works · Handoff + cancel paths tested · No-repeat-questions eval scenario passes

---

## Epic 5: API & Chat UI

**Track:** B — **Owner: Srimaan**
**Goal:** FastAPI streaming endpoints and minimal web chat UI.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| [5.1](../../docs/stories/5.1.fastapi-session-chat-case-endpoints.md) | FastAPI session, chat & case endpoints | **Srimaan** | Bharath | 3.1, 4.3 | M | ⚡ |
| [5.2](../../docs/stories/5.2.web-chat-ui.md) | Web chat UI | **Srimaan** | Bharath | 5.1 | S | defer |

> 5.2 deferred for workshop window — API + curl demo is enough to show the agent working.

### Epic 5 done when
- `POST /sessions` + `POST /sessions/{id}/messages` work end-to-end · SSE streaming tokens visible

---

## Epic 6: Evals & Quality

**Track:** Both — **Owners: Bharath + Srimaan**
**Goal:** Golden dataset, MLflow eval harness, CI gate, red-team safety scenarios.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| [6.1](../../docs/stories/6.1.golden-dataset-eval-harness.md) | Golden dataset & eval harness | **Srimaan** | Bharath | 4.3 | M | ⚡ |
| [6.2](../../docs/stories/6.2.ci-eval-gate-nightly-bedrock-evals.md) | CI eval gate & nightly Bedrock evals | **Srimaan** | Bharath | 6.1 | S | defer |
| [6.3](../../docs/stories/6.3.red-team-safety-scenarios.md) | Red-team safety scenarios | **Bharath** | Srimaan | 6.1 | S | defer |

> **6.1:** `eval/labelled_claims.csv` — 20+ rows (build set) + 10 holdout. Columns: `input`, `expected_answer`, `expected_tools`, `why`. Labelled by Srimaan/Bharath (ops stand-in), never by agent. Export `results.json` after each run.
> **6.1 must include:** no-repeat-questions scenario (FR-5.3), PENDING_CALLBACK scenario, minor dependent scenario.

### Epic 6 done when
- `make eval` scores ≥ 90% on build set · Hard gates 100% · results.json exported

---

## Epic 7: Deploy & Demo

**Track:** B — **Owner: Srimaan**
**Goal:** Deploy to AWS AgentCore Runtime. One story, not three.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| [7.1](../../docs/stories/7.1.aws-infrastructure-terraform.md) | Deploy to AWS AgentCore Runtime | **Srimaan** | Bharath | 5.1, 6.1 | M | ⚡ |
| [7.2](../../docs/stories/7.2.cd-pipeline-via-github-oidc.md) | GitHub Actions CD via OIDC | **Srimaan** | Bharath | 7.1 | S | defer |
| [7.3](../../docs/stories/7.3.demo-readiness-smoke-test-runbook.md) | Demo readiness & smoke-test runbook | **Srimaan** | Bharath | 7.1 | S | ⚡ |

> **7.1 updated:** deploy target is **AWS AgentCore Runtime** (not Terraform + ECS Fargate). Wire Bedrock model, configure AgentCore Memory (evaluate as Postgres checkpointer replacement), single `agentcore deploy` command. Old Terraform story still exists as file but is superseded.

### Epic 7 done when
- Agent running on AgentCore Runtime · Demo conversation works end-to-end on cloud · Smoke test passes

---

## Epic 8: Voice (Stretch)

**Track:** A — **Owner: Bharath**
**Goal:** Real-time voice intake using Amazon Transcribe streaming + Polly TTS.

> ⚠️ Stretch — only start if Epics 1–7 are merged and demo is green before time runs out.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| [8.1](../../docs/stories/8.1.voice-websocket-transcribe-streaming.md) | Voice WebSocket & Transcribe streaming | **Bharath** | Srimaan | 5.1 | L | stretch |
| [8.2](../../docs/stories/8.2.voice-polly-tts-turn-taking.md) | Polly TTS & turn-taking | **Bharath** | Srimaan | 8.1 | M | stretch |

---

## Epic 9: Presentation & Demo

**Track:** Both — **Owners: Srimaan + Bharath** (runs in parallel with E7)
**Goal:** Working demo script, results dashboard, and presentation deck for workshop audience.

| Story | Title | Owner | Reviewer | Depends on | Size | Priority |
|---|---|---|---|---|---|---|
| 9.1 | Demo script & scripted walkthrough recording | **Bharath** | Srimaan | 4.3 | S | ⚡ |
| 9.2 | Results dashboard (Vercel, reads results.json) | **Srimaan** | Bharath | 6.1 | S | ⚡ |
| 9.3 | Workshop presentation deck | **Both** | — | 7.1 | S | ⚡ |

> **9.3:** `_bmad-output/workshop-walkthrough.html` is already the foundation — update with final results and demo screenshots. Keep it browser-openable, no build step.

### Epic 9 done when
- `_bmad-output/workshop-walkthrough.html` opens in browser, shows all 7 steps with actual results populated, and `results.json` scores visible
- Demo runs end-to-end live in under 3 min (Bharath drives, Srimaan narrates)
- Vercel dashboard live at a public URL reading `results.json`
- ⚠️ **Known presentation risk:** story 5.2 (web chat UI) is deferred for workshop window — demo shows API/agent output, not a browser chat window. Audience will likely ask for the browser experience. Mitigation: show `workshop-walkthrough.html` as the visual, narrate the API interaction with clear output.

---

## Workshop Build Order (2.5 hr critical path)

```
Srimaan (Track B)                    Bharath (Track A)
─────────────────────────────────    ──────────────────────────────────
1.1  Repo scaffold + Docker (20m) ──► (unblocks both)
2.1  DB schema + seed       (20m)    1.3  LLM gateway mock      (15m)
2.2  Mock payer             (15m)    3.1  LangGraph skeleton     (20m)
2.3  Coverage MCP tools     (20m)    3.3  Intake node            (15m)
2.4  Verification MCP tools (20m)    3.4  Verify + callback      (25m)
2.5  Case + callback tools  (15m)    3.5  Policy display         (15m)
5.1  FastAPI endpoints      (20m) ──► (wires together)
6.1  Golden dataset + eval  (20m)    4.1  Claim extraction       (20m)
7.1  AgentCore deploy       (20m)    4.3  Confirm + case         (15m)
9.2  Vercel dashboard       (10m)    9.1  Demo script            (10m)
─────────────────────────────────    ──────────────────────────────────
Total: ~2h 20m                       Total: ~2h 15m
```

> Stories can start in parallel once 1.1 is merged. Srimaan + Bharath coordinate on `shared/schemas.py` (ClaimDraft) before 4.1 starts — this is the contracts-first moment.

---

## Story Details

> Format: Given/When/Then · Owner · Reviewer · Dependencies · Party-mode decisions applied inline

---

## Epic 1: Foundation & DevEx

### Story 1.1: Repo scaffold & local Docker stack
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** — · **Size:** M · ⚡

As a **developer**, I want a working repo with Docker Compose running all services locally,
so that both tracks can start building immediately without environment friction.

**Given** a fresh clone of the repo
**When** I run `make up`
**Then** `api`, `mcp-tools`, `postgres`, and `mlflow` containers start and pass healthchecks
**And** `GET /healthz` returns 200 with db + mcp reachability status
**And** `make test` runs and exits 0 (empty suite is fine at this point)
**And** `.env.example` documents all required variables with safe defaults for local dev

---

### Story 1.2: CI pipeline — lint, type, test, build *(deferred — post workshop)*
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 1.1 · **Size:** S

---

### Story 1.3: LLM gateway via LiteLLM (Bedrock + mock)
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 1.1 · **Size:** S · ⚡

As a **developer**, I want a `complete()` function that routes to Bedrock in prod and returns scripted responses in CI,
so that agent nodes can call the LLM without knowing the transport.

**Given** `LLM_MODE=mock` in `.env`
**When** `complete(messages, purpose="verify_phrase")` is called
**Then** `MockLLM` returns the scripted YAML response keyed by purpose + input hash/regex
**And** no real API call is made and no AWS credentials are required

**Given** `LLM_MODE=bedrock` in `.env` with valid AWS credentials
**When** `complete(messages, purpose="claim_extract", schema=ClaimDraft)` is called
**Then** the call routes through LiteLLM to AWS Bedrock Claude with the correct model ID
**And** throttling triggers retry with exponential backoff (max 2 retries, 20s timeout)

---

### Story 1.4: MLflow tracing baseline & PHI redaction
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 1.1 · **Size:** M · ⚡

As an **operator**, I want every agent turn traced to MLflow with PHI masked before writing,
so that traces are walkable by the team without exposing member data.

**Given** the agent processes any turn containing member name, DOB, or member ID
**When** the span is exported to MLflow
**Then** name, DOB, ZIP, member ID, phone, email, NPI are replaced with `[REDACTED]` in all span inputs/outputs
**And** the trace appears in the MLflow UI Traces tab with tool call rows visible
**And** `make eval` PHI-leak check passes with 0 leaked fields across all spans

---

## Epic 2: Data & MCP Tools

### Story 2.0: Golden dataset — `eval/labelled_claims.csv` *(NEW — party-mode fix)*
**Owner:** Both (Srimaan + Bharath) · **Reviewer:** Both · **Depends on:** 1.1 · **Size:** S · ⚡

As a **team**, I want a human-labelled golden dataset created before any agent code runs,
so that eval results measure real agent behaviour, not training data.

**Given** the team has reviewed the 7 seed personas and the claim scenarios from the PRD
**When** Srimaan and Bharath jointly fill `eval/labelled_claims.csv`
**Then** the file contains 20+ build-set rows covering:
  - Happy path (verified member, complete claim, case created)
  - PENDING_CALLBACK path (3 verification failures → callback requested)
  - Partial case (missing provider name, `complete=False` expected)
  - Minor dependent (patient ≠ subscriber, `patient_name` in expected_answer)
  - No-repeat-questions (provider given in description → agent must not re-ask)
  - Cancel mid-flow (no case created)
  - Human handoff (member-initiated)
**And** 10 rows are withheld as holdout (labels present in the file, column `holdout=true`)
**And** columns: `id`, `input`, `expected_answer` (JSON), `expected_tools` (JSON array), `why`, `holdout`
**And** no row is generated by the agent — every label is human-written

---

### Story 2.1: DB schema, migrations & synthetic seed
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 2.0 · **Size:** M · ⚡

As a **developer**, I want the Postgres schema and realistic synthetic members,
so that tools and evals have deterministic data to work against.

**Given** a fresh Postgres instance
**When** I run `make migrate && make seed`
**Then** all tables from architecture §4 exist (members, coverage_snapshots, verifications, cases, audit_log, callbacks)
**And** `make seed` loads 7 personas (P1–P7) idempotently — running twice produces the same row count
**And** `make migrate` works inside compose and in a CI service container

---

### Story 2.2: Mock payer eligibility service
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 2.1 · **Size:** S · ⚡

As a **tools developer**, I want a mock payer returning 271-like JSON from seed data,
so that coverage fetch works end-to-end without a real clearinghouse.

**Given** member ID `P1` exists in `data/seed/coverage.json`
**When** `PayerClient.fetch_eligibility(member_id="P1")` is called
**Then** it returns a 271-shaped JSON payload matching the seed record
**And** configurable latency + failure injection works via `PAYER_MOCK_LATENCY_MS` and `PAYER_MOCK_FAIL_RATE`
**And** an unknown member ID raises `PayerUnavailable` (same as network failure — no differential response)

---

### Story 2.3: FastMCP coverage tools
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 2.2 · **Size:** M · ⚡

As an **agent** (tool consumer), I want `fetch_coverage` and `get_policy_view` MCP tools,
so that coverage loads and policy reveals only after verification.

**Given** a valid member ID and an active session
**When** `fetch_coverage` is called
**Then** a coverage snapshot is stored with `status=unverified` and its UUID returned
**And** `get_policy_view` returns `NOT_VERIFIED` for any session without a PASSED verification record
**And** `get_policy_view` returns the policy summary only when verification `status=PASSED`
**And** all tool calls write an audit log entry
**And** tool contract tests pass against the JSON schemas in `docs/contracts/mcp-tools.md`

---

### Story 2.4: FastMCP verification tools
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 2.3 · **Size:** M · ⚡

As a **security-conscious PO**, I want verification decided by deterministic code,
so the LLM can never be talked into bypassing it.

**Given** a session with an unverified coverage snapshot
**When** `start_verification` is called
**Then** a verification record is created with status=PENDING and a random non-repeating challenge question
**And** `check_answer` evaluates: name via rapidfuzz ≥ 90, DOB via free-text date parser, ZIP first-5 match, employer fuzzy ≥ 85

**Given** a member gives 3 consecutive wrong answers
**When** `check_answer` is called for the third time
**Then** verification status is set to `LOCKED` and `request_callback` is triggered automatically
**And** expected answers never appear in tool responses, logs, or traces

---

### Story 2.5: FastMCP case & callback tools *(updated A-1)*
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 2.1 · **Size:** S · ⚡

As a **claims ops user**, I want verified claims saved as cases and failed verifications queued for callback,
so that no member interaction is lost.

**Given** a session with verification `status=PASSED` and all required claim fields present
**When** `create_case` is called
**Then** a case is created with `case_number` format `CLM-YYYYMMDD-NNNNN`, `status=NEW`
**And** `create_case` accepts `missing_fields[]` and `complete: bool` — stores them on the case record
**And** `create_case` rejects with `NOT_VERIFIED` error if verification is not PASSED

**Given** a session that has hit 3 verification failures
**When** `request_callback(session_id, contact_number)` is called
**Then** a row is written to the `callbacks` table with member_id (hashed), session_id, contact_number, status=PENDING
**And** the tool is idempotent per session_id

---

## Epic 3: Identity & Policy Flow

### Story 3.1: LangGraph skeleton, state & checkpointer
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 1.3, 2.1 · **Size:** M · ⚡

As an **agent developer**, I want the full graph wired with stub nodes and persistent state,
so that every subsequent node story just fills in one node without touching the graph structure.

**Given** a new session is created
**When** the graph is invoked with a user message
**Then** `AgentState` (including `Phase` enum with `PENDING_CALLBACK` replacing `LOCKED`) is initialised
**And** `build_graph()` wires all nodes and edges with stub pass-throughs
**And** `PostgresSaver` checkpoints state per `thread_id=session_id` after every turn
**And** the graph resumes correctly from checkpoint when the same `session_id` is reused
**And** `python -m agent.cli` runs a scripted turn end-to-end with mock LLM

---

### Story 3.2: Phase-based stub router (intent classifier enhancement later)
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 3.1 · **Size:** S · ⚡

As a **member**, I want to cancel or request a human at any point without being stuck in a loop,
so that I always have an exit.

**Given** `state.phase = VERIFY` and the member types "cancel"
**When** the router processes the message
**Then** the session routes to the `cancelled` node regardless of phase
**And** "request human" intent routes to the `handoff` node from any phase
**And** all other messages route by `state.phase` (stub — no LLM classification yet)

*Note: Full intent classification (abuse detection, edit intent, ambiguity) is a follow-up enhancement story within E3. This stub is required to unblock 3.3, 3.4, 3.5.*

---

### Story 3.3: Intake node — member ID & name
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 3.2, 2.3 · **Size:** S · ⚡

As a **member**, I want to give my ID and name naturally across one or two turns,
so I can start without filling in a form.

**Given** a member sends their member ID and full name in one message
**When** the intake node processes the turn
**Then** `member_id` and `full_name` are extracted and validated (`^[A-Z]{3}\d{9}$`)
**And** `fetch_coverage` is called and the snapshot stored with `status=unverified`
**And** `start_verification` is called and the session advances to `Phase.VERIFY`
**And** an unknown member ID and a known member ID produce identical responses (no enumeration)
**And** the member ID is echoed back masked (first 3 chars + `****`)

---

### Story 3.4: Verify node — challenge loop & PENDING_CALLBACK *(updated A-1)*
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 3.3, 2.4 · **Size:** M · ⚡

As a **member**, I want simple security questions to confirm my identity,
so that only I can see my coverage.

**Given** the session is in `Phase.VERIFY`
**When** the member answers a challenge question
**Then** the raw answer is sent to `check_answer` — the LLM never sees the expected answer
**And** on PENDING → the next challenge question is presented
**And** on FAILED with attempts remaining → the member is invited to try again
**And** on PASSED → `verified=True`, `Phase.POLICY`, coverage unlocked

**Given** the member gives 3 consecutive wrong answers
**When** `check_answer` returns `status=LOCKED`
**Then** `request_callback` is called with the session's collected contact number (or asked for one)
**And** `state.phase = PENDING_CALLBACK`
**And** the agent says: *"I wasn't able to verify your identity. Leave me a number and our team will call you back."*
**And** the session ends — no policy data shown, no case created

---

### Story 3.5: Policy display node (verified gate)
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 3.4, 2.3 · **Size:** S · ⚡

As a **verified member**, I want a clear coverage summary before I file,
so I understand what's covered.

**Given** `state.verified = True` and `state.phase = POLICY`
**When** the policy node runs
**Then** `get_policy_view` is called and `state.policy_view` is populated
**And** the agent renders: plan name, effective dates, deductible (met/remaining), OOP max (met/remaining), copays
**And** all values come from `policy_view` — no LLM-generated policy text
**And** if `state.verified = False`, a `VerificationInvariantError` is raised and routes to handoff

---

## Epic 4: Claim Intake & Case

### Story 4.1: Claim schema & NL extraction *(updated A-2, A-4)*
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 3.5 · **Size:** M · ⚡

As a **member**, I want to describe what happened in plain words,
so I don't need to know claim terminology.

**Given** the member describes an ER visit in free text
**When** the claim node processes the description
**Then** `ClaimDraft` fields are extracted using LLM structured output (`response_format=ClaimDraft`)
**And** extracted values merge into the existing draft — confirmed values are never overwritten with null
**And** relative dates (e.g. "last Tuesday") are resolved to calendar dates
**And** `patient_is_member` is extracted; when `False`, `patient_name` (and `patient_dob` if given) are captured
**And** adult dependent filing is rejected with a clear message (only minor dependents supported)

---

### Story 4.2: Gap detection & clarify loop *(updated A-3)*
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 4.1 · **Size:** M · ⚡

As a **member**, I want to be asked only for missing info one question at a time,
so filing is quick and doesn't feel repetitive.

**Given** the claim draft is missing `place_of_service`
**When** the clarify node runs
**Then** one targeted question is asked for the highest-priority missing field
**And** a field the member already provided in this session is never asked again

**Given** required fields remain missing after several clarification turns
**When** the clarify loop detects no further progress
**Then** the agent proceeds to confirmation with `missing_fields=[...]` and `complete=False`
**And** the member is told: *"I'll submit your claim now — our team may follow up about [field]."*
**And** no session is blocked or errored due to missing optional fields

---

### Story 4.3: Confirm & create case
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 4.2, 2.5 · **Size:** S · ⚡

As a **member**, I want to review and explicitly confirm before submission,
so my claim is accurate.

**Given** the claim draft is ready for review
**When** the confirm node presents the summary
**Then** all claim fields are shown in a readable format before the member confirms
**And** the member's affirmative reply triggers `create_case` with the full `ClaimDraft` (including `missing_fields[]` and `complete` flag)
**And** the case number and status `NEW` are returned to the member
**And** the LLM never decides whether to create the case — `create_case` tool owns that decision
**And** a "correct" reply routes back to claim extraction, not re-confirmation

---

### Story 4.4: Human handoff & cancel paths *(updated A-1)*
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 3.1 · **Size:** S · ⚡

As a **member**, I want to stop or reach a person at any time,
so I'm never trapped in the flow.

**Given** a member types "I want to speak to someone" from any phase
**When** the handoff node processes the intent
**Then** the agent acknowledges with a friendly message and logs `reason=user_request` to audit
**And** the session ends cleanly — no case is created

**Given** a member types "cancel" from any phase
**When** the cancel node processes the intent
**Then** the agent confirms the cancellation, discards the coverage snapshot, logs `reason=cancel`
**And** no case is created; session moves to `Phase.CANCELLED`

*Note: PENDING_CALLBACK (3 verification failures) is handled in Story 3.4, not here. This story covers member-initiated exits only.*

---

## Epic 5: API & Chat UI

### Story 5.1: FastAPI session, chat & case endpoints
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 3.1, 4.3 · **Size:** M · ⚡

As a **UI developer**, I want HTTP endpoints that drive the agent with streaming output,
so any front end (or curl) can use the system.

**Given** a `POST /sessions` request
**When** the endpoint handles it
**Then** a new `session_id` is returned with a greeting message

**Given** a `POST /sessions/{id}/messages` request with user text
**When** the agent processes the turn
**Then** agent tokens stream via SSE (`event: token`), followed by `event: state` and `event: done`
**And** `GET /sessions/{id}` never returns `policy_view` if `verified=False`
**And** rate limiting rejects >30 messages/min/session and messages >2000 chars

---

### Story 5.2: Web chat UI *(deferred for workshop — post-critical-path)*
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 5.1 · **Size:** S

> ⚠️ Deferred for workshop window. Demo shows API output directly. See Epic 9 presentation risk note.

---

## Epic 6: Evals & Quality

### Story 6.1: Eval harness (golden dataset pre-built in E2 Story 2.0)
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 4.3, 2.0 · **Size:** M · ⚡

As a **team**, I want repeatable offline evaluation that scores the agent against pre-labelled scenarios,
so we know when changes help or hurt.

**Given** `eval/labelled_claims.csv` exists (built in Story 2.0)
**When** `make eval` runs
**Then** `evals/runner.py` replays each build-set scenario through the graph using fake MCP + mock LLM
**And** scorers check: safety invariants (hard gates — 0 failures allowed), outcome match, field extraction accuracy ≥ 90%, no-repeat-questions (FR-5.3), PENDING_CALLBACK path, minor dependent path
**And** results are exported to MLflow evaluation run and to `results.json` (per-scenario decision, code-check, judge score, token counts)
**And** `make eval` exits non-zero if any hard gate fails or overall score < 90%

---

### Story 6.2: CI eval gate *(deferred)*
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 6.1 · **Size:** S

---

### Story 6.3: Red-team safety scenarios *(deferred)*
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 6.1 · **Size:** S

---

## Epic 7: Deploy & Demo

### Story 7.1: Deploy to AWS AgentCore Runtime *(replaces Terraform/ECS)*
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 5.1, 6.1 · **Size:** M · ⚡

As a **team**, I want the agent running in the cloud with a single deploy command,
so we can demo live without a local machine.

**Given** AgentCore Runtime is configured with the Bedrock Claude model IDs
**When** `agentcore deploy` is run
**Then** the agent endpoint is live and `GET /healthz` returns 200
**And** a full demo conversation runs end-to-end against the cloud endpoint
**And** AgentCore Memory is evaluated as a replacement for the Postgres LangGraph checkpointer

---

### Story 7.2: GitHub Actions CD *(deferred)*
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 7.1 · **Size:** S

---

### Story 7.3: Demo readiness & smoke-test runbook
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 7.1 · **Size:** S · ⚡

As a **presenter**, I want a reliable scripted demo with a fallback plan,
so the demo works in front of an audience.

**Given** the agent is deployed on AgentCore
**When** `scripts/smoke_e2e.py` runs against the deployed URL
**Then** the happy-path scenario completes, a case number is returned, and the MLflow trace is walkable
**And** `docs/demo-runbook.md` documents: personas, script, expected outputs, local-compose fallback
**And** the runbook has been dry-run twice before presentation

---

## Epic 8: Voice (Stretch)

### Story 8.1: Voice WebSocket & Transcribe streaming *(stretch)*
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 5.1 · **Size:** L

As a **member**, I want to speak instead of type, so filing feels like a phone call.

**Given** a browser microphone stream on `WS /voice/{session_id}`
**When** audio arrives at 16kHz PCM
**Then** it streams to Amazon Transcribe Streaming; partial transcripts are sent to the UI; final utterance text is sent to the graph
**And** end-of-utterance is detected via stability flag + 800ms silence

---

### Story 8.2: Polly TTS & turn-taking *(stretch)*
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 8.1 · **Size:** M

As a **member**, I want to hear replies so I can complete the flow hands-free.

**Given** the agent produces a response text in voice mode
**When** the response is sent
**Then** Amazon Polly neural voice streams audio back over the WebSocket
**And** barge-in stops Polly playback and resumes Transcribe input
**And** all safety invariants pass in voice mode (same eval thresholds)

---

## Epic 9: Presentation & Demo

### Story 9.1: Demo script & scripted walkthrough
**Owner:** Bharath · **Reviewer:** Srimaan · **Depends on:** 4.3 · **Size:** S · ⚡

As a **presenter**, I want a tested demo script with exact inputs and expected outputs,
so the live demo doesn't rely on improvisation.

**Given** the demo script in `docs/demo-runbook.md` is followed
**When** the demo conversation runs (Bharath drives, Srimaan narrates)
**Then** the agent verifies a member, displays policy, captures a claim, and returns a case number in < 3 minutes
**And** at least one non-happy path is shown (PENDING_CALLBACK or human handoff)
**And** an MLflow trace of the conversation is walkable during the presentation

---

### Story 9.2: Results dashboard (Vercel, reads results.json)
**Owner:** Srimaan · **Reviewer:** Bharath · **Depends on:** 6.1 · **Size:** S · ⚡

As a **workshop audience member**, I want to see eval results in a browser,
so I can judge whether the system is trustworthy.

**Given** `results.json` is exported from a `make eval` run
**When** the Vercel dashboard URL is opened
**Then** a table shows per-scenario decision, code-check result, judge score, and token counts
**And** summary cards show total scenarios, pass rate, and hard-gate status (all green = 100%)
**And** the dashboard has no API keys, no server, and no build step — static HTML reading `/results.json`

---

### Story 9.3: Workshop presentation deck
**Owner:** Both (Srimaan + Bharath) · **Reviewer:** — · **Depends on:** 7.1 · **Size:** S · ⚡

As a **workshop audience member**, I want a clear walkthrough of every decision made,
so I can understand how the system was built and why.

**Given** `_bmad-output/workshop-walkthrough.html` is updated with all 7 steps completed
**When** the file is opened in a browser
**Then** all step cards are filled in with actual outputs and decisions (not placeholders)
**And** the results.json score, MLflow trace link, and AgentCore deploy URL are visible
**And** the presentation risk note for 5.2 (no browser UI) is clearly addressed in the narration plan

**Epic 9 done when:** HTML opens in browser showing all 7 steps with real results · Vercel dashboard live at public URL · Demo runs end-to-end < 3 min · ⚠️ Known risk: no browser chat UI (5.2 deferred) — mitigation in demo script

