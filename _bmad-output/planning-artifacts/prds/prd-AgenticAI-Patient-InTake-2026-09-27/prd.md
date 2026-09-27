---
title: Claims Intake Agent — PRD
status: draft
created: 2026-09-27
updated: 2026-09-27
---

# Claims Intake Agent — Product Requirements Document

> MVP only · One agent · Source: `docs/intake-brief.md` (updated 2026-09-27)

---

## Goal & Success Metric

**Goal.** Replace the manual claim intake front door with a conversational AI agent that verifies a member's identity, shows their coverage, and turns a free-text claim description into a complete, auditable, structured case ready for backend processing.

**Success metric.** ≥ 90% of 20 human-labelled scenarios in `eval/labelled_claims.csv` produce the correct outcome — correct structured case OR correct non-case result (verification lockout, human handoff, cancel). Measured via code checks + LLM judge per scenario. All three hard gates hold at 100%.

**Counter-metric.** LLM judge flags ≥ 10% of sessions as confusing, repetitive, or untrustworthy → UX / prompt regression.

---

## User Journey

**Maria, 34 — subscriber filing a claim for her daughter's ER visit.**

1. Maria opens the web chat. She types her member ID and full name.
2. The agent replies: "Got it — just a moment while I look up your coverage." Coverage fetches silently behind the scenes.
3. The agent asks for her date of birth and ZIP code to confirm her identity.
4. After she answers correctly, her plan, deductible, and copays appear — nothing was shown before this moment.
5. "What happened? Tell me in your own words." Maria describes the ER visit.
6. One question: "Do you have the provider's name or facility?" She types it.
7. The agent shows a structured summary. Maria reads it and types "Yes, submit."
8. "Done — your case number is CLM-20261001 and its status is NEW. You'll hear from the claims team within 5 business days."

Total elapsed: under 3 minutes.

**Non-happy paths in scope:**
- Verification fails 3 times → session locks, routes to human, no hint about whether the ID exists.
- Member requests human handoff mid-flow → immediate warm transfer message.
- Member cancels after claim intake → confirm discard, no case created.
- Claim description is missing required fields → clarify loop (max 5 turns, one question at a time).

---

## Functional Requirements

### FR-1 · Member Identification

| ID | Requirement |
|---|---|
| FR-1.1 | Accept member ID (9-digit alphanumeric) and full name via text. |
| FR-1.2 | Validate member ID format before any fetch; reject with a plain-language message on bad format — no hint whether the ID exists in the system. |

### FR-2 · Coverage Fetch

| ID | Requirement |
|---|---|
| FR-2.1 | Call the payer MCP tool (`fetch_coverage`) with the member ID; store the snapshot with status `unverified`. |
| FR-2.2 | Never expose policy data to the member until verification status is `verified`. |
| FR-2.3 | If the payer tool returns no record, lock the session and route to human — same behaviour as verification failure; no differential error message. |

### FR-3 · Identity Verification

| ID | Requirement |
|---|---|
| FR-3.1 | Challenge with date of birth + one of: ZIP code, employer name, or subscriber ID. |
| FR-3.2 | Evaluate each answer via a deterministic tool (`verify_answer`); LLM never makes or overrides the pass/fail decision. |
| FR-3.3 | After 3 consecutive failures: lock session, log lockout, route to human agent queue. |
| FR-3.4 | Never hint to the member which answer was wrong or whether the member ID exists. |

### FR-4 · Policy Display

| ID | Requirement |
|---|---|
| FR-4.1 | After `verified`: display plan name, effective dates, deductible (met / remaining), OOP max (met / remaining), and relevant copays. |
| FR-4.2 | All values rendered directly from the coverage snapshot — no LLM-generated policy text; model may only compose the framing sentence. |

### FR-5 · Claim Intake

