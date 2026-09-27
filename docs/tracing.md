# Tracing & Observability (MLflow)

> Stories: 1.4 (baseline), then every story adds its spans. MLflow ≥ 3.x GenAI tracing.

## 1. Goals

- Every user turn has **one trace**, which you can find by `session_id`.
- You can see which node ran, which tools were called, what the LLM was asked, how many tokens it used, what it cost, and how long each step took.
- **Zero PHI** in any trace, log line or artifact.

## 2. Trace structure

```
api.message                        (FastAPI handler; tags: session_id, app_env, git_sha)
└── agent.turn                     (tags: phase_before, phase_after, intent)
    ├── node.router                attrs: intent, confidence, fast_path
    │   └── llm.intent             (litellm autolog; attrs: purpose=intent, model, tokens, cost)
    ├── node.intake                attrs: has_member_id, has_name, id_valid
    │   ├── mcp.fetch_coverage     attrs: found, snapshot_id
    │   └── mcp.start_verification attrs: name_match, question_id
    ├── node.verify                attrs: status, attempts
    │   ├── llm.verify_phrase
    │   └── mcp.check_answer       attrs: question_id, status, attempts
    ├── node.policy                attrs: plan_type, status
    │   └── mcp.get_policy_view
    ├── node.claim_extract         attrs: fields_filled, missing_count
    │   └── llm.claim_extract
    ├── node.clarify               attrs: target_field, clarify_turns
    ├── node.confirm / node.create_case   attrs: case_number, corrections
    └── node.handoff               attrs: reason
```

## 3. Naming & tagging rules

| Kind | Name | Created by |
|---|---|---|
| HTTP | `api.<route>` | `@mlflow.trace` on route handler |
| Turn | `agent.turn` | wrapper around `graph.ainvoke` / `astream` |
| Node | `node.<name>` | `@mlflow.trace(name=...)` on each node function (autolog also captures LangGraph runs) |
| Tool | `mcp.<tool>` | `agent/mcp_client.py` wraps each call |
| LLM | `llm.<purpose>` | `mlflow.litellm.autolog()`, span renamed or attributed with `purpose` |
| Voice | `voice.stt`, `voice.tts` | story 8.x |

Trace-level tags: `session_id`, `app_env`, `git_sha`, `llm_mode`, and for evals `eval_run_id` and `scenario_id`.

## 4. PHI redaction

These are masked at the **span processor / exporter** level, so masking happens no matter how a span was created:

| Data | Rule | Example |
|---|---|---|
| Member ID | regex `[A-Z]{3}\d{9}` (with separators) | `ABC•••••0001` |
| Names | known-values list registered per session + persona names | `[NAME]` |
| Dates of birth | any date within ±1 day of a registered DOB, plus fields named `dob` | `[DOB]` |
| ZIP | 5-digit tokens in verify phase; field `zip` | `[ZIP]` |
| Phone / email / SSN / card | standard regexes | `[PHONE]` `[EMAIL]` `[SSN]` `[CARD]` |
| Challenge answers | the `answer` argument of `check_answer` is always masked | `[ANSWER]` |

In tests, `tests/integration/test_trace_no_phi.py` runs S01 and R08, exports the traces as JSON, and asserts that none of the seed PHI strings appear.

Also: `logging` uses a `RedactingFormatter`, and uvicorn access logs exclude request bodies.

## 5. What to check in MLflow

- **Debugging a failing scenario:** filter traces by `tags.scenario_id = 'S04'`.
- **Cost:** sum `llm.*` span cost per session, and compare the default and fast model tiers.
- **Latency:** p95 of `agent.turn` duration (tracked by the nightly eval).
- **Prompt versions:** each `llm.*` span carries a `prompt_version` attribute that links to the Prompt Registry.

## 6. PR evidence

Each story that adds spans includes one of these in its PR description:

- a screenshot of the trace tree, or
- the trace ID from the local MLflow instance (`http://localhost:5000`).
