# Claims Intake Agent (Demo)

This is an AI agent that verifies a member, shows their coverage, and turns a natural-language claim description into a structured case. It is built with the **BMAD method** by two developers working story by story with **Claude Code**.

**Stack:** LangGraph · FastMCP · FastAPI · LiteLLM → AWS Bedrock (Claude) · Postgres · MLflow · Docker · GitHub Actions · AWS ECS

## Status

The planning phase is complete. Development starts at **story 1.1**. The repo has no application code yet; Claude Code writes it story by story.

## Where things are

| You want… | Open |
|---|---|
| Why we're building it | `docs/brief.md` |
| What we're building + story map + sprint plan | `docs/prd.md` |
| How it's built | `docs/architecture.md` |
| Agent ⇄ tools seam | `docs/contracts/mcp-tools.md` |
| Conversation design | `docs/intents.md` |
| Epics / stories | `docs/epics/`, `docs/stories/` |
| Evals, tests, tracing | `docs/qa/eval-plan.md`, `docs/qa/test-strategy.md`, `docs/tracing.md` |
| Eval datasets | `evals/datasets/*.jsonl`, `evals/thresholds.yaml` |
| Synthetic personas | `data/seed/` |
| How we collaborate | `CONTRIBUTING.md` |
| Rules for Claude Code | `CLAUDE.md`, `.claude/commands/` |
| BMAD install & cycle | `docs/bmad-setup.md` |

## Quickstart (after story 1.1 lands)

```bash
cp .env.example .env
make up && make seed
python -m agent.cli          # chat in the terminal (LLM_MODE=mock by default)
open http://localhost:8000   # web chat (after story 5.2)
open http://localhost:5000   # MLflow traces
```

## Flow

```
member ID + name → fetch_coverage (MCP, stored unverified) → verify (DOB + challenge, max 3)
   → policy view (verified only) → claim in natural language ⇄ clarify → confirm → create_case
```
