# Architecture — Claims Intake Agent

> BMAD artifact · Architect output · Version 1.0 · Inputs: `docs/prd.md`
> Contracts: `docs/contracts/mcp-tools.md` · Intents: `docs/intents.md` · Tracing: `docs/tracing.md`

## 1. System context

```
 Browser (chat UI, ES5)  ──HTTPS/SSE──►  api  (FastAPI + LangGraph agent)
                                          │   ├── LiteLLM ──► AWS Bedrock (Claude)   [LLM_MODE=bedrock]
                                          │   │                └► MockLLM             [LLM_MODE=mock]
                                          │   ├── MCP client ──streamable-http──► mcp-tools (FastMCP)
                                          │   │                                     ├── mock payer (in-proc module)
                                          │   │                                     └── Postgres (SQLAlchemy)
                                          │   ├── LangGraph checkpointer ─────────► Postgres
                                          │   └── MLflow tracing (redacted) ──────► mlflow server
 (stretch) Browser mic ──WS──► api/voice ──► Amazon Transcribe streaming / Amazon Polly
```

Containers (docker-compose locally, ECS Fargate in AWS): `api`, `mcp-tools`, `postgres` (RDS in AWS), `mlflow` (ECS service + S3 artifacts in AWS).

## 2. Repository layout

```
claims-intake-agent/
├── CLAUDE.md                  # rules for Claude Code
├── CONTRIBUTING.md            # two-dev GitHub workflow
├── Makefile                   # make up / test / eval / lint / seed
├── docker-compose.yml
├── pyproject.toml             # uv-managed, single workspace
├── .env.example
├── docs/                      # BMAD artifacts (brief, prd, architecture, epics, stories, qa)
├── agent/                     # LangGraph agent (Track A)
│   ├── graph.py               # build_graph()
│   ├── state.py               # AgentState (TypedDict) + enums
│   ├── nodes/                 # intake.py verify.py policy.py claim.py clarify.py confirm.py handoff.py router.py
│   ├── prompts/               # *.md prompt templates, versioned in MLflow
│   ├── schemas.py             # IntentResult, LLMResult (agent-only models)
│   ├── llm.py                 # LiteLLM wrapper + MockLLM
│   └── mcp_client.py          # typed client over MCP tools
├── mcp_tools/                 # FastMCP server (Track B)
│   ├── server.py
│   ├── tools/                 # coverage.py verification.py cases.py
│   ├── payer_mock.py
│   └── db/                    # models.py session.py migrations/ (alembic)
├── api/                       # FastAPI (Track B)
│   ├── main.py  routes/  deps.py
│   └── static/index.html      # chat UI
├── shared/                    # schemas.py (ClaimDraft, contract models) — imported by agent & mcp_tools
├── observability/             # redaction.py tracing.py (shared)
├── evals/                     # datasets/*.jsonl, runner.py, scorers.py
├── tests/                     # unit/ integration/ fakes/
├── data/seed/                 # synthetic members & coverage
├── infra/terraform/
└── .github/                   # workflows, templates, CODEOWNERS
```

## 3. LangGraph design

### 3.1 State (`agent/state.py`)

```python
class Phase(str, Enum):
    INTAKE = "intake"; VERIFY = "verify"; POLICY = "policy"
    CLAIM = "claim"; CLARIFY = "clarify"; CONFIRM = "confirm"
    DONE = "done"; LOCKED = "locked"; HANDOFF = "handoff"; CANCELLED = "cancelled"

class AgentState(TypedDict):
    session_id: str
    messages: Annotated[list[AnyMessage], add_messages]
    phase: Phase
    member_id: str | None
    full_name: str | None
    snapshot_id: str | None          # coverage_snapshots.id (never raw coverage in state before verify)
    verification_id: str | None
    verified: bool
    failed_attempts: int
    pending_question_id: str | None  # current challenge question id
    policy_view: dict | None         # populated ONLY by policy node after verified
    claim: ClaimDraft                # partial, accumulates across turns
    missing_fields: list[str]
    clarify_turns: int
    last_intent: str | None
    case_number: str | None
```

