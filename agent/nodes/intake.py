"""Intake node stub (story 3.1 skeleton; story 3.3 fills in real member-id/name intake).

Real behaviour (story 3.3): parse `member_id` + `full_name` out of the user's
message, validate the member-ID shape, then call `mcp.fetch_coverage` and
`mcp.start_verification` and move `state.phase` to VERIFY.

This stub only returns a canned message — no MCP calls, no extraction.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.state import AgentState

STUB_MESSAGE = (
    "Hi, I'm here to help with your claim. To get started, could you share "
    "your member ID and your full name?"
)


async def intake(state: AgentState, *, mcp: MCPClientProtocol, llm: LLMFn) -> dict[str, Any]:
    return {"messages": [AIMessage(content=STUB_MESSAGE)]}
