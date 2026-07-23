"""Flags any non-completed project that has gone quiet for a long time,
regardless of priority — the general staleness catch-all.

(`inactive_high_priority.py` covers the more urgent, shorter-fuse version
of this same idea specifically for high/critical priority projects.)
"""

from __future__ import annotations

from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.scoring import (
    clamp,
    confidence_from_availability,
    days_since,
    priority_weight,
    staleness_score,
    weighted_combine,
)

STALE_DAYS = 30
INACTIVE_STATUSES = {"completed", "archived", "done", "cancelled"}

WEIGHTS = {"priority": 0.35, "staleness": 0.65}


def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]:
    if (project.get("status") or "").lower() in INACTIVE_STATUSES:
        return []

    days = days_since(project.get("updated_at"), context.now)
    if days is None or days < STALE_DAYS:
        return []

    signals = {
        "priority": priority_weight(project.get("priority")),
        "staleness": staleness_score(days, mild=STALE_DAYS, severe=STALE_DAYS * 3),
    }
    priority_score = weighted_combine(signals, WEIGHTS)
    confidence = confidence_from_availability([project.get("updated_at") is not None])

    evidence = [
        f"No activity in {days:.0f} days",
        f"Status: {project.get('status', 'unknown')}",
        f"Priority: {project.get('priority', 'medium')}",
    ]

    candidate = RecommendationCandidate(
        project_id=project["id"],
        workspace=project.get("workspace", ""),
        title=f"Revisit {project['name']} — it's gone quiet",
        summary=f"{project['name']} has had no activity in {days:.0f} days.",
        recommendation_type="update_stale_project",
        priority_score=priority_score,
        confidence_score=confidence,
        reason=(
            f"The project has been inactive for {days:.0f} days while still marked "
            f"'{project.get('status', 'active')}'."
        ),
        evidence=evidence,
        suggested_action="Review the project and either update it, reprioritize it, or close it out.",
        estimated_effort="small",
        impact="Keeps the project's status honest and prevents it from silently rotting.",
        ttl_days=14,
    )
    return [candidate]
