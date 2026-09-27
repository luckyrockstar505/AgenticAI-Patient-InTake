# Epic 5: API & Chat UI

**Track:** B  
**Goal:** Expose the agent over FastAPI with streaming and a minimal ES5 web chat UI for the demo.

## Stories

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| [5.1](../stories/5.1.fastapi-session-chat-case-endpoints.md) | FastAPI session/chat/case endpoints | B | 3.1 | M |
| [5.2](../stories/5.2.web-chat-ui.md) | Web chat UI | B | 5.1 | S |

## Epic done when

- All stories Done (merged, QA PASS)
- `make test` and `make eval` green on main
- Demo of the epic's capability recorded in the PR of its last story
