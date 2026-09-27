"""LangGraph agent graph.

Story 1.1: placeholder. Story 3.1: wires the full skeleton per architecture
§3.2 — `router` + one stub node per phase, checkpointed by `thread_id =
session_id`. Later node stories (3.2-4.4) replace exactly one stub's body
each; the graph shape here (router → phase node → END) is expected to stay
stable, since "end of turn" is simply the graph finishing one `ainvoke` (see
Design Notes in the story spec) — the next user message is a fresh
invocation against the same `thread_id`, restored by the checkpointer.
"""
from __future__ import annotations

from collections.abc import Hashable
from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.llm import LLMFn
from agent.mcp_client import MCPClientProtocol
from agent.nodes.claim import claim
from agent.nodes.clarify import clarify
from agent.nodes.confirm import confirm
from agent.nodes.handoff import handoff
from agent.nodes.intake import intake
from agent.nodes.policy import policy
from agent.nodes.router import route_from_router, router
from agent.nodes.verify import verify
from agent.state import AgentState

# Every key `route_from_router` can return, mapped to the node it should
# reach (or END for the two fast-path terminals with no dedicated node file).
# Node "claim_extract" backs Phase.CLAIM (see agent/nodes/router.py for why
# it isn't named "claim").
_ROUTER_PATH_MAP: dict[Hashable, str] = {
    "intake": "intake",
    "verify": "verify",
    "policy": "policy",
    "claim_extract": "claim_extract",
    "clarify": "clarify",
    "confirm": "confirm",
    "handoff": "handoff",
    "cancelled": END,
    END: END,
}


def build_graph(mcp: MCPClientProtocol, llm: LLMFn, checkpointer: Any) -> CompiledStateGraph:
    """Build and compile the agent's `StateGraph`.

    `mcp` and `llm` are injected once here and bound into every node via
    `functools.partial`, so nodes stay plain functions of `state` for
    LangGraph while still being unit-testable with fakes (`FakeMCPClient`,
    a scripted `llm` callable).

    `checkpointer` is caller-constructed (production: `AsyncPostgresSaver`;
    tests: `MemorySaver`) — this function only wires it into `.compile()`.
    """
    graph = StateGraph(AgentState)

    graph.add_node("router", partial(router, mcp=mcp, llm=llm))
    graph.add_node("intake", partial(intake, mcp=mcp, llm=llm))
    graph.add_node("verify", partial(verify, mcp=mcp, llm=llm))
    graph.add_node("policy", partial(policy, mcp=mcp, llm=llm))
    graph.add_node("claim_extract", partial(claim, mcp=mcp, llm=llm))
    graph.add_node("clarify", partial(clarify, mcp=mcp, llm=llm))
    graph.add_node("confirm", partial(confirm, mcp=mcp, llm=llm))
    graph.add_node("handoff", partial(handoff, mcp=mcp, llm=llm))

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", route_from_router, _ROUTER_PATH_MAP)

    for node_name in ("intake", "verify", "policy", "claim_extract", "clarify", "confirm", "handoff"):
        graph.add_edge(node_name, END)

    return graph.compile(checkpointer=checkpointer)
