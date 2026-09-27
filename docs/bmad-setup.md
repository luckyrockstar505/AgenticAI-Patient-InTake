# Using BMAD + Claude Code with this repo

This kit already contains the **planning-phase** BMAD outputs:

- brief
- PRD
- architecture
- epics
- stories

You pick up at the **development cycle**.

## 1. Install BMAD into the repo

```bash
npx bmad-method install      # choose Claude Code as the IDE; install into this repo
```

The installer adds the BMAD agents and config (for example `.bmad-core/` or `_bmad/`, depending on the version) and Claude Code slash commands for its agents. **Keep the existing `docs/` folder.** If the installer asks for document locations, point it at these:

| Setting | Value |
|---|---|
| PRD | `docs/prd.md` (not sharded; epics are already split into `docs/epics/`) |
| Architecture | `docs/architecture.md` |
| Stories location | `docs/stories` |
| Story file naming | `{epic}.{story}.{slug}.md` |
| QA location | `docs/qa` |
| Dev "always load" files | `CLAUDE.md`, `docs/architecture.md`, `docs/contracts/mcp-tools.md` |

After installing, open `core-config.yaml` (or the equivalent file) and check that `devStoryLocation: docs/stories` and `devLoadAlwaysFiles` match the table above.

## 2. The cycle, per story

| Step | BMAD agent (Claude Code) | This repo's shortcut |
|---|---|---|
| Validate or refine a story before starting it | `/sm` → `*draft` or `*story-checklist`; `/po` → `*validate-story-draft` | Edit the story file, then set Status to `Approved` |
| Implement it | `/dev` → `*develop-story docs/stories/3.4…md` | `/story 3.4` |
| Review it | `/qa` → `*review docs/stories/3.4…md` | `/review-story 3.4` |
| Architecture question or change | `/architect` | Propose it in a PR to `docs/architecture.md` |

**Use fresh context per story.** Start a new Claude Code session for each story so the Dev agent only loads what that story needs.

## 3. What BMAD will expect in each story file

The story files already follow the BMAD story template:

- Status
- Story
- Acceptance Criteria
- Tasks / Subtasks (with AC references)
- Dev Notes (including Testing)
- Dev Agent Record (Agent Model Used, Debug Log References, Completion Notes, File List)
- QA Results
- Change Log

This project adds three sub-sections under Dev Notes: **Evals**, **Tracing**, and a header table that holds the owner, branch and issue.

## 4. First week checklist

- [ ] Create a GitHub repo, push this kit, and add Dev B as a collaborator
- [ ] Replace `@dev-a` / `@dev-b` in `.github/CODEOWNERS`
- [ ] Run `DEV_A=… DEV_B=… ./scripts/create_github_issues.sh`, then paste the issue numbers into the story headers
- [ ] Create a GitHub Project board (Backlog → Approved → In Progress → Review → Done) and add the issues
- [ ] Day 0: review and freeze the contracts together
- [ ] Enable Bedrock model access in your AWS region and put the model IDs in `.env`
- [ ] Dev B: `/story 1.1`. Dev A pairs on it, then starts `/story 1.3`
