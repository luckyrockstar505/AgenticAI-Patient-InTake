# MCP Tool Contracts — `claims-tools` v1

> Source of truth for the seam between Track A (agent) and Track B (tools).
> Changing a contract = PR that updates this file **first**, reviewed by both devs, with a version bump.
> Server: FastMCP, transport `streamable-http`, `MCP_URL=http://mcp-tools:8765/mcp`.
> All tools return JSON objects. Errors are returned as `{"ok": false, "error": {"code": "...", "message": "..."}}` — tools never raise to the client for business errors.

## Common

```json
{"ok": true, "data": { ... }}
{"ok": false, "error": {"code": "NOT_VERIFIED|NOT_FOUND_OR_MISMATCH|LOCKED|VALIDATION|INTERNAL", "message": "safe, non-PHI text"}}
```

Every tool takes `session_id: str` and writes an `audit_log` row.

---

## 1. `fetch_coverage`

Fetches eligibility/coverage from the (mock) payer and stores a snapshot with status `unverified`.

**Input**
```json
{"session_id": "s-123", "member_id": "ABC123456789"}
```
**Output (ok)**
```json
{"ok": true, "data": {"snapshot_id": "uuid", "found": true}}
```
**Output (unknown ID)** — deliberately indistinguishable to the member; agent shows generic message.
```json
{"ok": true, "data": {"snapshot_id": null, "found": false}}
```
Notes: payload is **not** returned to the agent. Audit: `coverage_fetched`.

## 2. `start_verification`

Creates/returns the verification record and performs the identity pre-checks it can do with what's known.

**Input**
```json
{"session_id": "s-123", "member_id": "ABC123456789", "full_name": "Jane Q Doe"}
```
**Output**
```json
{"ok": true, "data": {"verification_id": "uuid", "name_match": true, "next_question": {"id": "dob", "prompt_hint": "date_of_birth"}}}
```
- `name_match` uses rapidfuzz token-sort ratio ≥ 90 against first+last name. A mismatch still returns `next_question` (no enumeration) but counts as a failed attempt.
- `prompt_hint` values: `date_of_birth`, `zip_code`, `employer_group`, `subscriber_name`. The agent turns the hint into natural wording.

## 3. `check_answer`

**Input**
```json
{"session_id": "s-123", "verification_id": "uuid", "question_id": "dob", "answer": "March 4 1985"}
```
**Output**
```json
{"ok": true, "data": {"status": "PENDING|PASSED|FAILED|LOCKED", "attempts": 1, "remaining_attempts": 2,
                      "next_question": {"id": "zip", "prompt_hint": "zip_code"} }}
```
Rules:
- DOB normalized with `dateparser`-style parsing (server side); ZIP = first 5 digits; employer/subscriber = fuzzy ≥ 85.
- Pass = name_match AND dob correct AND 1 challenge correct.
- Any wrong answer → attempts+1; at `MAX_VERIFY_ATTEMPTS` → `LOCKED` (audit `verification_locked`).
- On `PASSED` the snapshot status flips to `verified` (audit `verification_passed`).
- Expected answers are never returned.

## 4. `get_policy_view`

**Input**
```json
{"session_id": "s-123", "verification_id": "uuid"}
```
**Output (ok)** — only when verification `PASSED`, else `NOT_VERIFIED`.
```json
{"ok": true, "data": {
  "plan_name": "Silver PPO 2500", "plan_type": "PPO", "group_name": "Acme Corp",
  "effective_date": "2026-01-01", "termination_date": "2026-12-31", "status": "active",
  "network": "in-network required for full benefits",
  "deductible": {"individual": 2500, "met": 800, "remaining": 1700},
  "oop_max": {"individual": 7000, "met": 1200, "remaining": 5800},
  "copays": {"pcp": 25, "specialist": 50, "urgent_care": 75, "er": 300},
  "coinsurance_pct": 20,
  "coverage_period": {"start": "2026-01-01", "end": "2026-12-31"}
}}
```
Audit: `policy_viewed`.

## 5. `create_case`

**Input**
```json
{"session_id": "s-123", "verification_id": "uuid", "claim": { /* ClaimDraft JSON, all required fields present */ }}
```
**Output**
```json
{"ok": true, "data": {"case_number": "CLM-20260927-00042", "status": "NEW"}}
```
Server-side validation: verification `PASSED` (else `NOT_VERIFIED`); required fields present; `date_of_service` within coverage period and not in future (else `VALIDATION` with `fields: [...]`). Idempotent per `session_id` (second call returns same case). Audit: `case_created`.

## 6. `get_case`

**Input** `{"case_number": "CLM-20260927-00042"}` → `{"ok": true, "data": {case…}}` (ops/demo view).

## 7. `end_session`

Closes a session server-side: discards `unverified` snapshots, writes audit.

**Input** `{"session_id": "s-123", "reason": "cancelled|handoff_user|handoff_locked|handoff_clarify_cap|handoff_error|completed"}`
**Output** `{"ok": true, "data": {"closed": true}}`

Audit: `session_ended` with reason. Idempotent.

---

## Change log

| Version | Date | Change | Approved by |
|---|---|---|---|
| 1.0 | 2026-09-27 | Initial contracts | A, B |
