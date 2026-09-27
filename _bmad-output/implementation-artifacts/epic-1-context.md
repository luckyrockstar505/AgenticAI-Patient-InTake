# Epic 1 Context: Foundation & DevEx

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Stand up the repo, local Docker stack, CI pipeline, LLM gateway, and MLflow tracing so both tracks (Bharath — Agent, Srimaan — Platform) can build and test independently from day one. This epic has no user-facing value on its own; its output is the trusted, reproducible baseline every later story depends on.

## Stories

- Story 1.1: Repo scaffold & local Docker stack
- Story 1.2: CI pipeline — lint, type, test, build *(deferred — post workshop)*
- Story 1.3: LLM gateway via LiteLLM (Bedrock + mock)
- Story 1.4: MLflow tracing baseline & PHI redaction

## Requirements & Constraints

- Python 3.12, managed by `uv`. Single workspace `pyproject.toml`. Deps pinned at story 1.1.
- Four local services via Docker Compose: `api` (:8000), `mcp-tools` (:8765), `postgres` (:5432), `mlflow` (:5000). All must pass healthchecks.
- `GET /healthz` on `api` must confirm db + mcp reachability (not just process-alive).
- LLM calls must never go to a real model in CI. `LLM_MODE=mock` must return scripted YAML responses keyed by `purpose` + input hash/regex — no network calls, no AWS credentials required.
- PHI (member ID, name, DOB, ZIP, phone, NPI) must be masked at the span exporter level before anything reaches MLflow. A `make eval` PHI-leak check must pass at 0 leaked fields.
- No static AWS keys anywhere. Local dev uses `AWS_PROFILE`; AWS deploy uses IAM task roles.
- `make eval` must stay green throughout this epic (no eval scenarios yet, so the empty suite must exit 0).

## Technical Decisions

**Repo layout** (`claims-intake-agent/`):
```
agent/          # Track A — LangGraph agent, nodes, prompts, LLM gateway
mcp_tools/      # Track B — FastMCP server, tools, payer mock, DB
api/            # Track B — FastAPI app, routes, static chat UI
shared/         # Both — ClaimDraft schema, contract models (imported by both tracks)
observability/  # Both — redaction.py, tracing.py
evals/          # Both — datasets, runner, scorers
tests/          # unit/, integration/, fakes/
data/seed/      # Synthetic members and coverage (never real PHI)
infra/          # AgentCore deploy config (replaces Terraform)
```

**LLM gateway** (`agent/llm.py`):
- `complete(messages, *, purpose, schema=None) → LLMResult` wraps `litellm.completion`.
- `LLM_MODE=mock` → `MockLLM` reads `tests/fakes/llm_scripts/*.yaml`.
- `LLM_MODE=bedrock` → LiteLLM to AWS Bedrock Claude. Model IDs from env (`LLM_MODEL_DEFAULT`, `LLM_MODEL_FAST`).
- Retries: 2 with exponential backoff on throttling; 20s timeout.

**Docker images**: `python:3.12-slim` base; install with `uv sync --frozen`; non-root user; multi-stage build.

**MLflow local**: `ghcr.io/mlflow/mlflow` with SQLite backend + local artifact volume. In AWS: ECS + S3 artifact store.

**Key libraries** (pin in pyproject.toml): `langgraph`, `fastmcp`, `litellm`, `mlflow>=3.x`, `fastapi`, `uvicorn`, `sse-starlette`, `sqlalchemy>=2`, `alembic`, `psycopg[binary]`, `pydantic>=2`, `rapidfuzz`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `uv`.

**Makefile targets**: `up`, `down`, `lint`, `fmt`, `typecheck`, `test`, `eval`, `seed`, `logs`.

## Cross-Story Dependencies

- 1.3 (LLM gateway) and 1.4 (MLflow) both depend on 1.1 completing first (Docker stack up, repo layout established, deps pinned).
- Story 3.1 (LangGraph skeleton) depends on 1.3 for `complete()`.
- Story 1.4 (MLflow) must establish the redaction layer before any PHI-adjacent code lands — 2.4 and 3.3 both read member data.
- 1.2 (CI) is deferred; existing `make test` must exit 0 even with an empty test suite so the gate is ready to add tests into.
