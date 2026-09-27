"""Typed MCP client stub.

Story 1.1: placeholder with correct interface from architecture §7.
Story 2.3 / 2.4 / 2.5 implement the real tool calls.
"""
from __future__ import annotations

from typing import Any


class MCPClient:
    """Thin typed wrapper over the MCP streamable-http transport."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call a named MCP tool.  Story 2.x provides real implementations."""
        raise NotImplementedError(f"MCP tool '{name}' not yet implemented")

    async def ping(self) -> dict[str, bool]:
        """Ping the MCP server."""
        return await self.call_tool("ping", {})
