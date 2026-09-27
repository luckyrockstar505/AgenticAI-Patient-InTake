"""Agent state definition.

Story 1.1: stub with correct type signatures from architecture §3.1.
Story 3.1 will wire the full LangGraph state and checkpointer.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from shared.schemas import ClaimDraft


class Phase(str, Enum):
    INTAKE = "intake"
    VERIFY = "verify"
    POLICY = "policy"
    CLAIM = "claim"
    CLARIFY = "clarify"
    CONFIRM = "confirm"
    DONE = "done"
    LOCKED = "locked"
    HANDOFF = "handoff"
    CANCELLED = "cancelled"


class AgentState(TypedDict):
    session_id: str
    messages: Annotated[list[AnyMessage], add_messages]
    phase: Phase
    member_id: str | None
    full_name: str | None
    snapshot_id: str | None
    verification_id: str | None
    verified: bool
    failed_attempts: int
    pending_question_id: str | None
    policy_view: dict[str, Any] | None
    claim: ClaimDraft
    missing_fields: list[str]
    clarify_turns: int
    last_intent: str | None
    case_number: str | None
