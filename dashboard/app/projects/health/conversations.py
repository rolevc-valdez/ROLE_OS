"""Recent-conversations signal: is this project still being actively discussed?"""

from __future__ import annotations

from datetime import datetime, timezone


def score_recent_conversations(dates: list[str], now: datetime | None = None) -> int:
    """Score 0-100 from the most recent linked-conversation date.

    An empty list (no conversations linked yet) gets a neutral-low score:
    it's not necessarily unhealthy, just unproven.
    """
    if not dates:
        return 30

    now = now or datetime.now(timezone.utc)
    parsed = []
    for value in dates:
        try:
            dt = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        parsed.append(dt)

    if not parsed:
        return 30

    days = (now - max(parsed)).total_seconds() / 86400
    if days <= 7:
        return 100
    if days <= 30:
        return 75
    if days <= 90:
        return 45
    return 20
