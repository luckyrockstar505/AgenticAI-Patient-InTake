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

## LLM gateway

All model calls go through `agent/llm.py:complete()` — no other module imports `litellm` directly.

- `LLM_MODE=mock` (default, used by `make test` / `make eval` / CI): responses come from `tests/fakes/llm_scripts/*.yaml`, matched by `purpose` + a regex on the last user message. No AWS credentials needed.
- `LLM_MODE=bedrock`: routes through LiteLLM to AWS Bedrock, using `LLM_MODEL_DEFAULT` / `LLM_MODEL_FAST` from `.env`.

### Enabling Bedrock model access

1. In the AWS Console, go to **Bedrock → Model access** in your target region (`AWS_REGION` in `.env`, default `us-west-2`).
2. Request access to the Claude model(s) you plan to use (a sonnet-class model for `LLM_MODEL_DEFAULT`, a haiku-class model for `LLM_MODEL_FAST`). Access is usually granted instantly for Anthropic models on Bedrock.
3. Copy the exact model IDs (or inference-profile ARNs) shown in the console into `.env` as `LLM_MODEL_DEFAULT=bedrock/<id>` / `LLM_MODEL_FAST=bedrock/<id>` — model IDs vary by region and are never hardcoded in source.
4. Make sure your shell has AWS credentials for that account (`AWS_PROFILE=<profile>` or an SSO login) — the gateway relies on the standard AWS credential chain; no static keys in code or `.env`.
5. Run the manual smoke test:
   ```bash
   AWS_PROFILE=<profile> LLM_MODE=bedrock uv run python scripts/smoke_bedrock.py
   ```
   A successful run prints token counts, cost, latency, and `OK — Bedrock reachable and responding.`

## Development status

Story 1.1 complete — repo scaffold and local Docker stack.
Story 1.3 complete — LLM gateway (LiteLLM/Bedrock + mock).
Development continues story by story.  See `docs/stories/` for the backlog.
