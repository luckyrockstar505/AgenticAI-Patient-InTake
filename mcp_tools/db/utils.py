"""Database URL normalisation utilities.

Provides a single function for rewriting legacy PostgreSQL driver prefixes
to the psycopg3 async driver prefix expected by the application.
"""
from __future__ import annotations


def normalise_db_url(url: str) -> str:
    """Ensure a PostgreSQL URL uses the psycopg3 driver prefix.

    Converts:
      ``postgresql://``         → ``postgresql+psycopg://``
      ``postgresql+psycopg2://`` → ``postgresql+psycopg://``

    Any URL that already uses ``postgresql+psycopg://`` (or a non-PostgreSQL
    scheme) is returned unchanged.
    """
    if url.startswith("postgresql://"):
        return "postgresql+psycopg" + url[len("postgresql"):]
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql+psycopg" + url[len("postgresql+psycopg2"):]
    return url
