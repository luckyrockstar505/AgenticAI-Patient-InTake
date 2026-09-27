# PRD — Claims Intake Agent (Demo)

> BMAD artifact · PM output · Version 1.0 · Source: `docs/brief.md`
> Stories live in `docs/stories/` (one file per story). Epic files in `docs/epics/`.

## 1. Goals

- G1 — Verify a member's identity safely before revealing any coverage data.
- G2 — Show verified policy details in plain language.
- G3 — Turn a free-text claim description into a complete, structured case with minimal follow-ups.
- G4 — Make every run observable (MLflow) and every release gated by evals.
- G5 — Deployable to AWS with one merge to `main`.

## 2. Functional requirements

| ID | Requirement |
|---|---|
| FR1 | Agent greets and asks for member ID and full name (in any order, one or two turns). |
| FR2 | Member ID format validated (`^[A-Z]{3}\d{9}$` for demo) before any tool call; re-ask on invalid. |
| FR3 | On valid member ID, agent calls `fetch_coverage` (MCP) and stores a **coverage snapshot** with status `unverified`. |
| FR4 | If member ID not found → generic message ("We couldn't verify those details") — never reveal whether the ID exists. |
| FR5 | Verification: name fuzzy-match (deterministic) + DOB exact match + 1 challenge question (ZIP, employer/group name, or subscriber name) chosen by the tool. |
| FR6 | Max **3** failed verification attempts per session → session `LOCKED`, handoff message, audit event. |
| FR7 | Coverage details are only rendered when `session.verified = true`. |
| FR8 | Policy view: plan name/type, effective dates, network, deductible (total/met/remaining), OOP max (total/met/remaining), copays (PCP, specialist, ER, urgent care), coinsurance. |
| FR9 | Agent accepts a claim description in natural language and extracts `ClaimDraft` fields (see architecture §5). |
| FR10 | For missing/ambiguous required fields the agent asks **one targeted question at a time**, max 6 clarify turns, then offers human handoff. |
| FR11 | Agent validates extracted values (date of service not in future, within coverage period, amount ≥ 0, etc.). |
| FR12 | Before creating a case the agent shows a summary and requires explicit confirmation ("yes"/"confirm"). Member may correct any field. |
| FR13 | `create_case` persists the case (status `NEW`), links the coverage snapshot, returns case number `CLM-YYYYMMDD-XXXXX`. |
| FR14 | Supported intents at every step: cancel, human handoff, repeat/clarify, off-topic (see `docs/intents.md`). |
| FR15 | *Stretch:* voice mode — streaming STT → same graph → TTS. |

## 3. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR1 | **Security/PHI:** synthetic data only; PHI redacted from logs & MLflow traces; secrets in AWS Secrets Manager / `.env` locally (never committed). |
| NFR2 | **Determinism where it matters:** verification decisions & case creation happen in tool code, never by LLM judgment. |
| NFR3 | **Latency:** p95 agent turn < 4s (text) on Bedrock Claude Sonnet-class model. |
| NFR4 | **Observability:** every turn produces an MLflow trace with node spans, tool spans, LLM spans, token counts and cost. |
| NFR5 | **Quality gate:** CI fails if unit/integration tests fail or offline evals fall below thresholds (`docs/qa/eval-plan.md`). |
| NFR6 | **Portability:** LLM access only via LiteLLM; model is a config value. `LLM_MODE=mock` for tests/CI. |
| NFR7 | **Auditability:** audit_log row for fetch, each verification attempt, lock, policy view, case creation. |
| NFR8 | **Code quality:** ruff + mypy (strict on `agent/`, `mcp_tools/`), pytest coverage ≥ 80% on tools & graph routing. |

## 4. Epics

| # | Epic | Track | Goal |
|---|---|---|---|
| E1 | Foundation & DevEx | B (1.3 A) | Repo, local stack, CI, LLM gateway, tracing baseline |
| E2 | Data & MCP Tools | B | Schema, synthetic data, mock payer, FastMCP tool server |
| E3 | Identity & Policy Flow | A | LangGraph skeleton, intents, intake, verification, policy display |
| E4 | Claim Intake & Case | A | NL extraction, clarify loop, confirm, case creation, handoff |
| E5 | API & Chat UI | B | FastAPI endpoints, streaming, minimal web UI |
| E6 | Evals & Quality | A/B | Golden dataset, eval harness, CI gate, red-team |
| E7 | Deploy & Demo | B | Terraform on AWS, CD pipeline, demo runbook |
| E8 | Voice (stretch) | A/B | Transcribe streaming + Polly |

