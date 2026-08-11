"""Bounded, deterministic sequencing for the recommended project -- not a
scheduling engine and not a calendar integration. Every Today Plan has
exactly one step (the one project the engine already chose); "09:00" is
a fixed anchor label, not a real-clock computation, matching the brief's
own worked example. Effort/duration are read from the same static,
auditable keyword-lookup convention `app.operational_intelligence.models.
expected_benefit_for` already established -- never an invented per-project
estimate.
"""

from __future__ import annotations

from typing import Any

from app.executive_decision.models import make_today_plan_step

_TODAY_PLAN_START_TIME = "09:00"
_NEXT_CHECKPOINT = "Create Snapshot"

# (effort, duration) keyed by a keyword found in the recommended action's
# own title/suggested_action text -- first match wins, case-insensitive.
# Same discipline as `_EXPECTED_BENEFIT_BY_KEYWORD`: a fixed, documented
# lookup table, never a generated estimate.
_EFFORT_DURATION_BY_KEYWORD: tuple[tuple[str, str, str], ...] = (
    ("commit or stash", "Low", "15 minutes"),
    ("rescan", "Low", "5 minutes"),
    ("import", "Low", "10 minutes"),
    ("readme", "Low", "30 minutes"),
    ("roadmap", "Low", "30 minutes"),
    ("todo", "Low", "30 minutes"),
    ("snapshot", "Low", "10 minutes"),
    ("shipping", "High", "2-4 hours"),
    ("unblock", "Medium", "1-2 hours"),
    ("deliverable", "Medium", "1-2 hours"),
    ("continue", "Medium", "1-2 hours"),
    ("decision", "Medium", "30-60 minutes"),
    ("review", "Low", "30 minutes"),
)
_DEFAULT_EFFORT = "Medium"
_DEFAULT_DURATION = "1-2 hours"


def estimate_effort_and_duration(action_title: str) -> tuple[str, str]:
    title_lower = (action_title or "").lower()
    for keyword, effort, duration in _EFFORT_DURATION_BY_KEYWORD:
        if keyword in title_lower:
            return effort, duration
    return _DEFAULT_EFFORT, _DEFAULT_DURATION


def dependencies_status(unsatisfied_dependency_names: list[str]) -> str:
    if not unsatisfied_dependency_names:
        return "Satisfied"
    return f"Blocked on: {', '.join(unsatisfied_dependency_names)}"


def build_today_plan(
    *,
    project: dict[str, Any] | None,
    action_title: str,
    objective: str,
    expected_duration: str,
    expected_result: str,
    dependency_status: str,
) -> list[dict[str, Any]]:
    """Exactly one step: the project Executive Decision already chose.
    A future sprint's candidate for a *second* step (e.g. "then review
    Needs Attention") is deliberately out of scope -- the brief asks for
    one deterministic recommendation, not a multi-item day plan."""
    if project is None:
        return []
    return [
        make_today_plan_step(
            start_time=_TODAY_PLAN_START_TIME,
            action=action_title,
            project=project,
            objective=objective,
            expected_duration=expected_duration,
            expected_result=expected_result,
            dependencies_status=dependency_status,
            next_checkpoint=_NEXT_CHECKPOINT,
        )
    ]
