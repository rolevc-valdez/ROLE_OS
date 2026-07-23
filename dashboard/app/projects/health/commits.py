"""Recent-commits signal (optional, forward-looking).

ROLE OS has no git integration yet, so this signal has no data source in
practice today — callers pass `commit_dates=None`, and this function
returns `None`, which tells `compute_health_score()` to exclude it from
scoring entirely (rather than penalizing every project for a feature that
doesn't exist yet). The scoring logic itself is implemented now so that
wiring up a real git integration later is a one-line change: pass real
commit dates in and this signal activates automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone


def score_recent_commits(commit_dates: list[str] | None, now: datetime | None = None) -> int | None:
    """Score 0-100 from the most recent commit date, or None if unavailable."""
    if commit_dates is None:
        return None
    if not commit_dates:
        return 30

    now = now or datetime.now(timezone.utc)
    parsed = []
    for value in commit_dates:
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
    if days <= 1:
        return 100
    if days <= 7:
        return 80
    if days <= 30:
        return 55
    return 25
