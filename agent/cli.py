"""Terminal chat over the compiled agent graph.

Story 3.1: interactive loop over `graph.ainvoke`, one call per typed message
— matching the API shape (`POST /sessions/{id}/messages`, architecture §8)
this graph is built for. Each call re-enters at `router` with the same
`thread_id = session_id`; the Postgres checkpointer restores everything in
between, so this loop itself stays state-free beyond the session id.

Run:
    LLM_MODE=mock uv run python -m agent.cli
    (requires `make up` — the checkpointer needs Postgres.)
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from agent.graph import build_graph
from agent.llm import complete
from agent.mcp_client import MCPClient
from agent.state import Phase
from shared.schemas import ClaimDraft

DEFAULT_DATABASE_URL = "postgresql://claims:claims@localhost:5432/claims"
DEFAULT_MCP_URL = "http://localhost:8765/mcp"

EXIT_WORDS = {"quit", "exit"}


def _psycopg_dsn(database_url: str) -> str:
    """`AsyncPostgresSaver` wants a plain psycopg DSN; `.env` uses the
    SQLAlchemy-style `postgresql+psycopg://` scheme — strip the `+psycopg`.
    """
    return database_url.replace("postgresql+psycopg://", "postgresql://")


def _initial_state(session_id: str) -> dict[str, object]:
    """Full `AgentState` defaults for a brand-new session (no prior checkpoint)."""
    return {
        "session_id": session_id,
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


async def main() -> None:
    database_url = _psycopg_dsn(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    mcp_url = os.environ.get("MCP_URL", DEFAULT_MCP_URL)
    session_id = str(uuid.uuid4())
    mcp = MCPClient(base_url=mcp_url)

    async with AsyncPostgresSaver.from_conn_string(database_url) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(mcp=mcp, llm=complete, checkpointer=checkpointer)
        config: RunnableConfig = {"configurable": {"thread_id": session_id}}

        print(f"Claims Intake Agent — session {session_id}")
        print("Type your message, or 'quit' to exit.\n")

        is_first_turn = True
        while True:
            try:
                text = input("you> ").strip()
            except EOFError:
                break
            if not text:
                continue
            if text.lower() in EXIT_WORDS:
                break

            input_state: dict[str, object] = {
                "session_id": session_id,
                "messages": [HumanMessage(content=text)],
            }
            if is_first_turn:
                input_state = {**_initial_state(session_id), **input_state}
                is_first_turn = False

            result = await graph.ainvoke(input_state, config=config)
            reply = result["messages"][-1]
            print(f"agent> {reply.content}\n")


if __name__ == "__main__":
    if sys.platform == "win32":
        # psycopg's async mode requires a selector loop; asyncio's default
        # ProactorEventLoop on Windows can't run AsyncPostgresSaver.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
