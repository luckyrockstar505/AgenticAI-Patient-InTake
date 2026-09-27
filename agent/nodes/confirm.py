"""Confirm / create-case node stub (story 3.1 skeleton; story 4.3 fills in the real flow).

Real behaviour (story 4.3): render the claim summary from a template, and
only call `mcp.create_case` when verification is PASSED **and** the user's
intent in this phase is an explicit `confirm` (hard safety invariant,
architecture §3.3 / CLAUDE.md) — never on `acknowledge` or low-confidence
intent.

This stub only returns a canned message — no `create_case` call, so no case
can be created by this story's code.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.state import AgentState

STUB_MESSAGE = "Here's a summary of your claim — does everything look right?"


async def confirm(state: AgentState, *, mcp: MCPClientProtocol, llm: LLMFn) -> dict[str, Any]:
    return {"messages": [AIMessage(content=STUB_MESSAGE)]}
