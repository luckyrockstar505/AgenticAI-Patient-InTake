"""LLM gateway stub.

Story 1.1: placeholder with correct signatures from architecture §6.
Story 1.3 implements the real LiteLLM wrapper + MockLLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResult:
    """Wrapper for LLM completion results."""

    content: str
    raw: dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0


def complete(
    messages: list[dict[str, str]],
    *,
    purpose: str,
    schema: type | None = None,
) -> LLMResult:
    """Call the configured LLM.  Story 1.3 provides the real implementation."""
    raise NotImplementedError("LLM gateway not yet implemented — see story 1.3")
