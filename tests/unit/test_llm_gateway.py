"""Unit tests for agent/llm.py — mock mode matching + bedrock kwargs."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from agent import llm


class _Person(BaseModel):
    name: str
    age: int


@pytest.fixture(autouse=True)
def _mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "mock")


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------
def test_mock_matches_purpose_and_pattern() -> None:
    result = llm.complete([{"role": "user", "content": "hello"}], purpose="test_greet")
    assert result.content == "hi there"


def test_mock_unmatched_raises_named_error() -> None:
    with pytest.raises(llm.LLMMockUnmatchedError, match="test_greet"):
        llm.complete([{"role": "user", "content": "goodbye"}], purpose="test_greet")


def test_mock_unknown_purpose_raises() -> None:
    with pytest.raises(llm.LLMMockUnmatchedError, match="no_such_purpose"):
        llm.complete([{"role": "user", "content": "hello"}], purpose="no_such_purpose")


def test_mock_schema_repair_succeeds() -> None:
    result = llm.complete(
        [{"role": "user", "content": "please extract the person"}],
        purpose="test_schema",
        schema=_Person,
    )
    assert result.parsed == _Person(name="Ann", age=30)


def test_mock_schema_unrepairable_raises() -> None:
    with pytest.raises(llm.LLMStructuredOutputError, match="test_schema_unrepairable"):
        llm.complete(
            [{"role": "user", "content": "please extract the person"}],
            purpose="test_schema_unrepairable",
            schema=_Person,
        )


# ---------------------------------------------------------------------------
# Bedrock mode (litellm patched)
# ---------------------------------------------------------------------------
class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 5


class _FakeMessage:
    content = '{"name": "Ann", "age": 30}'


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]
    usage = _FakeUsage()

    def model_dump(self) -> dict[str, Any]:
        return {"fake": True}


def test_bedrock_builds_correct_litellm_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "bedrock")
    monkeypatch.setenv("LLM_MODEL_DEFAULT", "bedrock/test-default-model")

    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> _FakeResponse:
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(llm.litellm, "completion", fake_completion)
    monkeypatch.setattr(llm.litellm, "completion_cost", lambda **_: 0.001)

    result = llm.complete(
        [{"role": "user", "content": "hi"}],
        purpose="test_bedrock",
        schema=_Person,
    )

    assert captured["model"] == "bedrock/test-default-model"
    assert captured["num_retries"] == llm.RETRY_COUNT
    assert captured["timeout"] == llm.TIMEOUT_SECONDS
    assert captured["response_format"] is _Person
    assert result.parsed == _Person(name="Ann", age=30)
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert result.cost_usd == 0.001


def test_bedrock_uses_fast_tier_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "bedrock")
    monkeypatch.setenv("LLM_MODEL_DEFAULT", "bedrock/test-default-model")
    monkeypatch.setenv("LLM_MODEL_FAST", "bedrock/test-fast-model")

    captured: dict[str, Any] = {}

    def fake_completion(**kwargs: Any) -> _FakeResponse:
        captured.update(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(llm.litellm, "completion", fake_completion)
    monkeypatch.setattr(llm.litellm, "completion_cost", lambda **_: 0.0)

    llm.complete(
        [{"role": "user", "content": "hi"}],
        purpose="test_bedrock_fast",
        model_tier="fast",
    )

    assert captured["model"] == "bedrock/test-fast-model"


def test_bedrock_missing_model_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "bedrock")
    monkeypatch.delenv("LLM_MODEL_DEFAULT", raising=False)

    with pytest.raises(llm.LLMGatewayError, match="LLM_MODEL_DEFAULT"):
        llm.complete([{"role": "user", "content": "hi"}], purpose="test_bedrock")


def test_unknown_llm_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODE", "not-a-real-mode")
    with pytest.raises(llm.LLMGatewayError, match="not-a-real-mode"):
        llm.complete([{"role": "user", "content": "hi"}], purpose="test_greet")
