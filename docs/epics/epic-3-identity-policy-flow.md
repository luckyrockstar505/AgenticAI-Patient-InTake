# Epic 3: Identity & Policy Flow

**Track:** A  
**Goal:** Build the LangGraph flow that captures identity, verifies the member deterministically, and reveals policy details only after verification.

## Stories

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| [3.1](../stories/3.1.langgraph-skeleton-state-checkpointer.md) | LangGraph skeleton, state & checkpointer | A | 1.3 | M |
| [3.2](../stories/3.2.intent-classifier-global-router.md) | Intent classifier & global router | A | 3.1 | M |
| [3.3](../stories/3.3.intake-node-member-id-name.md) | Intake node (member ID + name) | A | 3.1 | S |
| [3.4](../stories/3.4.verify-node-challenge-loop-lockout.md) | Verify node: challenge loop & lockout | A | 3.3, 2.4 | M |
| [3.5](../stories/3.5.policy-display-node-verified-gate.md) | Policy display node (verified gate) | A | 3.4, 2.3 | S |

## Epic done when

- All stories Done (merged, QA PASS)
- `make test` and `make eval` green on main
- Demo of the epic's capability recorded in the PR of its last story
