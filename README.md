# Claims Intake Agent (Demo)

AI agent that verifies a member, shows their coverage, and turns a natural-language claim description into a structured case. Built with the **BMAD method** by two developers working story by story with **Claude Code**.

**Stack:** LangGraph · FastMCP · FastAPI · LiteLLM → AWS Bedrock (Claude) · Postgres · MLflow · Docker · GitHub Actions · AWS ECS

---

## Quickstart

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd claims-intake-agent

# 2. Create your local .env (safe defaults already filled in)
cp .env.example .env

# 3. Start the full stack (builds images on first run — ~5-10 min cold start)
make up

# 4. Verify everything is healthy
curl -s http://localhost:8000/healthz | python3 -m json.tool
# Expected: {"status": "ok", "db": "ok", "mcp": "ok"}
```

Other useful targets:

```bash
make test    # run unit tests
make eval    # run eval suite (exits 0 with no scenarios until story 6.1)
make lint    # ruff + mypy
make logs    # tail container logs
make down    # stop containers
```

**MLflow UI:** http://localhost:5000

---

## Project map

| You want… | Open |
|---|---|
| Why we're building this | `docs/brief.md` |
| What we're building + story map | `docs/prd.md` |
| Architecture decisions | `docs/architecture.md` |
| Agent ⇄ tools contract | `docs/contracts/mcp-tools.md` |
| Conversation intents | `docs/intents.md` |
| Epics / stories | `docs/epics/`, `docs/stories/` |
| Evals, tests, tracing | `docs/qa/eval-plan.md`, `docs/tracing.md` |
| Eval datasets | `evals/datasets/`, `evals/thresholds.yaml` |
| Synthetic personas | `data/seed/` |
| Collaboration guide | `CONTRIBUTING.md` |
| Rules for Claude Code | `CLAUDE.md` |

---

## Conversation flow

```
member ID + name
  → fetch_coverage (MCP, stored unverified)
  → verify (DOB + challenge question, max 3 attempts)
  → policy view (verified members only)
  → claim in natural language ⇄ clarify loop
  → confirm
  → create_case
```

---

## Development status

Story 1.1 complete — repo scaffold and local Docker stack.  
Development continues story by story.  See `docs/stories/` for the backlog.
