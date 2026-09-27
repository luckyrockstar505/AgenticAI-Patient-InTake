---
title: 'DB schema, migrations & synthetic seed'
type: 'feature'
created: '2026-09-27'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: 'a4a72c5d1091a111ff6722a06b6bfdf50236a4f4'
context:
  - docs/architecture.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** There is no database schema, no migrations, and no seed data loaded into Postgres. Every MCP tool (stories 2.3–2.5) and every eval run depends on deterministic member and coverage records existing before any agent code runs.

**Approach:** Create SQLAlchemy 2.x mapped models for all tables (architecture §4 + callbacks table from A-1 party-mode decision), set up Alembic with an initial migration, and write a `make seed` CLI that loads `data/seed/members.json` and `data/seed/coverage.json` idempotently.

## Boundaries & Constraints

**Always:**
- SQLAlchemy 2.x mapped classes only (no legacy `Column`-style where avoidable).
- Alembic manages all schema changes; `make migrate` runs `alembic upgrade head`.
- `make seed` must be idempotent — running twice gives same row counts (use `INSERT ... ON CONFLICT DO NOTHING` or equivalent).
- Include the `callbacks` table (A-1 decision) and `missing_fields`/`complete` columns on `cases` (A-3 decision) — these are not in the original architecture doc but are required by party-mode decisions.
- `make eval` must exit 0 after this story (no new scenarios; existing suite stays green).
- Never create LangGraph checkpoint tables — those are `PostgresSaver.setup()` in story 3.1.

**Never:**
- No Payer mock logic in this story (story 2.2 owns that).
- No MCP tool endpoints (stories 2.3–2.5 own those).
- No Alembic autogenerate from models — write the migration SQL by hand to keep it reviewable.

## I/O & Edge-Case Matrix

| Scenario | Input | Expected Behavior |
|---|---|---|
| Fresh DB | Empty Postgres + `make migrate` | All 7 tables created, `alembic_version` at head |
| Seed on empty DB | `make seed` | 7 member rows + 7 coverage rows inserted |
| Seed twice | `make seed && make seed` | Same row counts, no duplicate key errors |
| Unknown member in coverage JSON | member_id in members but not in coverage JSON | Member row inserted, no coverage row; no crash |
| `make migrate` in CI container | Service container with `DATABASE_URL` set | Migrations run, exit 0 |

</frozen-after-approval>

## Code Map

- `mcp_tools/db/__init__.py` — already exists as stub; add `Base`, `get_engine()`, `get_session()` exports
- `mcp_tools/db/models.py` — NEW: SQLAlchemy 2.x mapped classes for all 7 tables
- `mcp_tools/db/session.py` — NEW: engine factory + `get_session()` context manager
- `mcp_tools/db/migrations/` — NEW: Alembic `env.py`, `alembic.ini`, `versions/0001_initial.py`
- `scripts/seed.py` — NEW: CLI script, reads `data/seed/members.json` + `data/seed/coverage.json`, upserts rows
- `data/seed/members.json` — EXISTS (7 personas P1–P7): verify member IDs match golden dataset
- `data/seed/coverage.json` — EXISTS: verify keyed by same member IDs
- `Makefile` — UPDATE: `seed` target calls `uv run python scripts/seed.py`; `migrate` target calls `alembic upgrade head`
- `tests/unit/test_models.py` — NEW: import models, check table names + column names (no live DB)
- `tests/integration/test_seed.py` — NEW: spin up Postgres (via compose or pytest-docker), run migrations + seed, assert row counts

## Tasks & Acceptance

**Execution:**
- [x] `mcp_tools/db/models.py` — 6 mapped classes: `Member`, `CoverageSnapshot`, `Verification`, `Case` (with `missing_fields` ARRAY + `complete` bool), `Callback`, `AuditLog`; uuid PKs
- [x] `mcp_tools/db/session.py` — `get_engine(url)` + `get_session()` async context manager; exports `Base`
- [x] `mcp_tools/db/__init__.py` — re-exports `Base`, `get_engine`, `get_session`, all model classes
- [x] `mcp_tools/db/migrations/` — Alembic init; `alembic.ini` reads `DATABASE_URL` from env; `versions/0001_initial.py` creates all 6 tables with CHECK constraints and indexes
- [x] `scripts/seed.py` — async; loads `data/seed/members.json` + `data/seed/coverage.json`; upserts via `ON CONFLICT DO NOTHING`; exits 0
- [x] `Makefile` — `seed` target calls `uv run python scripts/seed.py`; `migrate` target calls `alembic upgrade head`
- [x] `tests/unit/test_models.py` — 16 tests; all pass without live DB
- [x] `tests/integration/test_seed.py` — 5 integration tests; skipped if `DATABASE_URL` not set; asserts 6 members (P6 intentionally absent), idempotency verified

**Acceptance Criteria:**
- Given a clean Postgres, when `make migrate` runs, then all 7 tables exist and `alembic_version` is at head
- Given `make seed` runs on a fresh DB, then exactly 6 member rows exist (P6 is the not-found persona — intentionally absent from seed file)
- Given `make seed` runs twice, then row counts are unchanged (idempotent)
- Given `make test` runs, then unit model tests pass without a live DB
- Given `make eval` runs, then it exits 0 (no regressions)

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Verification

**Commands:**
- `uv run pytest tests/unit/test_models.py -v` -- expected: all pass, no live DB needed
- `uv run pytest tests/integration/test_seed.py -v` -- expected: 7 members, idempotent
- `uv run pytest tests/unit -v` -- expected: all unit tests pass (32+ from prior stories)
- `uv run ruff check . && uv run mypy . --ignore-missing-imports` -- expected: 0 errors
