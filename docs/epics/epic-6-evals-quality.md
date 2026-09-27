# Epic 6: Evals & Quality

**Track:** A/B  
**Goal:** Make agent quality measurable and enforce it in CI: golden conversations, scorers, safety scenarios.

## Stories

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| [6.1](../stories/6.1.golden-dataset-eval-harness.md) | Golden dataset & eval harness | A | 3.1, 1.4 | M |
| [6.2](../stories/6.2.ci-eval-gate-nightly-bedrock-evals.md) | CI eval gate & nightly Bedrock evals | B | 6.1, 1.2 | S |
| [6.3](../stories/6.3.red-team-safety-scenarios.md) | Red-team & safety scenarios | A | 6.1 | S |

## Epic done when

- All stories Done (merged, QA PASS)
- `make test` and `make eval` green on main
- Demo of the epic's capability recorded in the PR of its last story
