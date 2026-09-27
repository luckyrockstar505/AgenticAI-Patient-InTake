# Epic 2 Context: Data & MCP Tools

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Provide the database schema, synthetic seed data, mock payer service, and FastMCP tool server so that the LangGraph agent has deterministic data to work against and all MCP tool contracts are satisfied. This epic is the platform foundation for Epics 3 and 4 — no agent node can be tested without it.

## Stories

- Story 2.0: Golden dataset `eval/labelled_claims.csv` ✅ Done (Bharath)
- Story 2.1: DB schema, migrations & synthetic seed
- Story 2.2: Mock payer eligibility service
- Story 2.3: FastMCP coverage tools (`fetch_coverage`, `get_policy_view`)
- Story 2.4: FastMCP verification tools (`start_verification`, `check_answer`)
- Story 2.5: FastMCP case & callback tools (`create_case`, `request_callback`)

## Requirements & Constraints

- **Postgres only.** All tables live in Postgres (no SQLite except for integration test fixtures). LangGraph checkpoint tables are created by `PostgresSaver.setup()` in story 3.1 — never by Alembic.
- **`make seed` idempotent.** Running twice must produce the same row counts. Seed data lives in `data/seed/members.json` and `data/seed/coverage.json` (already present).
- **Callbacks table required.** Story 2.1 must create the `callbacks` table (A-1 party-mode decision) — it is not in the original architecture §4 but was added in the workshop session.
- **`make eval` stays green.** No new eval scenarios in 2.1 or 2.2; must not break existing suite.
- **Seed personas P1–P7:** active member (P1), 3-fail lockout target (P2), HDHP (P3), spouse dependent (P4), terminated (P5), not-found ID (P6), deductible met (P7). The existing `data/seed/members.json` already has these — extend only if needed.
- **`make migrate` works in compose and CI service container.** Connection via `DATABASE_URL` env var.

## Technical Decisions

**Database schema** (architecture §4 + A-1 fix):

```sql
members(id uuid pk, member_id text unique, first_name, last_name, dob date,
        zip text, employer_group text, subscriber_name text, relationship text,
        payer_id text, created_at)
coverage_snapshots(id uuid pk, session_id text, member_id text, payload jsonb,
        source text, status text CHECK('unverified','verified','discarded'), fetched_at)
verifications(id uuid pk, session_id text, member_id text,
        status text CHECK('PENDING','PASSED','FAILED','LOCKED'),
        attempts int, asked_question_ids text[], created_at, updated_at)
cases(id uuid pk, case_number text unique, session_id text, member_id text,
        snapshot_id uuid fk, verification_id uuid fk, claim jsonb,
        missing_fields text[], complete bool default true,   -- A-3 fix
        status text default 'NEW', created_at)
callbacks(id uuid pk, session_id text, member_id_hash text,  -- A-1 fix
        contact_number text, status text default 'PENDING', created_at)
audit_log(id bigserial pk, session_id text, event text, detail jsonb, created_at)
```

**Stack:** SQLAlchemy 2.x mapped classes (not legacy), Alembic for migrations, `mcp_tools/db/models.py` for models, `mcp_tools/db/session.py` for `get_session()` + engine factory.

**MCP contracts:** `docs/contracts/mcp-tools.md` is source of truth — tool signatures must match exactly. 2.1 only builds the DB layer; tools come in 2.3–2.5.

**Payer mock:** reads `data/seed/coverage.json` keyed by `member_id`. Story 2.2 wraps it in a `PayerClient` protocol. 2.1 does not implement payer logic.

## Cross-Story Dependencies

- 2.1 must land before 2.2 (payer mock needs the `coverage_snapshots` model)
- 2.3, 2.4, 2.5 all import from `mcp_tools/db/models.py` — any schema change there requires updating them
- Story 3.1 (LangGraph skeleton) creates LangGraph checkpoint tables via `PostgresSaver.setup()` — do NOT pre-create these tables in Alembic
- `eval/labelled_claims.csv` personas (P1–P7) must match seed data member IDs exactly for eval runs to resolve
