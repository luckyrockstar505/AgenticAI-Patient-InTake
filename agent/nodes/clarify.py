"""Clarify-loop node stub (story 3.1 skeleton; story 4.2 fills in gap detection).

Real behaviour (story 4.2): ask exactly one missing-field question per turn
from the bank in `docs/intents.md`, in priority order, incrementing
`state.clarify_turns` and looping back to claim-extraction until complete or
`MAX_CLARIFY_TURNS` is hit.

This stub only returns a canned message — no gap-detection logic.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.state import AgentState

STUB_MESSAGE = "I just need a bit more detail to finish your claim."


async def clarify(state: AgentState, *, mcp: MCPClientProtocol, llm: LLMFn) -> dict[str, Any]:
    return {"messages": [AIMessage(content=STUB_MESSAGE)]}
