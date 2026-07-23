"""Shared, deterministic scoring toolkit used by every Advisor rule.

No randomness anywhere: every score is a pure function of real project
data (priority, health, staleness, dependents, etc.). Missing/unavailable
signals are handled the same way as the Health Score engine
(`app.projects.health`) — a signal that has no data is simply left out of
the weighted average, and the remaining weights are renormalized, rather
than being counted as zero (which would unfairly tank the score) or
skipped silently (which would hide why a number looks the way it does —
every rule still reports which signals it used in its `evidence`).
"""

from __future__ import annotations

from datetime import datetime, timezone

PRIORITY_WEIGHTS = {"low": 25, "medium": 50, "high": 75, "critical": 100}


def priority_weight(priority: str | None) -> int:
    return PRIORITY_WEIGHTS.get((priority or "medium").lower(), 50)


def days_since(iso_value: str | None, now: datetime | None = None) -> float | None:
    """Days between `iso_value` and `now` (or the real current time). None if unparseable."""
    if not iso_value:
        return None
    try:
        dt = datetime.fromisoformat(iso_value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 86400


def clamp(value: float, low: float = 0, high: float = 100) -> int:
    return round(max(low, min(high, value)))


def weighted_combine(signals: dict[str, float], weights: dict[str, float]) -> int:
    """Combine 0-100 signals into one 0-100 score, renormalizing over the
    signals actually present (mirrors `app.projects.health`'s combiner)."""
    if not signals:
        return 0
    active_weights = {k: weights[k] for k in signals if k in weights}
    total_weight = sum(active_weights.values()) or 1.0
    weighted_sum = sum(signals[k] * active_weights.get(k, 0) for k in signals)
    return clamp(weighted_sum / total_weight)


def confidence_from_availability(available_flags: list[bool], floor: int = 40) -> int:
    """Confidence score from how many expected data points were actually available.

    A rule with plenty of missing inputs still produces a recommendation
    (better to surface a lower-confidence signal than none at all), but its
    confidence score reflects that thinner evidence base. `floor` keeps the
    score from collapsing to 0 even when almost nothing was available,
    since the rule firing at all means at least one condition was met.
    """
    if not available_flags:
        return floor
    ratio = sum(1 for f in available_flags if f) / len(available_flags)
    return clamp(floor + ratio * (100 - floor))


def staleness_score(days: float | None, *, mild: float = 7, severe: float = 30) -> int:
    """0-100, higher = staler. `mild`/`severe` are day thresholds for this rule's context."""
    if days is None:
        return 0
    if days <= mild:
        return 0
    if days >= severe:
        return 100
    return clamp((days - mild) / (severe - mild) * 100)


def completion_ratio(done: int, total: int) -> float | None:
    """Fraction complete, or None if there's nothing tracked to divide by."""
    if total <= 0:
        return None
    return done / total


def effort_from_count(count: int, *, small: int = 2, medium: int = 5) -> str:
    """Rough, deterministic effort estimate from an item count (todos, deliverables, ...)."""
    if count <= small:
        return "small"
    if count <= medium:
        return "medium"
    return "large"
