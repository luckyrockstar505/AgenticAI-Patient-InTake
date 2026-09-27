"""Checkpoint-resume integration test (story 3.1, AC3).

Requires a live Postgres (`make up`, or any reachable instance via
`DATABASE_URL`) — this is the one test in the suite allowed to touch a real
service (CLAUDE.md: "A test that touches the network is a bug" applies to
*unit* tests; this lives under `tests/integration` and is marked
`integration` precisely so `make test` (unit only) never runs it).

Simulates "process restart" by dropping the first `AsyncPostgresSaver` /
compiled graph and building a brand-new one against the same Postgres
before reading state back — i.e. nothing is held in Python-process memory
between the two halves of the test.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from agent.graph import build_graph
from agent.llm import LLMResult
from agent.state import Phase
from shared.schemas import ClaimDraft
from tests.fakes.fake_mcp import FakeMCPClient

pytestmark = pytest.mark.integration

DEFAULT_TEST_DATABASE_URL = "postgresql://claims:claims@localhost:5432/claims"


def _dsn() -> str:
    raw = os.environ.get("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    return raw.replace("postgresql+psycopg://", "postgresql://")


def _unexpected_llm_call(*args: Any, **kwargs: Any) -> LLMResult:
    raise AssertionError("stub nodes must never call the LLM")


def _initial_state(session_id: str, message: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "session_id": session_id,
        "messages": [HumanMessage(content=message)],
        "phase": Phase.VERIFY,
        "member_id": "ABC100000001",
        "full_name": "Jane Doe",
        "snapshot_id": "test-snapshot-id",
        "verification_id": "test-verification-id",
        "verified": False,
        "failed_attempts": 1,
        "pending_question_id": "zip",
        "policy_view": None,
        "claim": ClaimDraft(),
        "missing_fields": [],
        "clarify_turns": 0,
        "last_intent": None,
        "case_number": None,
    }
    base.update(overrides)
    return base


async def test_state_survives_a_simulated_process_restart() -> None:
    session_id = f"resume-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": session_id}}

    # --- "process 1": start a session, checkpoint some state -------------
    async with AsyncPostgresSaver.from_conn_string(_dsn()) as checkpointer_1:
        await checkpointer_1.setup()
        graph_1 = build_graph(mcp=FakeMCPClient(), llm=_unexpected_llm_call, checkpointer=checkpointer_1)
        first_input = _initial_state(session_id, "95814")
        result_1 = await graph_1.ainvoke(first_input, config=config)

        assert result_1["member_id"] == "ABC100000001"
        assert result_1["failed_attempts"] == 1
        assert result_1["phase"] == Phase.VERIFY

    # --- "process 2": brand-new saver + brand-new compiled graph, same DB
    async with AsyncPostgresSaver.from_conn_string(_dsn()) as checkpointer_2:
        await checkpointer_2.setup()
        graph_2 = build_graph(mcp=FakeMCPClient(), llm=_unexpected_llm_call, checkpointer=checkpointer_2)

        restored = await graph_2.aget_state(config)
        assert restored.values["member_id"] == "ABC100000001"
        assert restored.values["full_name"] == "Jane Doe"
        assert restored.values["snapshot_id"] == "test-snapshot-id"
        assert restored.values["verification_id"] == "test-verification-id"
        assert restored.values["failed_attempts"] == 1
        assert restored.values["pending_question_id"] == "zip"
        assert restored.values["phase"] == Phase.VERIFY

        # A brand-new turn, sending only the delta (session_id + new
        # message) — exactly what api/ will do — must not re-ask anything:
        # all previously-set fields stay put without being resent.
        second_input = {"session_id": session_id, "messages": [HumanMessage(content="03/04/1985")]}
        result_2 = await graph_2.ainvoke(second_input, config=config)

        assert result_2["member_id"] == "ABC100000001"
        assert result_2["full_name"] == "Jane Doe"
        assert result_2["failed_attempts"] == 1
        assert result_2["messages"][-1].content  # verify stub still replies


async def test_missing_checkpoint_is_treated_as_a_fresh_session() -> None:
    """Edge case from the I/O matrix: an unknown thread_id is a fresh session, not an error."""
    session_id = f"never-seen-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": session_id}}

    async with AsyncPostgresSaver.from_conn_string(_dsn()) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(mcp=FakeMCPClient(), llm=_unexpected_llm_call, checkpointer=checkpointer)

        existing = await graph.aget_state(config)
        assert existing.values == {}

        result = await graph.ainvoke(
            {
                "session_id": session_id,
                "messages": [HumanMessage(content="hi")],
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
            },
            config=config,
        )
        assert result["phase"] == Phase.INTAKE
