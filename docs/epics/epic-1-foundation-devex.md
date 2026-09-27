# Epic 1: Foundation & DevEx

**Track:** B  
**Goal:** Stand up the repo, local stack, CI, LLM gateway and tracing so both tracks can build in parallel from day one.

## Stories

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| [1.1](../stories/1.1.repo-scaffold-local-docker-stack.md) | Repo scaffold & local docker stack | B | — | M |
| [1.2](../stories/1.2.ci-pipeline-lint-type-test-build.md) | CI pipeline (lint, type, test, build) | B | 1.1 | S |
| [1.3](../stories/1.3.llm-gateway-via-litellm-bedrock-mock.md) | LLM gateway via LiteLLM (Bedrock + mock) | A | 1.1 | S |
| [1.4](../stories/1.4.mlflow-tracing-baseline-phi-redaction.md) | MLflow tracing baseline & PHI redaction | B | 1.1 | M |

## Epic done when

- All stories Done (merged, QA PASS)
- `make test` and `make eval` green on main
- Demo of the epic's capability recorded in the PR of its last story
