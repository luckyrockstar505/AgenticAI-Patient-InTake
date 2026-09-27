#!/usr/bin/env bash
# Creates labels, milestones (one per epic) and one GitHub issue per story.
# Usage: DEV_A=<github-user> DEV_B=<github-user> ./scripts/create_github_issues.sh
# Requires: gh auth login, run from repo root. Safe to re-run: skips issues whose title already exists.
set -euo pipefail
: "${DEV_A:?set DEV_A github username}"
: "${DEV_B:?set DEV_B github username}"

for l in 'track:A|1d76db' 'track:B|0e8a16' 'type:story|5319e7' 'size:S|c2e0c6' 'size:M|fbca04' 'size:L|d93f0b' 'stretch|bfdadc'; do
  gh label create "${l%%|*}" --color "${l##*|}" --force >/dev/null
done

gh api repos/:owner/:repo/milestones -f title='E1 Foundation & DevEx' >/dev/null 2>&1 || true
gh api repos/:owner/:repo/milestones -f title='E2 Data & MCP Tools' >/dev/null 2>&1 || true
gh api repos/:owner/:repo/milestones -f title='E3 Identity & Policy Flow' >/dev/null 2>&1 || true
gh api repos/:owner/:repo/milestones -f title='E4 Claim Intake & Case' >/dev/null 2>&1 || true
gh api repos/:owner/:repo/milestones -f title='E5 API & Chat UI' >/dev/null 2>&1 || true
gh api repos/:owner/:repo/milestones -f title='E6 Evals & Quality' >/dev/null 2>&1 || true
gh api repos/:owner/:repo/milestones -f title='E7 Deploy & Demo' >/dev/null 2>&1 || true
gh api repos/:owner/:repo/milestones -f title='E8 Voice (Stretch)' >/dev/null 2>&1 || true

existing=$(gh issue list --state all --limit 500 --json title -q '.[].title')

mk() { # title file owner labels milestone
  if grep -Fxq "$1" <<<"$existing"; then echo "skip: $1"; return; fi
  gh issue create --title "$1" --body-file "$2" --assignee "$3" --label "$4" --milestone "$5"
}

