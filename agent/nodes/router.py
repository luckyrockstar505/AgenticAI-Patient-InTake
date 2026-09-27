"""Global router node — phase-based stub router (stories 3.1 + 3.2).

Per architecture §3.2:

    START → router ─┬─(intent=cancel)───────► cancelled → END
                    ├─(intent=handoff)──────► handoff → END
                    └─(by phase) ─► <phase node>

This implements the regex fast-paths from `docs/intents.md` ("Regex
fast-paths run before the LLM") plus phase-based dispatch — no LLM intent
classification. Fast-model classification into `IntentResult`, a per-phase
allowed-intents policy table, and abuse/prompt-injection handling are real,
un-built scope — see `_bmad-output/implementation-artifacts/deferred-work.md`
(not yet assigned a story number). Every user message re-enters the graph at
this node.
"""
from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.graph import END

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.state import AgentState, Phase

# docs/intents.md: "Regex fast-paths run before the LLM"
CANCEL_RE = re.compile(r"\b(cancel|stop|quit)\b", re.IGNORECASE)
HANDOFF_RE = re.compile(r"\b(agent|human|representative|person)\b", re.IGNORECASE)

CANCELLED_MESSAGE = "No problem — I've cancelled this request. Nothing was submitted."

# Phases that map 1:1 onto a node file in agent/nodes/. The CLAIM phase's
# graph node is registered as "claim_extract" (matching architecture §3.2 /
# tracing.md's `node.claim_extract`) because LangGraph forbids a node name
# equal to an existing state key, and `claim` is already `AgentState.claim`.
_PHASE_TO_NODE: dict[Phase, str] = {
    Phase.INTAKE: "intake",
    Phase.VERIFY: "verify",
    Phase.POLICY: "policy",
    Phase.CLAIM: "claim_extract",
    Phase.CLARIFY: "clarify",
    Phase.CONFIRM: "confirm",
}


def _last_human_text(messages: list[AnyMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


async def router(state: AgentState, *, mcp: MCPClientProtocol, llm: LLMFn) -> dict[str, Any]:
    """Classify the cancel/handoff fast-paths; real intent classification is deferred (unassigned story).

    Never calls `mcp` or `llm` — routing here is pure regex + `state.phase`.
    """
    text = _last_human_text(state.get("messages", []))

    if CANCEL_RE.search(text):
        return {
            "last_intent": "cancel",
            "phase": Phase.CANCELLED,
            "messages": [AIMessage(content=CANCELLED_MESSAGE)],
        }

    if HANDOFF_RE.search(text):
        return {"last_intent": "request_human"}

    return {"last_intent": None}


def route_from_router(state: AgentState) -> str:
    """Conditional-edge function: where does the turn go after `router`?

    Table-driven per the I/O matrix: cancel/handoff fast-paths win regardless
    of phase; otherwise dispatch strictly on `state.phase`.
    """
    if state.get("last_intent") == "cancel":
        return "cancelled"
    if state.get("last_intent") == "request_human":
        return "handoff"

    phase = state.get("phase", Phase.INTAKE)
    return _PHASE_TO_NODE.get(phase, END)
