# Deferred Work

<!-- Append-only. One entry per deferred goal. Do not modify existing entries or look for duplicates. -->

- source_spec: `_bmad-output/implementation-artifacts/spec-3-2-phase-based-router-closeout.md`
  summary: Full intent classification for the global router — fast-model `IntentResult` classification, a per-phase allowed-intents policy table, **abuse/prompt-injection refusal handling**, and a classifier prompt registered in the MLflow Prompt Registry.
  evidence: This is the scope `docs/stories/3.2.intent-classifier-global-router.md` originally described (ACs 1 partial, 2, 4, 5). Story 3.2 was closed out against the smaller "phase-based stub router" scope from `epics.md`, which story 3.1 already delivered (`agent/nodes/router.py`, regex fast-paths + phase dispatch only, no LLM classification). This larger scope was never built and needs its own story before `docs/intents.md`'s full intent set (ask_question, describe_claim, provide_detail, off_topic, abuse, etc.) can be classified — today only `cancel`/`request_human` are handled, via regex. Flagged in `docs/intents.md`'s header and `agent/nodes/router.py`'s docstrings so it isn't only discoverable here. Safety-relevant: `abuse`/prompt-injection handling is currently a no-op (no refusal, no `safety_event` audit) until this lands — prioritize accordingly when assigning a story number.
