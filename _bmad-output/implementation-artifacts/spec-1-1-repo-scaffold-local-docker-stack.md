---
title: 'Repo scaffold & local Docker stack'
type: 'chore'
created: '2026-09-27'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'e0cbc6779d6afe7b448f7c4d674fa1a7d35081ac'
context:
  - docs/architecture.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repo is a blank slate — no package structure, no runnable services, and no shared environment. Both tracks (Bharath on Agent, Srimaan on Platform) are blocked until there is a single command that starts the full local stack.

**Approach:** Scaffold the full repo layout from architecture §2, write Dockerfiles and docker-compose for all four services, add the Makefile, `.env.example`, pinned `pyproject.toml`, and minimal placeholder modules so `make up && curl /healthz` returns 200 on a fresh clone.

## Boundaries & Constraints

**Always:**
- Python 3.12, uv-managed single workspace. All deps pinned in `pyproject.toml` using the library list from architecture §12.
- One base image: `python:3.12-slim`, non-root user (`appuser`), multi-stage build.
- `docker-compose.yml` services: `api` (:8000), `mcp-tools` (:8765), `postgres` (:5432), `mlflow` (:5000) on shared network `claims-net`.
- `.env` must be git-ignored; `.env.example` must match every key in architecture §9.
- `make up` / `make down` / `make test` / `make eval` / `make lint` / `make seed` / `make logs` must all exist (some may be stubs that exit 0).
- `make eval` must exit 0 even with an empty eval suite (no scenarios yet).
- README quickstart: clone → `cp .env.example .env` → `make up` → `curl /healthz` succeeds in < 10 minutes on a clean machine.

**Never:**
- No real application logic yet — all modules are placeholders with the correct import structure.
- No LangGraph, LLM calls, or MCP tools in this story (those are 1.3 / 2.x).
- No Alembic migrations (2.1 owns the schema).
- No production infra or AWS resources.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Healthz happy path | `GET /healthz` after `make up` | `{"status": "ok", "db": "ok", "mcp": "ok"}` | N/A |
| MCP ping | Call `ping` tool on mcp-tools | `{"pong": true}` | N/A |
| `make test` empty suite | No test files yet | Exit 0, "no tests ran" | N/A |
| Dirty `.env` missing key | `make up` with missing `DATABASE_URL` | Compose validation error before container starts | Compose built-in |

</frozen-after-approval>

## Code Map

All files are NEW (blank repo). The architecture §2 layout is the source of truth.

- `pyproject.toml` — single uv workspace, Python 3.12, all pinned deps from arch §12, ruff + mypy + pytest config
- `docker-compose.yml` — four services with healthchecks, `claims-net` bridge network, env_file `.env`
- `Dockerfile.api` — multi-stage, `python:3.12-slim`, `uv sync --frozen`, non-root `appuser`, exposes 8000
- `Dockerfile.mcp` — same pattern, exposes 8765
- `Makefile` — all 8 targets; `up`/`down` wrap compose; `test` runs pytest; `eval` runs `python -m evals.runner` (exits 0 if no scenarios)
- `.env.example` — all keys from architecture §9 with safe local defaults
- `.gitignore` — `.env`, `__pycache__`, `.mypy_cache`, `mlflow.db`, `mlruns/`, `.pytest_cache`
- `agent/__init__.py`, `agent/llm.py` (stub), `agent/state.py` (stub), `agent/graph.py` (stub), `agent/mcp_client.py` (stub)
- `mcp_tools/__init__.py`, `mcp_tools/server.py` (stub FastMCP with `ping` tool)
- `api/__init__.py`, `api/main.py` (FastAPI app with `/healthz`), `api/routes/__init__.py`
- `shared/__init__.py`, `shared/schemas.py` (stub `ClaimDraft` placeholder)
- `observability/__init__.py`, `observability/redaction.py` (stub), `observability/tracing.py` (stub)
- `evals/__init__.py`, `evals/runner.py` (stub, exits 0), `evals/datasets/` (empty dir with `.gitkeep`)
- `tests/__init__.py`, `tests/unit/test_health.py` (TestClient hits `/healthz`), `tests/integration/` (empty with `.gitkeep`)
- `data/seed/` (empty with `.gitkeep`)
- `CLAUDE.md` — rules for Claude Code agents on this repo
- `README.md` — quickstart only

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` — create uv workspace, pin all deps from arch §12, configure ruff (line-length=100, target=py312), mypy (strict=false, python_version=3.12), pytest (testpaths=["tests"])
- [x] `Dockerfile.api` + `Dockerfile.mcp` — multi-stage python:3.12-slim, non-root appuser, `uv sync --frozen`, COPY only needed dirs
- [x] `docker-compose.yml` — four services with healthchecks (`/healthz` for api, `ping` for mcp, pg_isready for postgres, wget for mlflow), `claims-net` bridge, env_file `.env`
- [x] `Makefile` — all 8 targets; `up`/`down` use `docker compose`; `test` is `pytest tests/unit`; `eval` is `python -m evals.runner`; `lint` is `ruff check . && mypy .`; `seed` is a stub `echo "seed: TBD"` exit 0
- [x] `api/main.py` — FastAPI app, `GET /healthz` hits DB (ping) and MCP (ping tool), returns `{"status":"ok","db":"ok","mcp":"ok"}`
- [x] `mcp_tools/server.py` — `FastMCP("claims-tools")` with one `ping()` tool returning `{"pong": true}`; transport streamable-http on `:8765/mcp`
- [x] All stub package files — `__init__.py` with correct relative imports, placeholder classes/functions matching arch §2 signatures
- [x] `.env.example`, `.gitignore`, `CLAUDE.md`, `README.md` — per constraints above
- [x] `tests/unit/test_health.py` — FastAPI TestClient asserts `/healthz` returns 200 with `{"status":"ok"}`

**Acceptance Criteria:**
- Given a clean clone with `cp .env.example .env`, when `make up` runs, then all four containers start healthy within 60s
- Given containers are up, when `curl localhost:8000/healthz`, then `{"status":"ok","db":"ok","mcp":"ok"}` is returned
- Given containers are up, when the MCP `ping` tool is called, then `{"pong": true}` is returned
- Given `make test` runs, then it exits 0 (even with only one unit test)
- Given `make eval` runs, then it exits 0 with "no scenarios" output (empty suite)
- Given `make lint` runs, then ruff and mypy both pass on the stub codebase

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `make up` -- expected: all four containers healthy (no restart loops)
- `curl -s localhost:8000/healthz | python3 -m json.tool` -- expected: `{"status": "ok", "db": "ok", "mcp": "ok"}`
- `make test` -- expected: exit 0, ≥1 test passed
- `make eval` -- expected: exit 0, "no scenarios" message
- `make lint` -- expected: exit 0, no ruff or mypy errors
- `make down` -- expected: all containers removed cleanly
