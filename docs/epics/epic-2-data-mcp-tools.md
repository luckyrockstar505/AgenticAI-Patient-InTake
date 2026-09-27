# Epic 2: Data & MCP Tools

**Track:** B  
**Goal:** Provide the database, synthetic members, mock payer and the FastMCP tool server that implements docs/contracts/mcp-tools.md.

## Stories

| Story | Title | Owner | Depends on | Size |
|---|---|---|---|---|
| [2.1](../stories/2.1.db-schema-migrations-synthetic-seed.md) | DB schema, migrations & synthetic seed | B | 1.1 | M |
| [2.2](../stories/2.2.mock-payer-eligibility-service.md) | Mock payer eligibility service | B | 2.1 | S |
| [2.3](../stories/2.3.fastmcp-coverage-tools.md) | FastMCP coverage tools | B | 2.2 | M |
| [2.4](../stories/2.4.fastmcp-verification-tools.md) | FastMCP verification tools | B | 2.3 | M |
| [2.5](../stories/2.5.fastmcp-case-tools.md) | FastMCP case tools | B | 2.1 | S |

## Epic done when

- All stories Done (merged, QA PASS)
- `make test` and `make eval` green on main
- Demo of the epic's capability recorded in the PR of its last story
