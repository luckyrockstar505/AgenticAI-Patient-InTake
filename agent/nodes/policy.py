"""Policy display node stub (story 3.1 skeleton; story 3.5 fills in the real render).

Real behaviour (story 3.5): call `mcp.get_policy_view` and render it from a
template — **only** when `state.verified is True` (hard safety invariant,
architecture §3.3). Numbers are template-rendered, never LLM-generated.

This stub only returns a canned message — no MCP calls, no policy_view write.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.state import AgentState

STUB_MESSAGE = "You're verified. Here's your plan summary."


async def policy(state: AgentState, *, mcp: MCPClientProtocol, llm: LLMFn) -> dict[str, Any]:
    return {"messages": [AIMessage(content=STUB_MESSAGE)]}
