"""FastMCP server for Claims Intake Agent.

Exposes:
  GET  /healthz   — simple HTTP health check (FastAPI wrapper)
  POST /mcp       — MCP streamable-http endpoint (FastMCP tools)

Story 1.1: scaffold with one stub tool (ping).
Story 2.x adds coverage, verification, and case tools.

Run locally:
    uv run python -m mcp_tools.server
Or via Docker:
    docker compose up mcp-tools
"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# MCP tool definitions
# ---------------------------------------------------------------------------
mcp = FastMCP("claims-tools")


@mcp.tool()
def ping() -> dict[str, bool]:
    """Health-check ping.  Returns {pong: true}."""
    return {"pong": True}


# ---------------------------------------------------------------------------
# HTTP wrapper — adds /healthz alongside the MCP endpoint
# ---------------------------------------------------------------------------
app = FastAPI(title="claims-tools-mcp", docs_url=None, redoc_url=None)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe used by docker-compose and api/healthz."""
    return {"status": "ok"}


# Mount FastMCP's streamable-http ASGI handler at /mcp.
# FastMCP 2.x: mcp.http_app() returns a Starlette ASGI application.
# The path argument tells FastMCP its own root within the mounted scope.
app.mount("/mcp", mcp.http_app(path="/"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
