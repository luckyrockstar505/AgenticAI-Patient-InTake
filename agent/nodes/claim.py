"""Claim-extraction node stub (story 3.1 skeleton; story 4.1 fills in NL extraction).

Real behaviour (story 4.1): LiteLLM structured-output extraction into
`ClaimDraft` (`purpose="claim_extract"`), merged into the existing draft
(never overwrite a confirmed value with `None`), then gap-detection decides
CLARIFY vs CONFIRM (story 4.2).

This stub only returns a canned message — no LLM extraction calls.
"""
from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.state import AgentState

STUB_MESSAGE = "Go ahead and tell me what happened, and I'll help you file the claim."


async def claim(state: AgentState, *, mcp: MCPClientProtocol, llm: LLMFn) -> dict[str, Any]:
    return {"messages": [AIMessage(content=STUB_MESSAGE)]}
