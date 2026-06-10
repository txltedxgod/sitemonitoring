"""Small shared helpers."""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp (kept naive for consistent SQLite comparisons)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
