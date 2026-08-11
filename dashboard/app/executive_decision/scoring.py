"""Decision scoring: a fixed, additive, fully-documented point table --
never a hidden/learned weighting. Every contributor is a plain function
returning `(points, reason | None)`; `reason` is `None` only when that
contributor did not apply to this project (nothing to explain). The
score is the sum of contributor points, clamped to 0-100; every non-zero
contribution is named in `evidence`, so a decision is always traceable to
the exact facts that produced it -- the same discipline
`app.impact_analysis.scoring` and `app.project_ecosystem.graph` already
established for this codebase.
"""

from __future__ import annotations

from typing import Any

# Operational Intelligence's own top recommendation for this project is
# already a 0-100 priority computed by an existing engine -- scaled down
# (never renormalized/hidden) so it contributes at most this many points,
# leaving room for Executive Decision's own, additional evidence
# (commercial value, ecosystem position, health) to matter too.
_OI_PRIORITY_SCALE = 0.4  # priority 100 -> 40 points

_BUSINESS_VALUE_POINTS = {"critical": 25, "high": 20, "medium": 10, "low": 0}
_LAUNCH_READY_BONUS = 15  # Operational Intelligence's own "Consider shipping/launching" fired

_UNBLOCKS_POINTS_PER_PROJECT = 5
_UNBLOCKS_POINTS_CAP = 15  # 3 projects

_ALREADY_BLOCKING_BONUS = 10  # this project is itself stalling 1+ real dependents today

_IMPACT_RISK_POINTS = {"none": 0, "low": 2, "medium": 5, "high": 10, "critical": 15}

_PENDING_WORK_BONUS = 5

_RECENT_ACTIVITY_WITHIN_DAYS = 3
_RECENT_ACTIVITY_BONUS = 5
_STALE_ACTIVITY_AFTER_DAYS = 30
_STALE_ACTIVITY_PENALTY = -5

_HEALTH_SCORE_SCALE = 0.1  # health 100 -> 10 points

# A project the user explicitly parked should very rarely win over one
# that's still active -- not disqualified outright (an all-paused
# workspace must still produce a recommendation), just heavily discounted.
_PAUSED_STATUSES = ("paused", "on_hold", "archived")
_PAUSED_PENALTY = -20
_BLOCKED_STATUSES = ("blocked", "at_risk")
_BLOCKED_STATUS_PENALTY = -15

# Stale workspace data (Discovery hasn't rescanned recently) doesn't
# change *what* the evidence says, only how much to trust it -- so it
# discounts confidence, never the score itself.
_STALE_DATA_CONFIDENCE_PENALTY = 0.85


def _oi_priority_contribution(
    top_recommendation: dict[str, Any] | None,
) -> tuple[float, str | None]:
    if not top_recommendation:
        return 0.0, None
    priority = top_recommendation["priority"]
    points = priority * _OI_PRIORITY_SCALE
    return (
        points,
        f"Operational Intelligence priority {priority}/100 ({top_recommendation['recommendation']!r})",
    )


def _commercial_value_contribution(
    business_value: str | None, top_recommendation: dict[str, Any] | None
) -> tuple[float, str | None]:
    points = 0.0
    reasons: list[str] = []
    if business_value and _BUSINESS_VALUE_POINTS.get(business_value, 0):
        points += _BUSINESS_VALUE_POINTS[business_value]
        reasons.append(f"business_value = {business_value}")
    if top_recommendation and top_recommendation["recommendation"] == "Consider shipping/launching":
        points += _LAUNCH_READY_BONUS
        reasons.append(
            "Operational Intelligence: launch-ready (high health + commercial readiness)"
        )
    return points, "; ".join(reasons) if reasons else None


def _unblocks_contribution(dependent_names: list[str]) -> tuple[float, str | None]:
    if not dependent_names:
        return 0.0, None
    points = min(len(dependent_names) * _UNBLOCKS_POINTS_PER_PROJECT, _UNBLOCKS_POINTS_CAP)
    return points, f"Unblocks {len(dependent_names)} project(s): {', '.join(dependent_names)}"


