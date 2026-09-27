---
type: party-mode-review
date: 2026-09-27
participants: Mary (Analyst), John (PM), Winston (Architect), Sally (UX Designer)
artifact: prd.md
status: open
---

# Party Mode Review — Claims Intake Agent PRD

> Findings from the Mary / John / Winston / Sally round-table, 2026-09-27.
> Each item is tagged with a priority and an owner action.

---

## Action Items (resolve before epics/stories)

| # | Finding | Raised by | Priority | Action |
|---|---|---|---|---|
| A-1 | **FR-9 missing: human handoff experience** — what context transfers to the human agent, what Maria sees, whether she has to repeat her member ID | Sally + John | 🔴 High | Add FR-9 to `prd.md` |
| A-2 | **OQ-2 (dependents) is a scope question, not an open question** — if out of scope, say so explicitly; if in scope, FR-1.1 and FR-5.1 change | Mary | 🔴 High | Resolve OQ-2 as In/Out scope, update §MVP Scope |
| A-3 | **FR-5.2: "max 5 clarification turns" is an invented number with no exit condition** — unspecified what happens after 5 turns (lock? handoff? partial case?) | Winston | 🔴 High | Replace with "escalate to human if required fields missing after clarify loop; loop length is a tunable parameter" |
| A-4 | **FR-5.4 `[ASSUMPTION]` must be resolved before build** — if required fields list is wrong, every claim-extraction story is built against the wrong spec | Winston | 🔴 High | Confirm required fields with ops/Srimaan, remove `[ASSUMPTION]` tag |
| A-5 | **Add state names table** — "unverified," "verified," "locked" appear in prose but no single source of truth; two devs will invent incompatible models | Winston | 🟡 Medium | Add 4–5 row state table to prd.md (state name, trigger, exits) |
| A-6 | **Add NFR: session/rate concurrency** — no spec for simultaneous sessions; demo falls over if pounded during investor meeting | John | 🟡 Medium | Add NFR-6 with a reasonable concurrent-session target |
| A-7 | **Add golden dataset scenario for "no repeat questions"** — FR-5.3 promises it but no labelled eval case enforces it | Sally | 🟡 Medium | Add scenario to `eval/labelled_claims.csv` design: member gives provider in description → agent must not ask again |
| A-8 | **Add competitive context sentence** — PRD has no line drawing against Olive AI, Waystar, Infinitus; payer PM can't tell why they'd choose this | Mary | 🟡 Medium | Add 1–2 sentence competitive context after Goal section |
| A-9 | **Mock mode design unspecified** — canned responses vs. local model matters for test quality; a perfect mock hides real-model failures | Winston | 🟡 Medium | Add NFR or note clarifying mock strategy |

---

## Items to Defer (not MVP blockers)

| # | Finding | Raised by | Defer condition |
|---|---|---|---|
| D-1 | FR-7.3 (session checkpoint/resume) — demo is 3 min, nobody resumes mid-claim; cut to post-MVP | John | Revisit if demo runs > 5 min |
| D-2 | FR-6.4 audit log detail (hashed member ID) — *contested*: Mary argues it's core to the payer value prop; John says only log if you demo it | John vs. Mary | Resolve: keep if audit trail is in the demo script |

---

## Contested Items (need Srimaan's call)

| # | Tension | Position A | Position B |
|---|---|---|---|
| C-1 | Audit log in MVP | Mary: cutting it amputates the payer trust story | John: only include if it's in the demo script |
| C-2 | State machine location | Winston: state names table belongs in prd.md | Mary: state diagram belongs in architecture doc |
| C-3 | Audit log detail | Include hashed member ID + verification outcome + case ID | Log event only, no member identifiers in demo env |

---

## Verbatim Quotes Worth Keeping

> *"If you demo without a walkable audit trail, you've cut the thing that closes the room."* — Mary

> *"You've built verification theater — she'll hit lockout and call the contact center and give her member ID again from scratch, which is exactly the problem you said you were solving."* — Sally

> *"Five is a number you made up."* — Winston on FR-5.2

---

## Next Step

Resolve A-1 through A-4 first (PRD story-boundary blockers), then A-5 through A-9 (sharpening). Log each resolution via:

```
uv run _bmad/scripts/memlog.py append \
  --workspace _bmad-output/planning-artifacts/prds/prd-AgenticAI-Patient-InTake-2026-09-27 \
  --type decision --text "<what was decided and why>"
```
