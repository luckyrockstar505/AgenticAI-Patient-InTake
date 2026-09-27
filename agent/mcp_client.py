"""Typed MCP client — the seam described in `docs/contracts/mcp-tools.md`.

Story 1.1: placeholder with correct interface from architecture §7.
Story 3.1: real streamable-http transport (via the `mcp` client library) plus
one typed async method per contract tool. `tests/fakes/fake_mcp.py` implements
the same method surface (`MCPClientProtocol`) in-memory so nodes and tests can
swap implementations without changing call sites.

Story 2.3 / 2.4 / 2.5 land the actual `mcp_tools/` server-side tools this talks to.
"""
from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent


@runtime_checkable
class MCPClientProtocol(Protocol):
    """The async method surface nodes depend on.

    `agent.mcp_client.MCPClient` (real, streamable-http) and
    `tests.fakes.fake_mcp.FakeMCPClient` (in-memory, seed-JSON backed) both
    satisfy this structurally — nodes type-hint against the protocol, not a
    concrete class, so tests can inject the fake.
    """

    async def fetch_coverage(self, session_id: str, member_id: str) -> dict[str, Any]: ...

    async def start_verification(
        self, session_id: str, member_id: str, full_name: str
    ) -> dict[str, Any]: ...

    async def check_answer(
        self, session_id: str, verification_id: str, question_id: str, answer: str
    ) -> dict[str, Any]: ...

    async def get_policy_view(self, session_id: str, verification_id: str) -> dict[str, Any]: ...

    async def create_case(
        self, session_id: str, verification_id: str, claim: dict[str, Any]
    ) -> dict[str, Any]: ...

    async def get_case(self, case_number: str) -> dict[str, Any]: ...

    async def end_session(self, session_id: str, reason: str) -> dict[str, Any]: ...


class MCPClient:
    """Thin typed wrapper over the MCP streamable-http transport.

    Every public method returns the tool's JSON envelope exactly as documented
    in `docs/contracts/mcp-tools.md`: `{"ok": true, "data": {...}}` or
    `{"ok": false, "error": {"code": ..., "message": ...}}`. Callers (nodes)
    branch on `"ok"` — tools never raise for business errors, so neither does
    this client.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a named MCP tool over a fresh streamable-http session.

        Opens/tears down a connection per call — simplest correct thing for
        this skeleton; a later story may switch to a pooled/persistent
        session if latency becomes a concern.
        """
        arguments = arguments or {}
        async with streamablehttp_client(self.base_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)

        if result.structuredContent is not None:
            return result.structuredContent
        for block in result.content:
            if isinstance(block, TextContent):
                try:
                    parsed: dict[str, Any] = json.loads(block.text)
                    return parsed
                except json.JSONDecodeError:
                    continue
        if result.isError:
            return {"ok": False, "error": {"code": "INTERNAL", "message": f"tool '{name}' failed"}}
        return {}

    async def ping(self) -> dict[str, bool]:
        """Ping the MCP server."""
        return await self.call_tool("ping", {})

    # ------------------------------------------------------------------
    # Contract tools (docs/contracts/mcp-tools.md)
    # ------------------------------------------------------------------
    async def fetch_coverage(self, session_id: str, member_id: str) -> dict[str, Any]:
        """§1 fetch_coverage — never returns the coverage payload itself."""
        return await self.call_tool(
            "fetch_coverage", {"session_id": session_id, "member_id": member_id}
        )

    async def start_verification(
        self, session_id: str, member_id: str, full_name: str
    ) -> dict[str, Any]:
        """§2 start_verification — creates/returns the verification record."""
        return await self.call_tool(
            "start_verification",
            {"session_id": session_id, "member_id": member_id, "full_name": full_name},
        )

    async def check_answer(
        self, session_id: str, verification_id: str, question_id: str, answer: str
    ) -> dict[str, Any]:
        """§3 check_answer — the LLM never sees expected answers; this does the check."""
        return await self.call_tool(
            "check_answer",
            {
                "session_id": session_id,
                "verification_id": verification_id,
                "question_id": question_id,
                "answer": answer,
            },
        )

    async def get_policy_view(self, session_id: str, verification_id: str) -> dict[str, Any]:
        """§4 get_policy_view — only succeeds when verification is PASSED."""
        return await self.call_tool(
            "get_policy_view",
            {"session_id": session_id, "verification_id": verification_id},
        )

    async def create_case(
        self, session_id: str, verification_id: str, claim: dict[str, Any]
    ) -> dict[str, Any]:
        """§5 create_case — server-side gate on verification PASSED + required fields."""
        return await self.call_tool(
            "create_case",
            {"session_id": session_id, "verification_id": verification_id, "claim": claim},
        )

    async def get_case(self, case_number: str) -> dict[str, Any]:
        """§6 get_case — ops/demo view."""
        return await self.call_tool("get_case", {"case_number": case_number})

    async def end_session(self, session_id: str, reason: str) -> dict[str, Any]:
        """§7 end_session — idempotent; discards unverified snapshots server-side."""
        return await self.call_tool("end_session", {"session_id": session_id, "reason": reason})
