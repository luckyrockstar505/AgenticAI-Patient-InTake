"""Verify node stub (story 3.1 skeleton; story 3.4 fills in the challenge loop + lockout).

Real behaviour (story 3.4): call `mcp.check_answer` with the member's answer,
branch on `PENDING|PASSED|FAILED|LOCKED`, track `state.failed_attempts`, and
on PASSED move `state.phase` to POLICY; on LOCKED move to LOCKED and end.

This stub only returns a canned message — no MCP calls, no real verification
(the safety invariant that the LLM never decides pass/fail is preserved by
construction: this stub decides nothing).
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.state import AgentState

STUB_MESSAGE = "Thanks. To verify your identity, what's your date of birth?"


async def verify(state: AgentState, *, mcp: MCPClientProtocol, llm: LLMFn) -> dict[str, Any]:
    return {"messages": [AIMessage(content=STUB_MESSAGE)]}
