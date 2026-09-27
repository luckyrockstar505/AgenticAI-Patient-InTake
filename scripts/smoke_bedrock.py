#!/usr/bin/env python3
"""Manual smoke test for the Bedrock LLM gateway.

Requires a real AWS profile with Bedrock model access enabled — see the
"Enabling Bedrock model access" section in README.md before running this.

Usage:
    AWS_PROFILE=<profile> LLM_MODE=bedrock uv run python scripts/smoke_bedrock.py
"""
from __future__ import annotations

import os
import sys

from agent.llm import LLMGatewayError, complete


def main() -> int:
    os.environ.setdefault("LLM_MODE", "bedrock")
    if os.environ.get("LLM_MODE") != "bedrock":
        print("LLM_MODE must be 'bedrock' for this smoke test.", file=sys.stderr)
        return 1

    try:
        result = complete(
            [{"role": "user", "content": "Reply with exactly the word: pong"}],
            purpose="smoke_test",
            model_tier="fast",
        )
    except LLMGatewayError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"content:     {result.content!r}")
    print(f"input_tokens:  {result.input_tokens}")
    print(f"output_tokens: {result.output_tokens}")
    print(f"cost_usd:      {result.cost_usd}")
    print(f"latency_ms:    {result.latency_ms:.1f}")
    print("OK — Bedrock reachable and responding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
