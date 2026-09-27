"""Integration test fixtures.

Windows note: psycopg's async mode refuses to run on the default
`ProactorEventLoop`. Switch to the selector-based policy for this whole
directory so `AsyncPostgresSaver` (used by `test_checkpoint_resume.py`)
works under `pytest-asyncio` on Windows dev machines; a no-op on Linux/macOS
and in CI.
"""
from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
