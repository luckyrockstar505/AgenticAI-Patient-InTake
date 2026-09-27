---
title: Claims Intake Agent — PRD
status: draft
created: 2026-09-27
updated: 2026-09-27
---

# Claims Intake Agent — Product Requirements Document

> MVP only · One agent (single LangGraph graph, not multi-agent) · Source: `docs/intake-brief.md` (updated 2026-09-27)
> This reconciles the party-mode-reviewed draft (`review-party-mode.md`) with its resolved action items A-1–A-4, A-6, A-8, A-9 (see `.memlog.md`), plus the labelled-example success criteria already checked into `evals/`. A-7 and the contested items are carried into **Open Items** below rather than decided here.

---

## Goal & Success Metric

**Goal.** Replace the manual claim intake front door with a single conversational AI agent — one LangGraph graph, no sub-agent orchestration — that verifies a member's identity, shows their coverage, and turns a free-text claim description into a complete, auditable, structured case ready for backend processing.

**Competitive context.** Unlike chatbot-layer vendors (Olive AI, Waystar, Infinitus) that bolt conversation onto an existing intake form, this agent makes verification and case creation tool-owned decisions the LLM cannot override — the safety story is the product, not just the conversation. *(Added per A-8.)*

**Success metric.** Success criteria are the labelled examples already checked into the repo, not invented targets:
- **Hard gates (100%, `evals/thresholds.yaml:hard_gates`):** `safety.no_case_without_verify_and_confirm` (S02, S03, R06) · `safety.no_policy_before_verify` (S03, S06, R01, R03) · `safety.no_enumeration` (S06, R04) · `safety.no_phi_echo` (every scenario's `must_not_contain`).
- **Scenario outcome match:** ≥ 0.95 mock / ≥ 0.90 live across S01–S10 in `evals/datasets/scenarios.jsonl` (`outcome.final_phase`, `outcome.claim_fields`).
- **Extraction & intent:** `extraction.field_f1` ≥ 0.90 against `claims_extraction.jsonl` (E01–E08); `intent.accuracy` ≥ 0.90 against `intents.jsonl` (live).

**`[NOTE FOR PM]`** `docs/intake-brief.md` §5a describes a new golden dataset (`eval/labelled_claims.csv`, 20 build + 10 holdout scenarios, LLM-judge scored) that doesn't exist yet and isn't the same shape as the `evals/datasets/*.jsonl` + `evals/thresholds.yaml` files already in the repo (code-check scored, 18 scenarios + 8 extraction + 20 intent examples, already written). Two different eval designs for the same product — pick one before story-writing. Carried into **Open Items**.

**Counter-metric.** LLM judge flags ≥ 10% of sessions as confusing, repetitive, or untrustworthy → UX / prompt regression. `efficiency.clarify_turns` must never be improved by skipping a required field — `outcome.claim_fields` accuracy wins that trade-off.

---

## Glossary

- **Coverage snapshot** — cached eligibility data, `unverified` until identity checks pass.
- **Verification** — deterministic (non-LLM) name + DOB + one challenge-question check.
- **ClaimDraft** — structured claim fields extracted from free text (see `docs/architecture.md` §5).
- **Case** — the persisted, confirmed claim record ops receives.
- **Callback request** — the record created on verification lockout, queued for a human agent to call the member back (see FR-3.3; replaces the earlier generic "route to human" wording for this path).

---

## User Journey

**Maria, 34 — subscriber filing a claim for her daughter's ER visit.**

1. Maria opens the web chat. She types her member ID and full name.
2. The agent replies: "Got it — just a moment while I look up your coverage." Coverage fetches silently behind the scenes.
3. The agent asks for her date of birth and ZIP code to confirm her identity.
4. After she answers correctly, her plan, deductible, and copays appear — nothing was shown before this moment.
5. "What happened? Tell me in your own words." Maria describes the ER visit and names her daughter as the patient.
6. One question: "Do you have the provider's name or facility?" She types it.
7. The agent shows a structured summary. Maria reads it and types "Yes, submit."
8. "Done — your case number is CLM-20261001 and its status is NEW. You'll hear from the claims team within 5 business days."

Total elapsed: under 3 minutes.

**Non-happy paths in scope:**
- Verification fails 3 times → session enters `PENDING_CALLBACK`; agent collects a callback number; no policy shown, no case created; a human calls back manually. *(Updated per A-1 — replaces the earlier "routes to human" wording.)*
- Member requests human handoff mid-flow → immediate warm transfer message.
- Member cancels after claim intake → confirm discard, no case created.
- Claim description is missing required fields → agent asks for each missing field once; if still missing after asking, the case is created anyway with `missing_fields` recorded and `complete: false` — ops follows up. *(Updated per A-3 — no hard turn cap.)*
- Subscriber files on behalf of a minor dependent → `patient_name` is collected and differs from the subscriber's name. Adult-dependent self-filing is out of scope for MVP. *(Per A-2.)*

---

## State Model

*(Added per A-5. This table is the quick reference; the authoritative diagram lives in `docs/architecture.md`.)*

| State | Entered when | Exits to |
|---|---|---|
| `INTAKE` | Session starts | `VERIFYING` once a valid member ID + name are given |
| `VERIFYING` | Coverage snapshot fetched (`unverified`) | `VERIFIED` (challenge passed) or `PENDING_CALLBACK` (3 failures) |
| `VERIFIED` | Verification passes | `CLAIM_INTAKE` |
| `PENDING_CALLBACK` | 3 failed verification attempts | terminal — human calls back |
| `CLAIM_INTAKE` / `CLARIFYING` | Member describes the claim | `CONFIRMING` |
| `CONFIRMING` | Summary shown | `DONE` (confirmed) or `CANCELLED` |
| `DONE` | `create_case` succeeds | terminal |
| `CANCELLED` / `HUMAN_HANDOFF` | Member cancels, or requests a person, from any state | terminal |

---

## Functional Requirements

### FR-1 · Member Identification

| ID | Requirement |
|---|---|
| FR-1.1 | Accept member ID (9-digit alphanumeric) and full name via text. If filing for a minor dependent, also collect the dependent's name (`patient_name`). Adult-dependent self-filing is out of scope for MVP. |
| FR-1.2 | Validate member ID format before any fetch; reject with a plain-language message on bad format — no hint whether the ID exists in the system. |

### FR-2 · Coverage Fetch

| ID | Requirement |
|---|---|
| FR-2.1 | Call the payer MCP tool (`fetch_coverage`) with the member ID; store the snapshot with status `unverified`. |
| FR-2.2 | Never expose policy data to the member until verification status is `verified`. |
| FR-2.3 | If the payer tool returns no record, treat it exactly like a verification failure (same lockout/callback path, FR-3.3) — no differential error message. |

### FR-3 · Identity Verification

| ID | Requirement |
|---|---|
| FR-3.1 | Challenge with date of birth + one of: ZIP code, employer name, or subscriber ID. |
| FR-3.2 | Evaluate each answer via a deterministic tool (`verify_answer`); the LLM never makes or overrides the pass/fail decision. |
| FR-3.3 | After 3 consecutive failures: call `request_callback` (tool), collect a callback phone number, write member ID + session ID + contact number to the callbacks queue, set state `PENDING_CALLBACK`. No case created, no policy shown. *(Replaces lockout→human-queue wording per A-1.)* |
| FR-3.4 | Never hint to the member which answer was wrong, or whether the member ID exists. |

### FR-4 · Policy Display

| ID | Requirement |
|---|---|
| FR-4.1 | After `verified`: display plan name, effective dates, deductible (met / remaining), OOP max (met / remaining), and relevant copays. |
| FR-4.2 | All values rendered directly from the coverage snapshot — no LLM-generated policy text; the model may only compose the framing sentence. |

### FR-5 · Claim Intake

| ID | Requirement |
|---|---|
| FR-5.1 | Invite a free-text claim description; extract structured fields: date of service, place of service, provider name and NPI (if given), reason/diagnosis description, services rendered, amounts (if known), accident-related flag, other-insurance flag, and `patient_name` when the patient is a minor dependent. |
| FR-5.2 | Ask one targeted clarification question per missing or ambiguous required field, once each — no hard turn cap. If required fields are still missing after asking, proceed to confirmation with what's collected. *(Replaces the earlier 5-turn cap per A-3.)* |
| FR-5.3 | Never ask for a field the member already provided in the same session. |
| FR-5.4 | Required fields for case creation: `date_of_service`, `place_of_service`, `provider_name`, `diagnosis_reason` (plus `patient_name` when patient ≠ subscriber). Optional: amounts, NPI, accident-related flag, other-insurance flag. *(Confirmed per A-4 — assumption tag removed.)* |

### FR-6 · Confirmation and Case Creation

| ID | Requirement |
|---|---|
| FR-6.1 | Present a complete structured summary of extracted claim fields before creation, including any fields still missing. |
| FR-6.2 | Create the case record only after explicit member confirmation (affirmative reply). |
| FR-6.3 | `create_case` receives `missing_fields: []` and `complete: bool` alongside the collected fields; returns a case number and status `NEW`. The LLM never decides whether to create the case. *(Updated per A-3.)* |
| FR-6.4 | Audit logging — **contested, needs Srimaan's call (see Open Items C-1/C-3).** Default until decided: one event-only log entry per session (verification outcome + case ID or null), no member identifiers — this strictly satisfies the `safety.no_phi_echo` hard gate with no ambiguity. |

### FR-7 · Control Flow

| ID | Requirement |
|---|---|
| FR-7.1 | Offer cancel at any turn; confirm before discarding; no case created on cancel. |
| FR-7.2 | Offer human handoff at any turn (member-initiated, or system-initiated on lockout via FR-3.3). |
| FR-7.3 | Resume a checkpointed session without re-asking fields already collected (Postgres LangGraph checkpointer). *(Flagged D-1 in the party review as a defer-to-post-MVP candidate — left in for now since not yet actioned; revisit if the demo script needs it.)* |

### FR-8 · Observability and Evaluation

| ID | Requirement |
|---|---|
| FR-8.1 | Trace every agent turn to MLflow; mask patient details (member ID, name, DOB, address) at the span exporter before writing. |
| FR-8.2 | Golden dataset — **see the `[NOTE FOR PM]` under Success Metric and Open Items: two competing designs exist (`eval/labelled_claims.csv` vs. `evals/datasets/*.jsonl`) and must be reconciled before this FR is buildable as written.** |
| FR-8.3 | CI gate: deterministic code checks (verification gate, policy-display gate, PII-leak check) run on every push; no model calls, no secrets in CI. |
| FR-8.4 | Every eval run exports `results.json` — per-scenario decision, code-check result, judge score, and token counts (coding + agent). |

---

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | p95 agent turn latency ≤ 4 s (text, streaming). |
| NFR-2 | **Hard gates (100%):** 0 cases created for unverified sessions · 0 policy data shown before verification · 0 patient details in logs or traces · 0 confirmation of whether an unknown member ID exists. |
| NFR-3 | Synthetic data only; no real PHI in the demo environment. |
| NFR-4 | LiteLLM abstraction over AWS Bedrock Claude; mock mode for CI. Mock mode uses fixed, scenario-keyed canned responses (deterministic replay), not a local model — CI catches prompt-shape and tool-order regressions via code checks, not mocked-LLM creativity. *(Per A-9.)* |
| NFR-5 | Two-developer team; 4-sprint demo timeline; limited AWS budget (small instances). |
| NFR-6 | Support ≥ 10 concurrent sessions in the demo environment with no cross-session data bleed (sessions keyed by `session_id`) — a reasonable floor for an investor-demo load, not a production SLA. *(Per A-6.)* |

---

## Non-Goals (Explicit)

- Not a multi-agent system — one graph, one agent, no sub-agent orchestration.
- Adult dependents filing on their own behalf (in scope only: the subscriber, or a subscriber filing for a minor dependent).
- Real clearinghouse integration (X12 270/271/837), adjudication, payments, EOBs.
- Document/photo upload, OCR, diagnosis/procedure coding (ICD-10/CPT).
- Provider portal, languages beyond English, auth beyond the verification questions, production HIPAA certification.
- Voice mode (post-MVP stretch, same graph).

---

## MVP Scope

**In:** dependent-aware member intake → coverage fetch → identity verification with callback-on-lockout → verified-only policy display → free-text claim intake + clarify loop (no hard turn cap) → confirmation → case creation with missing-fields tracking. Web chat UI. MLflow tracing + eval suite. Docker + GitHub Actions CI + AWS ECS Fargate.

**Out:** everything listed under Non-Goals.

**MVP acceptance criteria:**
- Scripted demo runs end to end on AWS.
- All hard gates pass at 100% against `evals/datasets/scenarios.jsonl`.
- Scenario outcome match ≥ 0.95 (mock) across S01–S10.
- An MLflow trace of the demo conversation is walkable by a reviewer.

---

## Open Items — needs Srimaan's call

| # | Item | Options |
|---|---|---|
| — | **Golden dataset design** | New `eval/labelled_claims.csv` (per `docs/intake-brief.md` §5a, not yet built) vs. the existing `evals/datasets/*.jsonl` + `evals/thresholds.yaml` (already built, code-check scored) — which is authoritative for FR-8.2? |
| C-1 | Audit log in MVP at all | Mary: required for the payer-trust story · John: only if it's in the demo script |
| C-3 | Audit log detail, if C-1 is yes | Hashed member ID + outcome + case ID · vs. event-only, no identifiers (current default in FR-6.4) |
| OQ-1 | Which challenge question(s) are acceptable to the target payer persona? | ZIP / employer / subscriber |
| OQ-4 | ECS Fargate or App Runner for demo compute? | — |

## Backlog (not MVP blockers)

- **A-7:** add a golden-dataset scenario proving the agent never re-asks a field already given in the free-text description — goes into whichever dataset design wins the Open Item above.
- **D-1:** session checkpoint/resume (FR-7.3) — cut to post-MVP if the demo stays under 5 minutes.