### 3.2 Graph

```
START → router ─┬─(intent=cancel)──────────────► cancelled → END
                ├─(intent=handoff)─────────────► handoff → END
                └─(by phase) ─► intake ──(member_id & name valid)──► fetch_coverage ──► verify
                                                                                      │   ▲
                                                           (fail & attempts<3) ───────┘   │
                                                           (fail & attempts=3) ──► locked → END
                                                           (pass) ──► policy ──► claim_extract
                                                                                    │
                                                        (missing_fields) ──► clarify ⇄ claim_extract
                                                        (complete) ──► confirm ─(yes)─► create_case → END
                                                                          └─(edit)──► claim_extract
```

- Each user message re-enters at `router`, which classifies intent (`docs/intents.md`) and dispatches on `state.phase`.
- Nodes that need user input **end the turn** (return an AI message; graph halts via `interrupt`/END and resumes on next message with the same `thread_id = session_id`).
- **Checkpointer:** `langgraph-checkpoint-postgres` (`PostgresSaver`), `thread_id = session_id`.

### 3.3 Hard safety invariants (enforced in code + evals)

1. `policy_view` is written only by `policy` node and only if `state.verified is True` (assert + test).
2. `create_case` tool rejects when the verification record isn't `PASSED` (server-side check, not just agent).
3. Verification pass/fail is decided by `check_answer` in `mcp_tools` — the LLM never sees expected answers.
4. Unknown member ID and wrong answers produce the same generic message (no enumeration).

## 4. Data model (Postgres)

```sql
members(id uuid pk, member_id text unique, first_name, last_name, dob date, zip text,
        employer_group text, subscriber_name text, relationship text, payer_id text, created_at)
coverage_snapshots(id uuid pk, session_id text, member_id text, payload jsonb, source text,  -- 'mock_payer'
        status text check (status in ('unverified','verified','discarded')), fetched_at timestamptz)
verifications(id uuid pk, session_id text, member_id text, status text  -- PENDING|PASSED|FAILED|LOCKED
        , attempts int, asked_question_ids text[], created_at, updated_at)
cases(id uuid pk, case_number text unique, session_id text, member_id text, snapshot_id uuid fk,
        verification_id uuid fk, claim jsonb, status text default 'NEW', created_at)
audit_log(id bigserial pk, session_id text, event text, detail jsonb, created_at)
-- + LangGraph checkpoint tables (created by PostgresSaver.setup())
```

Payer mock reads from `data/seed/coverage.json` keyed by member_id; `members` table is seeded from `data/seed/members.json`.

## 5. Claim schema (`shared/schemas.py`)

```python
class ClaimDraft(BaseModel):
    claim_type: Literal["medical","pharmacy","dental","vision"] | None = None      # required
    patient_is_member: bool | None = None                                          # required
    date_of_service: date | None = None                                            # required, <= today, in coverage period
    provider_name: str | None = None                                               # required
    provider_npi: str | None = None                                                # optional, 10 digits (Luhn check)
    place_of_service: Literal["office","hospital_inpatient","hospital_outpatient",
                              "emergency_room","urgent_care","telehealth","pharmacy","other"] | None = None  # required
    reason_for_visit: str | None = None                                            # required (free text)
    services: list[str] = []                                                       # required, >=1
    amount_billed: Decimal | None = None                                           # required, >= 0
    amount_paid_by_member: Decimal | None = None                                   # optional
    is_accident_related: bool | None = None                                        # required
    accident_type: Literal["auto","work","other"] | None = None                    # required if accident
    has_other_insurance: bool | None = None                                        # required
    notes: str | None = None

REQUIRED = ["claim_type","patient_is_member","date_of_service","provider_name","place_of_service",
            "reason_for_visit","services","amount_billed","is_accident_related","has_other_insurance"]
```

