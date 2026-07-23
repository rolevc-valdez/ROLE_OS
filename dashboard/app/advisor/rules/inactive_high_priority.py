"""Flags a high/critical priority project that has gone quiet even briefly
— a much shorter fuse than the general `stale_project` rule, because
inactivity on something important is itself a risk worth surfacing early.
"""

from __future__ import annotations

from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.scoring import confidence_from_availability, days_since, priority_weight, staleness_score, weighted_combine

INACTIVE_STATUSES = {"completed", "archived", "done", "cancelled"}
HIGH_PRIORITIES = {"high", "critical"}
INACTIVITY_DAYS = 7

WEIGHTS = {"priority": 0.5, "staleness": 0.5}


def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]:
    priority = (project.get("priority") or "medium").lower()
    if priority not in HIGH_PRIORITIES:
        return []
    if (project.get("status") or "").lower() in INACTIVE_STATUSES:
        return []

    days = days_since(project.get("updated_at"), context.now)
    if days is None or days < INACTIVITY_DAYS:
        return []

    signals = {
        "priority": priority_weight(priority),
        "staleness": staleness_score(days, mild=INACTIVITY_DAYS, severe=INACTIVITY_DAYS * 4),
    }
    priority_score = weighted_combine(signals, WEIGHTS)
    confidence = confidence_from_availability([project.get("updated_at") is not None])

    evidence = [
        f"Priority: {priority}",
        f"No activity in {days:.0f} days (threshold for high-priority projects is {INACTIVITY_DAYS})",
    ]

    candidate = RecommendationCandidate(
        project_id=project["id"],
        workspace=project.get("workspace", ""),
        title=f"{project['name']} is high priority but has stalled",
        summary=f"{project['name']} is {priority} priority with no activity in {days:.0f} days.",
        recommendation_type="review_risk",
        priority_score=priority_score,
        confidence_score=confidence,
        reason=(
            f"This is a {priority}-priority project, and high-priority projects going quiet for "
            f"{days:.0f} days is a risk signal worth catching early."
        ),
        evidence=evidence,
        suggested_action="Check in on this project before the delay compounds.",
        estimated_effort="small",
        impact="Catching stalled high-priority work early avoids bigger delays later.",
        ttl_days=5,
    )
    return [candidate]
