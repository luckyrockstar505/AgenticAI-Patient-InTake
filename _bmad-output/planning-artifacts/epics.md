---
stepsCompleted: ["step-01-validate-prerequisites"]
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
| [2.1](../../docs/stories/2.1.db-schema-migrations-synthetic-seed.md) | DB schema, migrations & synthetic seed | **Srimaan** | Bharath | 1.1 | M | ⚡ |
| [2.2](../../docs/stories/2.2.mock-payer-eligibility-service.md) | Mock payer eligibility service | **Srimaan** | Bharath | 2.1 | S | ⚡ |
| [2.3](../../docs/stories/2.3.fastmcp-coverage-tools.md) | FastMCP coverage tools | **Srimaan** | Bharath | 2.2 | M | ⚡ |
| [2.4](../../docs/stories/2.4.fastmcp-verification-tools.md) | FastMCP verification tools | **Srimaan** | Bharath | 2.3 | M | ⚡ |
| [2.5](../../docs/stories/2.5.fastmcp-case-tools.md) | FastMCP case & callback tools | **Srimaan** | Bharath | 2.1 | S | ⚡ |

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
| [3.2](../../docs/stories/3.2.intent-classifier-global-router.md) | Intent classifier & global router | **Bharath** | Srimaan | 3.1 | S | defer |
| [3.3](../../docs/stories/3.3.intake-node-member-id-name.md) | Intake node (member ID + name) | **Bharath** | Srimaan | 3.1 | S | ⚡ |
| [3.4](../../docs/stories/3.4.verify-node-challenge-loop-lockout.md) | Verify node — challenge loop & callback | **Bharath** | Srimaan | 3.3, 2.4 | M | ⚡ |
| [3.5](../../docs/stories/3.5.policy-display-node-verified-gate.md) | Policy display node (verified gate) | **Bharath** | Srimaan | 3.4, 2.3 | S | ⚡ |

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
- Demo runs end-to-end in under 3 min · results.json displayed in Vercel dashboard · Walkthrough HTML complete with all 7 steps filled in

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
