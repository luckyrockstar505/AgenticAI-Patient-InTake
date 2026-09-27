"""Human-handoff node stub (story 3.1 skeleton; story 4.4 fills in real reasons/audit).

Real behaviour (story 4.4): call `mcp.end_session` with the specific reason
(`handoff_user|handoff_locked|handoff_clarify_cap|handoff_error`) and end the
session.

This stub only returns a canned message — no `end_session` call yet.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.state import AgentState

STUB_MESSAGE = "Sure — connecting you with a representative now."


async def handoff(state: AgentState, *, mcp: MCPClientProtocol, llm: LLMFn) -> dict[str, Any]:
    return {"messages": [AIMessage(content=STUB_MESSAGE)]}
