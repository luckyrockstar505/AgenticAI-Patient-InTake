"""MLflow tracing stub.

Story 1.1: placeholder with correct interface from architecture §1 / docs/tracing.md.
Story 1.4 implements the real MLflow GenAI tracing integration.
"""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any


@contextmanager
def span(name: str, **attributes: Any) -> Generator[None, None, None]:
    """Context manager that records an MLflow span.

    Story 1.4 provides the real implementation.
    """
    yield
