"""Unit tests for api.main module-level configuration derived from env vars."""
from __future__ import annotations

import importlib

import pytest


def test_mcp_healthz_url_derived_from_mcp_url_ending_with_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """MCP_HEALTHZ_URL replaces /mcp suffix with /healthz."""
    monkeypatch.setenv("MCP_URL", "http://mcp-tools:8765/mcp")
    monkeypatch.setenv("APP_ENV", "test")
    import api.main as main_module
    importlib.reload(main_module)
    assert main_module.MCP_HEALTHZ_URL == "http://mcp-tools:8765/healthz"


def test_mcp_healthz_url_when_mcp_url_does_not_end_with_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """When MCP_URL does not end with /mcp, /healthz is appended to the full URL."""
    monkeypatch.setenv("MCP_URL", "http://mcp-tools:8765")
    monkeypatch.setenv("APP_ENV", "test")
    import api.main as main_module
    importlib.reload(main_module)
    assert main_module.MCP_HEALTHZ_URL == "http://mcp-tools:8765/healthz"