mk 'Story 1.1: Repo scaffold & local docker stack' 'docs/stories/1.1.repo-scaffold-local-docker-stack.md' "$DEV_B" 'type:story,track:B,size:M' 'E1 Foundation & DevEx'
mk 'Story 1.2: CI pipeline (lint, type, test, build)' 'docs/stories/1.2.ci-pipeline-lint-type-test-build.md' "$DEV_B" 'type:story,track:B,size:S' 'E1 Foundation & DevEx'
mk 'Story 1.3: LLM gateway via LiteLLM (Bedrock + mock)' 'docs/stories/1.3.llm-gateway-via-litellm-bedrock-mock.md' "$DEV_A" 'type:story,track:A,size:S' 'E1 Foundation & DevEx'
mk 'Story 1.4: MLflow tracing baseline & PHI redaction' 'docs/stories/1.4.mlflow-tracing-baseline-phi-redaction.md' "$DEV_B" 'type:story,track:B,size:M' 'E1 Foundation & DevEx'
mk 'Story 2.1: DB schema, migrations & synthetic seed' 'docs/stories/2.1.db-schema-migrations-synthetic-seed.md' "$DEV_B" 'type:story,track:B,size:M' 'E2 Data & MCP Tools'
mk 'Story 2.2: Mock payer eligibility service' 'docs/stories/2.2.mock-payer-eligibility-service.md' "$DEV_B" 'type:story,track:B,size:S' 'E2 Data & MCP Tools'
mk 'Story 2.3: FastMCP coverage tools' 'docs/stories/2.3.fastmcp-coverage-tools.md' "$DEV_B" 'type:story,track:B,size:M' 'E2 Data & MCP Tools'
mk 'Story 2.4: FastMCP verification tools' 'docs/stories/2.4.fastmcp-verification-tools.md' "$DEV_B" 'type:story,track:B,size:M' 'E2 Data & MCP Tools'
mk 'Story 2.5: FastMCP case tools' 'docs/stories/2.5.fastmcp-case-tools.md' "$DEV_B" 'type:story,track:B,size:S' 'E2 Data & MCP Tools'
mk 'Story 3.1: LangGraph skeleton, state & checkpointer' 'docs/stories/3.1.langgraph-skeleton-state-checkpointer.md' "$DEV_A" 'type:story,track:A,size:M' 'E3 Identity & Policy Flow'
mk 'Story 3.2: Intent classifier & global router' 'docs/stories/3.2.intent-classifier-global-router.md' "$DEV_A" 'type:story,track:A,size:M' 'E3 Identity & Policy Flow'
mk 'Story 3.3: Intake node (member ID + name)' 'docs/stories/3.3.intake-node-member-id-name.md' "$DEV_A" 'type:story,track:A,size:S' 'E3 Identity & Policy Flow'
mk 'Story 3.4: Verify node: challenge loop & lockout' 'docs/stories/3.4.verify-node-challenge-loop-lockout.md' "$DEV_A" 'type:story,track:A,size:M' 'E3 Identity & Policy Flow'
mk 'Story 3.5: Policy display node (verified gate)' 'docs/stories/3.5.policy-display-node-verified-gate.md' "$DEV_A" 'type:story,track:A,size:S' 'E3 Identity & Policy Flow'
mk 'Story 4.1: Claim schema & NL extraction' 'docs/stories/4.1.claim-schema-nl-extraction.md' "$DEV_A" 'type:story,track:A,size:M' 'E4 Claim Intake & Case'
mk 'Story 4.2: Gap detection & clarify loop' 'docs/stories/4.2.gap-detection-clarify-loop.md' "$DEV_A" 'type:story,track:A,size:M' 'E4 Claim Intake & Case'
mk 'Story 4.3: Confirm & create case' 'docs/stories/4.3.confirm-create-case.md' "$DEV_A" 'type:story,track:A,size:S' 'E4 Claim Intake & Case'
mk 'Story 4.4: Human handoff & cancel paths' 'docs/stories/4.4.human-handoff-cancel-paths.md' "$DEV_A" 'type:story,track:A,size:S' 'E4 Claim Intake & Case'
mk 'Story 5.1: FastAPI session/chat/case endpoints' 'docs/stories/5.1.fastapi-session-chat-case-endpoints.md' "$DEV_B" 'type:story,track:B,size:M' 'E5 API & Chat UI'
mk 'Story 5.2: Web chat UI' 'docs/stories/5.2.web-chat-ui.md' "$DEV_B" 'type:story,track:B,size:S' 'E5 API & Chat UI'
mk 'Story 6.1: Golden dataset & eval harness' 'docs/stories/6.1.golden-dataset-eval-harness.md' "$DEV_A" 'type:story,track:A,size:M' 'E6 Evals & Quality'
mk 'Story 6.2: CI eval gate & nightly Bedrock evals' 'docs/stories/6.2.ci-eval-gate-nightly-bedrock-evals.md' "$DEV_B" 'type:story,track:B,size:S' 'E6 Evals & Quality'
mk 'Story 6.3: Red-team & safety scenarios' 'docs/stories/6.3.red-team-safety-scenarios.md' "$DEV_A" 'type:story,track:A,size:S' 'E6 Evals & Quality'
mk 'Story 7.1: AWS infrastructure (Terraform)' 'docs/stories/7.1.aws-infrastructure-terraform.md' "$DEV_B" 'type:story,track:B,size:L' 'E7 Deploy & Demo'
mk 'Story 7.2: CD pipeline via GitHub OIDC' 'docs/stories/7.2.cd-pipeline-via-github-oidc.md' "$DEV_B" 'type:story,track:B,size:M' 'E7 Deploy & Demo'
mk 'Story 7.3: Demo readiness: smoke test & runbook' 'docs/stories/7.3.demo-readiness-smoke-test-runbook.md' "$DEV_A,$DEV_B" 'type:story,track:A,track:B,size:S' 'E7 Deploy & Demo'
mk 'Story 8.1: Voice: WebSocket + Transcribe streaming' 'docs/stories/8.1.voice-websocket-transcribe-streaming.md' "$DEV_B" 'type:story,track:B,size:L,stretch' 'E8 Voice (Stretch)'
mk 'Story 8.2: Voice: Polly TTS & turn-taking' 'docs/stories/8.2.voice-polly-tts-turn-taking.md' "$DEV_A" 'type:story,track:A,size:M,stretch' 'E8 Voice (Stretch)'

echo 'Done. Paste issue numbers into each story file header (GitHub issue row).'
