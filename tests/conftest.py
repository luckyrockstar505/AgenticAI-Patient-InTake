"""Root-level pytest configuration.

Autouse fixture that blocks any real ``litellm.completion`` call during the
test suite.  If a test somehow triggers an un-patched LLM call the fixture
raises ``AssertionError`` with a clear message pointing at LLM_MODE.

Tests that explicitly need to exercise the Bedrock error-handling path can
override the patch at the test level:

    def test_bedrock_error(monkeypatch):
        monkeypatch.setattr("litellm.completion", lambda *a, **kw: ...)
        ...

Test-level patches take precedence over this autouse fixture.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _block_real_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raise immediately if any test tries to call litellm.completion for real."""

    def _raise(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            f"litellm.completion called in tests — "
            f"LLM_MODE={os.environ.get('LLM_MODE', 'unset')!r}. "
            "All LLM calls must use LLM_MODE=mock."
        )

    monkeypatch.setattr("litellm.completion", _raise)
