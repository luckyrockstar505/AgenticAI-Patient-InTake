"""LLM gateway — the only module allowed to import litellm (see CLAUDE.md).

Story 1.3: real LiteLLM (Bedrock) wrapper + MockLLM for tests/CI.
"""
from __future__ import annotations

import glob
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import litellm
import yaml
from pydantic import BaseModel, ValidationError

ModelTier = Literal["default", "fast"]

# Type of `complete()` itself — nodes type-hint their injected `llm` param
# against this so tests can pass a stand-in callable instead of the real
# gateway. Kept here (not in agent/nodes) so nothing outside this module
# needs to import litellm transitively.
LLMFn = Callable[..., "LLMResult"]

MOCK_SCRIPTS_GLOB = str(Path(__file__).parent.parent / "tests" / "fakes" / "llm_scripts" / "*.yaml")
RETRY_COUNT = 2
TIMEOUT_SECONDS = 20.0

REPAIR_PROMPT_MARKER = "valid JSON matching this schema"


class LLMGatewayError(Exception):
    """Base error for the LLM gateway."""


class LLMStructuredOutputError(LLMGatewayError):
    """Raised when structured output still doesn't match `schema` after the repair retry."""


class LLMMockUnmatchedError(LLMGatewayError):
    """Raised in mock mode when no script matches the requested purpose + last user message."""


@dataclass
class LLMResult:
    """Result of an LLM completion call."""

    content: str
    parsed: BaseModel | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


# A caller takes the full message history and returns one raw (unparsed) LLMResult.
_Caller = Callable[[list[dict[str, str]]], LLMResult]


def complete(
    messages: list[dict[str, str]],
    *,
    purpose: str,
    schema: type[BaseModel] | None = None,
    model_tier: ModelTier = "default",
) -> LLMResult:
    """Call the configured LLM and return an `LLMResult`.

    Routes to Bedrock (via LiteLLM) or a scripted mock depending on `LLM_MODE`.
    When `schema` is given, `LLMResult.parsed` is a validated instance of it —
    one repair retry is attempted on invalid JSON before raising.
    """
    mode = os.environ.get("LLM_MODE", "mock")
    if mode == "mock":
        caller = _mock_caller(purpose)
    elif mode == "bedrock":
        caller = _bedrock_caller(model_tier, schema)
    else:
        raise LLMGatewayError(f"Unknown LLM_MODE={mode!r}; expected 'mock' or 'bedrock'")
    return _call_with_repair(messages, purpose=purpose, schema=schema, caller=caller)


def _call_with_repair(
    messages: list[dict[str, str]],
    *,
    purpose: str,
    schema: type[BaseModel] | None,
    caller: _Caller,
) -> LLMResult:
    result = caller(messages)
    if schema is None:
        return result

    parsed = _try_parse(result.content, schema)
    if parsed is not None:
        result.parsed = parsed
        return result

    # One repair retry: ask the model (or mock script) to fix its own output.
    repair_messages = [
        *messages,
        {"role": "assistant", "content": result.content},
        {
            "role": "user",
            "content": (
                f"Your last response was not {REPAIR_PROMPT_MARKER}. "
                f"Return ONLY valid JSON matching this schema: {schema.model_json_schema()}"
            ),
        },
    ]
    repair_result = caller(repair_messages)
    repair_result.latency_ms += result.latency_ms
    repair_result.input_tokens += result.input_tokens
    repair_result.output_tokens += result.output_tokens
    repair_result.cost_usd += result.cost_usd

    parsed = _try_parse(repair_result.content, schema)
    if parsed is None:
        raise LLMStructuredOutputError(
            f"purpose={purpose!r}: response did not match schema after one repair retry"
        )
    repair_result.parsed = parsed
    return repair_result


def _try_parse(content: str, schema: type[BaseModel]) -> BaseModel | None:
    try:
        return schema.model_validate_json(content)
    except (ValidationError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Bedrock (via LiteLLM)
# ---------------------------------------------------------------------------
def _model_for_tier(model_tier: ModelTier) -> str:
    env_var = "LLM_MODEL_DEFAULT" if model_tier == "default" else "LLM_MODEL_FAST"
    model = os.environ.get(env_var)
    if not model:
        raise LLMGatewayError(f"{env_var} is not set")
    return model


def _bedrock_caller(model_tier: ModelTier, schema: type[BaseModel] | None) -> _Caller:
    model = _model_for_tier(model_tier)

    def call(msgs: list[dict[str, str]]) -> LLMResult:
        start = time.perf_counter()
        response = litellm.completion(
            model=model,
            messages=msgs,
            response_format=schema if schema is not None else None,
            num_retries=RETRY_COUNT,
            timeout=TIMEOUT_SECONDS,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        if not response.choices:
            raise LLMGatewayError("Empty choices list returned by model")
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        try:
            cost_usd = litellm.completion_cost(completion_response=response)
        except Exception:
            cost_usd = 0.0
        return LLMResult(
            content=content,
            raw=response.model_dump() if hasattr(response, "model_dump") else dict(response),
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )

    return call


# ---------------------------------------------------------------------------
# Mock (tests / CI)
# ---------------------------------------------------------------------------
@dataclass
class _MockRule:
    pattern: re.Pattern[str]
    response: str


def _load_mock_scripts() -> dict[str, list[_MockRule]]:
    scripts: dict[str, list[_MockRule]] = {}
    for path in sorted(glob.glob(MOCK_SCRIPTS_GLOB)):
        with open(path, encoding="utf-8") as f:
            try:
                doc = yaml.safe_load(f) or {}
            except yaml.YAMLError:
                continue
        purpose = doc.get("purpose")
        if not purpose:
            continue
        rules = [
            _MockRule(pattern=re.compile(m["pattern"], re.IGNORECASE), response=m["response"])
            for m in doc.get("matches", [])
            if "pattern" in m and "response" in m
        ]
        scripts.setdefault(purpose, []).extend(rules)
    return scripts


def _last_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _mock_caller(purpose: str) -> _Caller:
    def call(msgs: list[dict[str, str]]) -> LLMResult:
        scripts = _load_mock_scripts()
        rules = scripts.get(purpose, [])
        last_user_message = _last_user_message(msgs)

        for rule in rules:
            if rule.pattern.search(last_user_message):
                return LLMResult(content=rule.response, latency_ms=0.0)

        raise LLMMockUnmatchedError(
            f"No mock script matched purpose={purpose!r} for input {last_user_message!r} "
            f"(looked in {MOCK_SCRIPTS_GLOB})"
        )

    return call