Extraction uses LiteLLM structured output (`response_format=ClaimDraft` JSON schema) → merge into existing draft (never overwrite a confirmed value with `None`). Diagnosis/CPT coding is **out of scope** for the member-facing demo (ops codes later).

## 6. LLM gateway (`agent/llm.py`)

- `complete(messages, *, purpose, schema=None) -> LLMResult` wraps `litellm.completion`.
- Model map in config: `LLM_MODEL_DEFAULT=bedrock/anthropic.claude-sonnet-...`, `LLM_MODEL_FAST=bedrock/anthropic.claude-haiku-...` (intent classification). Exact IDs set in `.env` — check Bedrock console for enabled model IDs in your region.
- `LLM_MODE=mock` → `MockLLM` returns scripted responses from `tests/fakes/llm_scripts/*.yaml` keyed by `purpose` + input hash/regex. CI always runs mock.
- Retries: 2 with exponential backoff on throttling; timeout 20s.

## 7. MCP integration

- `mcp_tools/server.py`: `FastMCP("claims-tools")`, transport `streamable-http` on `:8765/mcp`.
- `agent/mcp_client.py`: thin typed wrapper using the `mcp` Python client (or `langchain-mcp-adapters` if tools are exposed to an LLM-driven node). **Nodes call tools directly** (deterministic control flow); the LLM does not choose tools in this demo.
- Tool contracts: `docs/contracts/mcp-tools.md` (source of truth, versioned).

## 8. API (`api/`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/sessions` | create session → `{session_id}` + greeting |
| POST | `/sessions/{id}/messages` | send user text → SSE stream of agent tokens + final `state_view` |
| GET | `/sessions/{id}` | phase, verified flag, policy_view (if verified), claim draft, case_number |
| GET | `/cases/{case_number}` | case details (demo ops view) |
| GET | `/healthz` | liveness (checks db + mcp) |
| WS | `/voice/{id}` | *stretch* audio in / audio out |

## 9. Configuration (`.env.example`)

```
APP_ENV=local
LLM_MODE=mock                      # mock | bedrock
AWS_REGION=us-west-2
LLM_MODEL_DEFAULT=bedrock/<claude-sonnet-model-id>
LLM_MODEL_FAST=bedrock/<claude-haiku-model-id>
DATABASE_URL=postgresql+psycopg://claims:claims@postgres:5432/claims
MCP_URL=http://mcp-tools:8765/mcp
MLFLOW_TRACKING_URI=http://mlflow:5000
MLFLOW_EXPERIMENT=claims-intake-agent
MAX_VERIFY_ATTEMPTS=3
MAX_CLARIFY_TURNS=6
```

## 10. Security & PHI

- Synthetic data only (`data/seed/`). Real PHI must never be committed or sent to Bedrock in this demo.
- `observability/redaction.py` masks: member IDs, names, DOB, ZIP, phone, email, NPI, dollar amounts optional. Applied to log records and MLflow span inputs/outputs (see `docs/tracing.md`).
- Bedrock via IAM task role (no static keys in AWS); locally via `AWS_PROFILE`.
- Secrets: AWS Secrets Manager → ECS task env. `.env` git-ignored.

## 11. Deployment (AWS)

ECR (2 images) → ECS Fargate services `api` (behind ALB, HTTPS) and `mcp-tools` (internal, Service Connect) → RDS Postgres → MLflow on ECS with S3 artifact store → CloudWatch logs. Terraform in `infra/terraform`. GitHub Actions deploys via OIDC role (no long-lived AWS keys).

## 12. Key library choices

`langgraph`, `langchain-core`, `langgraph-checkpoint-postgres`, `fastmcp`, `mcp`, `litellm`, `mlflow` (≥ 3.x for GenAI tracing), `fastapi`, `uvicorn`, `sse-starlette`, `sqlalchemy` 2.x, `alembic`, `psycopg[binary]`, `pydantic` v2, `rapidfuzz` (name match), `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `uv`. Pin versions in `pyproject.toml` at story 1.1.