## 5. Story map

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| 1.1 | Repo scaffold & local docker stack | B | — | M |
| 1.2 | CI pipeline (lint, type, test, build) | B | 1.1 | S |
| 1.3 | LLM gateway via LiteLLM (Bedrock + mock) | A | 1.1 | S |
| 1.4 | MLflow tracing baseline & PHI redaction | B | 1.1 | M |
| 2.1 | DB schema, migrations & synthetic seed | B | 1.1 | M |
| 2.2 | Mock payer eligibility service | B | 2.1 | S |
| 2.3 | FastMCP coverage tools | B | 2.2 | M |
| 2.4 | FastMCP verification tools | B | 2.3 | M |
| 2.5 | FastMCP case tools | B | 2.1 | S |
| 3.1 | LangGraph skeleton, state & checkpointer | A | 1.3 | M |
| 3.2 | Intent classifier & global router | A | 3.1 | M |
| 3.3 | Intake node (member ID + name) | A | 3.1 | S |
| 3.4 | Verify node: challenge loop & lockout | A | 3.3, 2.4 | M |
| 3.5 | Policy display node (verified gate) | A | 3.4, 2.3 | S |
| 4.1 | Claim schema & NL extraction | A | 1.3 | M |
| 4.2 | Gap detection & clarify loop | A | 4.1, 3.1 | M |
| 4.3 | Confirm & create case | A | 4.2, 2.5 | S |
| 4.4 | Human handoff & cancel paths | A | 3.2 | S |
| 5.1 | FastAPI session/chat/case endpoints | B | 3.1 | M |
| 5.2 | Web chat UI | B | 5.1 | S |
| 6.1 | Golden dataset & eval harness | A | 3.1, 1.4 | M |
| 6.2 | CI eval gate & nightly Bedrock evals | B | 6.1, 1.2 | S |
| 6.3 | Red-team & safety scenarios | A | 6.1 | S |
| 7.1 | AWS infrastructure (Terraform) | B | 1.1 | L |
| 7.2 | CD pipeline via GitHub OIDC | B | 7.1, 1.2 | M |
| 7.3 | Demo readiness: smoke test & runbook | A+B | all E1–E7 | S |
| 8.1 | Voice: WebSocket + Transcribe streaming | B | 5.1 | L |
| 8.2 | Voice: Polly TTS & turn-taking | A | 8.1 | M |

Sizes: S ≈ ½–1 day, M ≈ 1–2 days, L ≈ 3+ days (with Claude Code).

## 6. Suggested sprint plan (two devs in parallel)

```
Day 0 (both)  Contracts review: docs/contracts/*.md, state schema, ClaimDraft  → freeze v1
Sprint 1      B: 1.1 → 1.2 → 2.1          A: (pair on 1.1) → 1.3 → 3.1
Sprint 2      B: 1.4 → 2.2 → 2.3 → 2.4 → 2.5    A: 3.2 → 3.3 → 4.1 → 6.1
Sprint 3      B: 5.1 → 5.2 → 6.2          A: 3.4 → 3.5 → 4.2 → 4.3 → 4.4
Sprint 4      B: 7.1 → 7.2                A: 6.3        Both: 7.3 (demo)
Stretch       B: 8.1                      A: 8.2
```

Track A codes against the **fake MCP client** (`tests/fakes/fake_mcp.py`, built in 3.1) until Track B's real tools land — contracts in `docs/contracts/mcp-tools.md` are the seam.

## 7. Definition of Done (every story)

- [ ] All acceptance criteria met and demonstrated in PR description
- [ ] Unit tests added; `make test` green; coverage not reduced
- [ ] Eval scenarios listed in story added/updated in `evals/datasets/`; `make eval` passes locally (mock mode)
- [ ] Tracing spans/attributes listed in story present (screenshot or trace ID in PR)
- [ ] No PHI in logs (redaction test passes)
- [ ] Story file updated: Status, Dev Agent Record, File List, Change Log
- [ ] Reviewed & approved by the other developer; CI green; squash-merged
