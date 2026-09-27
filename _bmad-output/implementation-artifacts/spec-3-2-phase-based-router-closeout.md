---
title: 'Story 3.2 closeout — stub router already delivered by 3.1'
type: 'chore'
created: '2026-09-27'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: ['{project-root}/_bmad-output/planning-artifacts/epics.md', '{project-root}/docs/stories/3.2.intent-classifier-global-router.md', '{project-root}/agent/nodes/router.py', '{project-root}/docs/intents.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `_bmad-output/planning-artifacts/epics.md` scopes story 3.2 as a phase-based stub router (regex cancel/handoff fast-paths, dispatch by `state.phase`) — and that exact router already shipped as part of story 3.1 (`agent/nodes/router.py`, `route_from_router`). Meanwhile `docs/stories/3.2.intent-classifier-global-router.md` still describes a larger, un-built scope (fast-model `IntentResult` classification, a per-phase allowed-intents policy table, abuse/prompt-injection handling, a registered MLflow prompt) under the same story number. The user has decided: treat 3.2's scope per epics.md, and close it out against the router already built.

**Approach:** Mark story 3.2 `Done` in `docs/stories/3.2.intent-classifier-global-router.md`, with Completion Notes pointing at 3.1's `agent/nodes/router.py` as satisfying the phase-based/regex-fast-path scope. Tick only the sub-tasks that scope actually covers; leave the LLM-classification-specific tasks (classifier prompt, phase policy table, abuse handling, prompt registry) unchecked and record them as deferred work in `_bmad-output/implementation-artifacts/deferred-work.md`, per this workflow's own deferred-goal mechanism — not invented as a new story number unilaterally. Update `epics.md`'s Epic 3 story row and `epic-3-context.md`'s Stories list to match. No production code changes; no new tests (nothing in `agent/` behavior changes).

</frozen-after-approval>

## Implementation Notes

- Updated `docs/stories/3.2.intent-classifier-global-router.md` (Status, scope note, tasks, Dev Agent Record, File List, Change Log), `_bmad-output/planning-artifacts/epics.md` (Epic 3 row + note), `_bmad-output/implementation-artifacts/epic-3-context.md` (Stories list), and created `_bmad-output/implementation-artifacts/deferred-work.md`.
- Blind Hunter review (N=4 floor, 11 findings returned) surfaced real gaps beyond the original plan: Status was set to `Done` instead of `Review` with no reviewer involvement, branch name didn't follow `story/<id>-<slug>`, no lint/test/eval evidence was recorded, `agent/nodes/router.py`'s docstrings were left stale, and `docs/intents.md` had no flag marking most of its content as deferred/unbuilt. All patched — see Review Triage Log.
- Branch renamed `chore/3.2-stub-router-closeout` → `story/3.2-router-closeout` mid-implementation.
- Verified: `make lint` (ruff+mypy, whole repo) clean, `pytest tests/unit` 90 passed, `evals.runner` stays green.

## Review Triage Log

- **high** — Story status set to `Done` with no reviewer (Srimaan) involvement and an unfilled QA Results section, skipping CLAUDE.md's InProgress→Review workflow. Evidence: `docs/stories/3.2...md` read directly. Fixed: Status → `Review`; scope note now says "awaiting Srimaan's review."
- **medium** — Branch `chore/3.2-stub-router-closeout` didn't follow the `story/<id>-<slug>` convention CLAUDE.md requires for story work. Fixed: renamed to `story/3.2-router-closeout`.
- **medium** — No evidence `make lint`/`test`/`eval` were run before calling this closeout complete. Fixed: ran all three, recorded results in Debug Log References.
- **medium** — `agent/nodes/router.py`'s two docstrings still said "story 3.2 adds real intent classification" / "real intent classification is story 3.2," contradicted by this closeout. Fixed: reworded both (comment-only, no behavior change).
- **medium** — `docs/intents.md` describes a full `IntentResult` classifier, intent catalog, and phase-policy table that were never built, with no signal to a reader that most of it is deferred; the deferred-work.md entry also didn't cross-link back to it or flag the safety-relevant abuse-handling gap prominently. Fixed: added a status callout to `docs/intents.md`'s header, added it to this spec's `context:` list, and strengthened the `deferred-work.md` entry to call out the abuse-handling gap explicitly.
- **low** — Task checkbox "Regex fast-paths (... partial ...)" was checked despite being labelled partial. Fixed: split into a checked item for the fully-delivered regex piece and a separate unchecked item for the deferred classifier piece.
- **low** — epics.md's replacement note dropped the original "Do NOT defer 3.2 — it is required for the graph to dispatch" rationale. Fixed: one clause added explaining why that constraint no longer blocks (3.1 already satisfies it).
- **false** — Spec frontmatter `status: 'in-progress'` claimed to be inconsistent with sibling specs using `'in-review'`. Disproved: those siblings are `route: 'dispatch'` (terminal state `in-review`, set by step-04-review.md); this spec is `route: 'oneshot'`, whose own Finalize step sets `'done'` directly — different terminal states by design, not a bug. The `in-progress` value the reviewer saw was simply this spec mid-execution, before Finalize ran.
- **false** — Spec missing `## Spec Change Log` and `## Verification` sections, "ends abruptly." Disproved: step-02-plan.md's oneshot route explicitly permits writing only frontmatter + `## Intent` + `## Implementation Notes`, deleting every other section. The `## Review Triage Log` section the reviewer also flagged as missing is added here, in Finalize, as scripted — its prior absence wasn't a defect, just sequencing.


