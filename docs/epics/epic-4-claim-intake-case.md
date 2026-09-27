# Epic 4: Claim Intake & Case

**Track:** A  
**Goal:** Turn a natural-language claim description into a complete ClaimDraft through targeted follow-ups, confirm it, and create a case.

## Stories

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| [4.1](../stories/4.1.claim-schema-nl-extraction.md) | Claim schema & NL extraction | A | 1.3 | M |
| [4.2](../stories/4.2.gap-detection-clarify-loop.md) | Gap detection & clarify loop | A | 4.1, 3.1 | M |
| [4.3](../stories/4.3.confirm-create-case.md) | Confirm & create case | A | 4.2, 2.5 | S |
| [4.4](../stories/4.4.human-handoff-cancel-paths.md) | Human handoff & cancel paths | A | 3.2 | S |

## Epic done when

- All stories Done (merged, QA PASS)
- `make test` and `make eval` green on main
- Demo of the epic's capability recorded in the PR of its last story