| ID | Requirement |
|---|---|
| FR-5.1 | Invite free-text claim description; extract structured fields: date of service, place of service, provider name and NPI (if given), reason/diagnosis description, services rendered, amounts (if known), accident-related flag, other-insurance flag. |
| FR-5.2 | Ask one targeted clarification question per missing or ambiguous required field; maximum 5 clarification turns per session. |
| FR-5.3 | Never ask for a field the member already provided in the same session. |
| FR-5.4 | [ASSUMPTION] Required fields for case creation: date of service, place of service, provider name, diagnosis/reason. Amounts and NPI are optional-but-requested. |

### FR-6 · Confirmation and Case Creation

| ID | Requirement |
|---|---|
| FR-6.1 | Present a complete structured summary of extracted claim fields before creation. |
| FR-6.2 | Create the case record only after explicit member confirmation (affirmative reply). |
| FR-6.3 | Return case number and status `NEW`; never let the LLM decide whether to create the case — `create_case` tool owns that. |
| FR-6.4 | Write one audit log entry per session capturing member ID (hashed), verification outcome, and case ID (or null). |

### FR-7 · Control Flow

| ID | Requirement |
|---|---|
| FR-7.1 | Offer cancel at any turn; confirm before discarding; no case created on cancel. |
| FR-7.2 | Offer human handoff at any turn (member-initiated or system-initiated on lockout). |
| FR-7.3 | Resume a checkpointed session without re-asking fields already collected (Postgres LangGraph checkpointer). |

### FR-8 · Observability and Evaluation

| ID | Requirement |
|---|---|
| FR-8.1 | Trace every agent turn to MLflow; mask patient details (member ID, name, DOB, address) at the span exporter before writing. |
| FR-8.2 | Golden dataset: `eval/labelled_claims.csv` — 20+ rows, human-labelled by ops staff, never by the agent; 10-row holdout withheld until final eval. Columns: `input`, `expected_answer`, `expected_tools`, `why`. |
| FR-8.3 | CI gate: deterministic code checks (verification gate, policy-display gate, PII-leak check) run on every push; no model calls, no secrets in CI. |
| FR-8.4 | Every eval run exports `results.json` — per-scenario decision, code-check result, judge score, and token counts (coding + agent). |

---

## Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | p95 agent turn latency ≤ 4 s (text, streaming). |
| NFR-2 | **Hard gates (enforced by eval, must be 100%):** 0 cases created for unverified sessions · 0 policy data shown before verification · 0 patient details in logs or traces. |
| NFR-3 | Synthetic data only; no real PHI in the demo environment. |
| NFR-4 | LiteLLM abstraction over AWS Bedrock Claude; mock mode for CI (no real model calls). |
| NFR-5 | Two-developer team; 4-sprint demo timeline; limited AWS budget (small instances). |

---

## MVP Scope

**In:** member ID intake → coverage fetch → identity verification → policy display → free-text claim intake + clarify loop → confirmation → case creation. Web chat UI. MLflow tracing + eval suite. Docker + GitHub Actions CI + AWS ECS Fargate.

**Out:** voice input, real clearinghouse integration (X12 270/271/837), adjudication, payments, EOBs, document/photo upload, OCR, ICD-10/CPT coding, provider portal, multi-language, production HIPAA certification. Demo uses synthetic data only.

**MVP acceptance criteria:**
- Scripted demo runs end to end on AWS.
- All three hard gates pass at 100% on the build set (20 scenarios).
- A holdout eval run (10 scenarios) scores ≥ 90%.
- An MLflow trace of the demo conversation is walkable by a reviewer.

---

## Open Questions

| # | Question | Owner | Condition to resolve |
|---|---|---|---|
| OQ-1 | Which challenge questions are acceptable to the target payer persona? | Srimaan | Before FR-3 build |
| OQ-2 | Should dependents file independently, or only through the subscriber? | Srimaan | Before FR-1/5 build |
| OQ-3 | What ops-only case fields exist that members cannot provide? | Srimaan | Before FR-5.4 assumption is locked |
| OQ-4 | ECS Fargate or App Runner for demo compute? | Team | Before infra story |
