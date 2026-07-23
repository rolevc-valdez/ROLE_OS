"""Flags a project with several open to-dos that have been sitting for a
long time without resolution."""

from __future__ import annotations

from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.scoring import (
    clamp,
    confidence_from_availability,
    days_since,
    effort_from_count,
    priority_weight,
    weighted_combine,
)

OVERDUE_DAYS = 14
MIN_OVERDUE_COUNT = 2

WEIGHTS = {"priority": 0.3, "todo_pressure": 0.7}


def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]:
    todos = project.get("todos") or []
    open_todos = [t for t in todos if (t.get("status") or "open") != "done"]
    overdue = [t for t in open_todos if (days_since(t.get("created_at"), context.now) or 0) >= OVERDUE_DAYS]

    if len(overdue) < MIN_OVERDUE_COUNT:
        return []

    signals = {
        "priority": priority_weight(project.get("priority")),
        "todo_pressure": clamp(len(overdue) * 20),
    }
    priority_score = weighted_combine(signals, WEIGHTS)
    confidence = confidence_from_availability([t.get("created_at") is not None for t in overdue])

    oldest_days = max((days_since(t.get("created_at"), context.now) or 0) for t in overdue)
    evidence = [f"{len(overdue)} open to-do(s) older than {OVERDUE_DAYS} days"]
    evidence.extend(f"“{t['text']}”" for t in overdue[:3] if t.get("text"))

    candidate = RecommendationCandidate(
        project_id=project["id"],
        workspace=project.get("workspace", ""),
        title=f"Resolve {len(overdue)} overdue to-dos on {project['name']}",
        summary=f"{project['name']} has {len(overdue)} to-do(s) open for {oldest_days:.0f}+ days.",
        recommendation_type="resolve_todo",
        priority_score=priority_score,
        confidence_score=confidence,
        reason=f"{len(overdue)} to-do(s) have been open for at least {OVERDUE_DAYS} days with no resolution.",
        evidence=evidence,
        suggested_action=f"Resolve or reprioritize the {len(overdue)} overdue to-do(s).",
        estimated_effort=effort_from_count(len(overdue)),
        impact="Clearing overdue to-dos prevents them from silently blocking progress.",
        ttl_days=7,
    )
    return [candidate]
