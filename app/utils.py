"""Small shared helpers."""
from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC timestamp (kept naive for consistent SQLite comparisons)."""
    return datetime.now(UTC).replace(tzinfo=None)
