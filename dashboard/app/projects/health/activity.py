"""Recent-activity signal: how recently was the project itself updated?"""

from __future__ import annotations

from datetime import datetime, timezone


def _days_since(iso_value: str, now: datetime) -> float | None:
    try:
        dt = datetime.fromisoformat(iso_value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 86400


def score_recent_activity(updated_at: str | None, now: datetime | None = None) -> int:
    """Score 0-100: higher means the project was updated more recently."""
    if not updated_at:
        return 0
    now = now or datetime.now(timezone.utc)
    days = _days_since(updated_at, now)
    if days is None:
        return 0
    if days <= 1:
        return 100
    if days <= 7:
        return 85
    if days <= 30:
        return 65
    if days <= 90:
        return 35
    if days <= 180:
        return 15
    return 5
