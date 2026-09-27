"""Unit tests for GET /healthz.

Uses FastAPI dependency overrides so no real DB or MCP connection is needed.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app, db_health_check, mcp_health_check


# ---------------------------------------------------------------------------
# Override both dependencies to return "ok" without real infra
# ---------------------------------------------------------------------------
async def _always_ok() -> str:
    return "ok"


@pytest.fixture(autouse=True)
def _override_health_deps():
    """Set dependency overrides for every test in this module; clean up after."""
    app.dependency_overrides[db_health_check] = _always_ok
    app.dependency_overrides[mcp_health_check] = _always_ok
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def test_healthz_returns_200(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200


def test_healthz_status_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    data = response.json()
    assert data["status"] == "ok"


def test_healthz_db_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    data = response.json()
    assert data["db"] == "ok"


def test_healthz_mcp_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    data = response.json()
    assert data["mcp"] == "ok"
