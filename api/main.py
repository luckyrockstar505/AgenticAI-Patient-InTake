"""FastAPI application entry-point.

Story 1.1: scaffold with /healthz endpoint.
Stories 5.x add sessions, messages, cases, and the chat UI.

Run locally:
    uv run uvicorn api.main:app --reload --port 8000
Or via Docker:
    docker compose up api
"""
from __future__ import annotations

import os

import httpx
import sqlalchemy
from fastapi import Depends, FastAPI

# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(title="Claims Intake Agent API")

# ---------------------------------------------------------------------------
# Configuration (resolved at import time so tests can set env vars before import)
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://claims:claims@postgres:5432/claims",
)
MCP_URL: str = os.getenv("MCP_URL", "http://mcp-tools:8765/mcp")
# Derive healthz URL from MCP_URL: replace trailing /mcp with /healthz
_MCP_BASE: str = MCP_URL[: -len("/mcp")] if MCP_URL.endswith("/mcp") else MCP_URL
MCP_HEALTHZ_URL: str = f"{_MCP_BASE}/healthz"


# ---------------------------------------------------------------------------
# Health sub-checks (injectable so unit tests can override them)
# ---------------------------------------------------------------------------
async def db_health_check() -> str:
    """Attempt a SELECT 1 against Postgres.  Returns 'ok' or 'error'."""
    try:
        engine = sqlalchemy.create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        engine.dispose()
        return "ok"
    except Exception:
        return "error"


async def mcp_health_check() -> str:
    """GET the MCP server's /healthz endpoint.  Returns 'ok' or 'error'."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(MCP_HEALTHZ_URL)
            return "ok" if resp.status_code == 200 else "error"
    except Exception:
        return "error"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/healthz")
async def healthz(
    db: str = Depends(db_health_check),
    mcp: str = Depends(mcp_health_check),
) -> dict[str, str]:
    """Liveness check.  Always returns HTTP 200; sub-statuses show degradation."""
    return {"status": "ok", "db": db, "mcp": mcp}
