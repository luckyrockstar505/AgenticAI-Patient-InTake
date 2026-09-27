# Contributing — two developers, story by story

## Roles

| | Dev A (Bharath) | Dev B |
|---|---|---|
| Track | **A — Agent**: `agent/`, `evals/`, prompts | **B — Platform**: `mcp_tools/`, `api/`, `observability/`, `infra/`, `.github/` |
| Reviews | Track B PRs | Track A PRs |
| Shared | `docs/contracts/`, `shared/`, `CLAUDE.md` (both must approve) | same |

Add a `.github/CODEOWNERS` file to enforce this split automatically.

## Story lifecycle (BMAD → GitHub)

```
Draft ──(SM/PO review, both agree)──► Approved ──(owner starts)──► InProgress
   ──(PR opened)──► Review ──(QA PASS + CI green + approval)──► Done (squash-merged)
```

| Step | Who | BMAD agent | GitHub |
|---|---|---|---|
| 1. Refine the story | both, 15 min | `*sm` (Scrum Master) / `*po` validate | Issue created by `scripts/create_github_issues.sh` |
| 2. Start it | owner | — | Assign yourself and move the issue to **In Progress** on the Project board |
| 3. Implement | owner | Claude Code `/story <id>` (Dev) | Branch `story/<id>-<slug>` with small commits |
| 4. Open a PR | owner | — | Use the PR template, with `Closes #<issue>` |
| 5. QA review | other dev | Claude Code `/review-story <id>` (QA) | PR review. The QA Results section gets committed to the story file |
| 6. Merge | owner | — | Squash-merge once CI is green and the PR is approved. The issue closes automatically |
| 7. Mark Done | owner | — | Set the story file's Status to `Done` in the merge commit |

## Branches & commits

- `main` is protected: CI must be green, 1 approval is required, the branch must be up to date, and merges are squash-only.
- Branch per story: `story/3.4-verify-node-challenge-loop`. Stories get their own branches, never shared ones.
- Use Conventional Commits with the story scope: `feat(story-3.4): …`, `fix(story-2.4): …`, `docs(story-3.4): QA results`.
- Rebase on `main` daily (`git pull --rebase origin main`). Keep PRs under about 400 changed lines. If a story grows past that, split it.

## Working in parallel without blocking each other

1. **Contracts first.** On Day 0, both devs review and freeze `docs/contracts/mcp-tools.md` v1, the state schema and `ClaimDraft`.
2. **Fakes.** Track A codes against `tests/fakes/fake_mcp.py` (story 3.1). Contract tests run against both the fake and the real server, so they can't drift.
3. **Shared code** (`shared/schemas.py`, contracts) changes only in a dedicated PR titled `contract: …` that both devs approve and that bumps the contract version.
4. **Daily 10-min sync.** Cover what merged, what's blocked, and the next story. Update the Project board.
5. **Dependencies.** Don't start a story whose "Depends on" stories aren't Done. The exception is coding against the fake when the dependency is a Track B tool.

## Project board (GitHub Projects)

Columns: **Backlog → Approved → In Progress → Review → Done**.

Custom fields:

- Track (A/B)
- Epic (E1–E8)
- Size (S/M/L)
- Sprint

Milestones: one per epic, created by the script.

## Setup (once)

```bash
git clone <repo> && cd claims-intake-agent
cp .env.example .env            # fill AWS_PROFILE / model IDs for live runs
make up && make seed
gh auth login
DEV_A=<gh-user> DEV_B=<gh-user> ./scripts/create_github_issues.sh
```

Configure branch protection in GitHub: Settings → Branches → `main`.

### Required branch protection rules

- **CI must be all-green** before a PR can merge. Required status checks:
  - `Lint` (`lint` job — ruff + mypy)
  - `Unit tests` (`test-unit` job)
  - `Integration tests` (`test-integration` job)
  - `Docker build` (`docker-build` job)
  - `Eval (mock)` (`eval` job)
- **1 approving review** required (from the other track's developer — see the Roles table above).
- **Squash merge only** — no merge commits, no rebase merges.
- **Branch must be up to date** with `main` before merge.

### CI invariants — never break these

- `LLM_MODE=mock` is always set in CI. A test that calls `litellm.completion` without a mock override will fail with an `AssertionError` from `tests/conftest.py`.
- Never commit `.env` files or credentials to the repository. The CI environment never has real AWS credentials.
- `make eval` (and the `eval` CI job) must always exit 0. The eval runner silently succeeds when no scenarios are registered.

## Definition of Done

See `docs/prd.md` §7. It applies to every PR.
