"""Table-driven routing tests for the LangGraph skeleton (story 3.1).

Two layers:
  1. `route_from_router` in isolation — table-driven phase/intent -> node.
  2. The compiled graph end-to-end (FakeMCPClient + MemorySaver, no network,
     no Postgres) — confirms canned messages, no MCP calls, and that the
     cancel/handoff fast-paths bypass phase logic (I/O matrix rows 1-3).
"""
from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END

from agent.graph import build_graph
from agent.llm import LLMResult
from agent.nodes.claim import STUB_MESSAGE as CLAIM_MESSAGE
from agent.nodes.clarify import STUB_MESSAGE as CLARIFY_MESSAGE
from agent.nodes.confirm import STUB_MESSAGE as CONFIRM_MESSAGE
from agent.nodes.handoff import STUB_MESSAGE as HANDOFF_MESSAGE
from agent.nodes.intake import STUB_MESSAGE as INTAKE_MESSAGE
from agent.nodes.policy import STUB_MESSAGE as POLICY_MESSAGE
from agent.nodes.router import CANCELLED_MESSAGE, route_from_router
from agent.nodes.verify import STUB_MESSAGE as VERIFY_MESSAGE
from agent.state import Phase
from shared.schemas import ClaimDraft
from tests.fakes.fake_mcp import FakeMCPClient


def _unexpected_llm_call(*args: Any, **kwargs: Any) -> LLMResult:
    raise AssertionError("stub nodes must never call the LLM")


def _full_state(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "session_id": "s-test",
        "messages": [],
        "phase": Phase.INTAKE,
        "member_id": None,
        "full_name": None,
        "snapshot_id": None,
        "verification_id": None,
        "verified": False,
        "failed_attempts": 0,
        "pending_question_id": None,
        "policy_view": None,
        "claim": ClaimDraft(),
        "missing_fields": [],
        "clarify_turns": 0,
        "last_intent": None,
        "case_number": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. `route_from_router` in isolation — table-driven.
# ---------------------------------------------------------------------------
ROUTING_TABLE: list[tuple[Phase | None, str | None, str]] = [
    # (phase, last_intent, expected destination)
    (Phase.INTAKE, None, "intake"),
    (Phase.VERIFY, None, "verify"),
    (Phase.POLICY, None, "policy"),
    (Phase.CLAIM, None, "claim_extract"),
    (Phase.CLARIFY, None, "clarify"),
    (Phase.CONFIRM, None, "confirm"),
    # Fast-paths win regardless of phase.
    (Phase.INTAKE, "cancel", "cancelled"),
    (Phase.VERIFY, "cancel", "cancelled"),
    (Phase.CONFIRM, "cancel", "cancelled"),
    (Phase.INTAKE, "request_human", "handoff"),
    (Phase.POLICY, "request_human", "handoff"),
    (Phase.CLARIFY, "request_human", "handoff"),
    # Terminal phases with no fast-path fall straight to END.
    (Phase.DONE, None, END),
    (Phase.LOCKED, None, END),
    (Phase.HANDOFF, None, END),
    (Phase.CANCELLED, None, END),
]


@pytest.mark.parametrize("phase,last_intent,expected", ROUTING_TABLE)
def test_route_from_router(phase: Phase, last_intent: str | None, expected: str) -> None:
    state = _full_state(phase=phase, last_intent=last_intent)
    assert route_from_router(state) == expected


# ---------------------------------------------------------------------------
# 2. Full compiled graph, in-memory checkpointer + fake MCP.
# ---------------------------------------------------------------------------
@pytest.fixture
def graph() -> Any:
    mcp = FakeMCPClient()
    compiled = build_graph(mcp=mcp, llm=_unexpected_llm_call, checkpointer=MemorySaver())
    return compiled, mcp


@pytest.mark.parametrize(
    "phase,expected_message",
    [
        (Phase.INTAKE, INTAKE_MESSAGE),
        (Phase.VERIFY, VERIFY_MESSAGE),
        (Phase.POLICY, POLICY_MESSAGE),
        (Phase.CLAIM, CLAIM_MESSAGE),
        (Phase.CLARIFY, CLARIFY_MESSAGE),
        (Phase.CONFIRM, CONFIRM_MESSAGE),
    ],
)
async def test_normal_dispatch_by_phase(graph: Any, phase: Phase, expected_message: str) -> None:
    compiled, mcp = graph
    state = _full_state(phase=phase, messages=[HumanMessage(content="hi there")])
    result = await compiled.ainvoke(state, config={"configurable": {"thread_id": f"t-{phase.value}"}})

    assert result["messages"][-1].content == expected_message
    assert result["phase"] == phase  # stub nodes don't advance the phase
    assert mcp.calls == []  # AC: no MCP tool call for a canned stub reply


@pytest.mark.parametrize("phase", [Phase.INTAKE, Phase.VERIFY, Phase.POLICY, Phase.CONFIRM])
async def test_cancel_fast_path_bypasses_phase(graph: Any, phase: Phase) -> None:
    compiled, mcp = graph
    state = _full_state(phase=phase, messages=[HumanMessage(content="never mind, please cancel")])
    result = await compiled.ainvoke(state, config={"configurable": {"thread_id": f"cancel-{phase.value}"}})

    assert result["phase"] == Phase.CANCELLED
    assert result["messages"][-1].content == CANCELLED_MESSAGE
    assert mcp.calls == []


@pytest.mark.parametrize("phase", [Phase.INTAKE, Phase.POLICY, Phase.CLARIFY])
async def test_handoff_fast_path_bypasses_phase(graph: Any, phase: Phase) -> None:
    compiled, mcp = graph
    state = _full_state(phase=phase, messages=[HumanMessage(content="let me talk to a human")])
    result = await compiled.ainvoke(state, config={"configurable": {"thread_id": f"handoff-{phase.value}"}})

    assert result["messages"][-1].content == HANDOFF_MESSAGE
    assert mcp.calls == []


async def test_fresh_session_no_mcp_calls(graph: Any) -> None:
    """AC: fresh session, phase=INTAKE -> routes to intake, no MCP tool call."""
    compiled, mcp = graph
    state = _full_state(phase=Phase.INTAKE, messages=[HumanMessage(content="ABC100000001 Jane Doe")])
    result = await compiled.ainvoke(state, config={"configurable": {"thread_id": "fresh-session"}})

    assert result["messages"][-1].content == INTAKE_MESSAGE
    assert mcp.calls == []
