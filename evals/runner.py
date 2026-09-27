"""Eval runner stub.

Story 1.1: exits 0 with "no scenarios" message so `make eval` succeeds even
with an empty dataset.  Story 6.1 replaces this with the real harness.

Usage:
    python -m evals.runner
    python -m evals.runner --mode mock
    python -m evals.runner --mode live
"""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Claims Intake Agent eval runner")
    parser.add_argument(
        "--mode",
        choices=["mock", "live"],
        default="mock",
        help="LLM mode to use for evals (default: mock)",
    )
    args = parser.parse_args()

    print(f"[evals] mode={args.mode}  no scenarios yet — story 6.1 adds the harness")
    sys.exit(0)


if __name__ == "__main__":
    main()