def _already_blocking_contribution(blocked_names: list[str]) -> tuple[float, str | None]:
    if not blocked_names:
        return 0.0, None
    return (
        _ALREADY_BLOCKING_BONUS,
        f"Already blocking {len(blocked_names)} project(s) today: {', '.join(blocked_names)}",
    )


def _impact_risk_contribution(overall_risk: str) -> tuple[float, str | None]:
    points = _IMPACT_RISK_POINTS.get(overall_risk, 0)
    if points <= 0:
        return 0.0, None
    return points, f"Impact Analysis: {overall_risk} risk if this project changes today"


def _pending_work_contribution(pending_work: str) -> tuple[float, str | None]:
    if not pending_work:
        return 0.0, None
    return _PENDING_WORK_BONUS, "Project Memory: real pending work already recorded"


def _recent_activity_contribution(days_since_activity: float | None) -> tuple[float, str | None]:
    if days_since_activity is None:
        return 0.0, None
    if days_since_activity <= _RECENT_ACTIVITY_WITHIN_DAYS:
        return (
            _RECENT_ACTIVITY_BONUS,
            f"Active in the last {round(days_since_activity, 1)} day(s)",
        )
    if days_since_activity >= _STALE_ACTIVITY_AFTER_DAYS:
        return (
            _STALE_ACTIVITY_PENALTY,
            f"No activity in {round(days_since_activity)} day(s)",
        )
    return 0.0, None


def _health_contribution(health_score: int | None) -> tuple[float, str | None]:
    if health_score is None:
        return 0.0, None
    points = health_score * _HEALTH_SCORE_SCALE
    if points <= 0:
        return 0.0, None
    return points, f"Project health score {health_score}/100"


def _status_contribution(status: str | None) -> tuple[float, str | None]:
    status_lower = (status or "").lower()
    if status_lower in _PAUSED_STATUSES:
        return _PAUSED_PENALTY, f"Project status is '{status}'"
    if status_lower in _BLOCKED_STATUSES:
        return _BLOCKED_STATUS_PENALTY, f"Project status is '{status}'"
    return 0.0, None


def compute_decision_score(
    *,
    top_recommendation: dict[str, Any] | None,
    business_value: str | None,
    dependent_names: list[str],
    blocked_names: list[str],
    overall_risk: str,
    pending_work: str,
    days_since_activity: float | None,
    health_score: int | None,
    status: str | None,
    is_data_stale: bool,
) -> tuple[float, float, list[str]]:
    """Returns `(decision_score, confidence, evidence)`. Every non-zero
    contributor's reason is appended to `evidence` in the fixed order
    below, so the score is always reconstructable by re-reading this
    function top to bottom -- never a black box."""
    contributions = [
        _oi_priority_contribution(top_recommendation),
        _commercial_value_contribution(business_value, top_recommendation),
        _unblocks_contribution(dependent_names),
        _already_blocking_contribution(blocked_names),
        _impact_risk_contribution(overall_risk),
        _pending_work_contribution(pending_work),
        _recent_activity_contribution(days_since_activity),
        _health_contribution(health_score),
        _status_contribution(status),
    ]

    total = 0.0
    evidence: list[str] = []
    for points, reason in contributions:
        if reason is None:
            continue
        total += points
        evidence.append(reason)

    score = max(0.0, min(100.0, total))

    # Confidence: how much of the score rests on real recommendation/
    # ecosystem evidence (never invented) -- present when Operational
    # Intelligence produced a recommendation for this project, discounted
    # (never dropped) when the underlying Discovery data is stale.
    confidence = 0.85 if top_recommendation else 0.5
    if is_data_stale:
        confidence *= _STALE_DATA_CONFIDENCE_PENALTY
        evidence.append("data_freshness.is_stale = true -- confidence discounted accordingly")

    return score, confidence, evidence
