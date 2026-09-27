# Epic 7: Deploy & Demo

**Track:** B  
**Goal:** Deploy to AWS with Terraform and a GitHub Actions CD pipeline, and make the demo repeatable.

## Stories

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| [7.1](../stories/7.1.aws-infrastructure-terraform.md) | AWS infrastructure (Terraform) | B | 1.1 | L |
| [7.2](../stories/7.2.cd-pipeline-via-github-oidc.md) | CD pipeline via GitHub OIDC | B | 7.1, 1.2 | M |
| [7.3](../stories/7.3.demo-readiness-smoke-test-runbook.md) | Demo readiness: smoke test & runbook | A+B | 3.5, 4.3, 5.2, 6.2, 7.2 | S |

## Epic done when

- All stories Done (merged, QA PASS)
- `make test` and `make eval` green on main
- Demo of the epic's capability recorded in the PR of its last story
