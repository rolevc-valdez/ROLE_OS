"""Flags a project whose overall Health Score has dropped into critical
territory. Looks at *which* signal from the Health Score breakdown
(`app.projects.health`) is weakest to decide whether the sharpest, most
actionable framing is "review the pending decisions" (when unresolved
decisions are the dominant drag) or a more general "review project risk".
"""

from __future__ import annotations

from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.scoring import clamp, confidence_from_availability, priority_weight, weighted_combine

CRITICAL_THRESHOLD = 40

SIGNAL_LABELS = {
    "recent_activity": "recent activity",
    "open_todos": "open to-dos",
    "unresolved_decisions": "unresolved decisions",
    "missing_deliverables": "missing deliverables",
    "recent_conversations": "recent conversations",
    "recent_commits": "recent commits",
}

WEIGHTS = {"priority": 0.3, "risk": 0.7}


def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]:
    health = context.health
    if not health or health.get("score", 100) >= CRITICAL_THRESHOLD:
        return []

    breakdown = health.get("breakdown") or {}
    if not breakdown:
        return []

    weakest_key, weakest_value = min(breakdown.items(), key=lambda kv: kv[1])

    signals = {
        "priority": priority_weight(project.get("priority")),
        "risk": clamp(100 - health["score"]),
    }
    priority_score = weighted_combine(signals, WEIGHTS)
    confidence = confidence_from_availability([True] * len(breakdown))

    evidence = [f"Health score: {health['score']}/100"] + [
        f"{SIGNAL_LABELS.get(k, k)}: {v}/100" for k, v in sorted(breakdown.items(), key=lambda kv: kv[1])
    ]

    if weakest_key == "unresolved_decisions":
        decisions = project.get("decisions") or []
        pending = [d for d in decisions if (d.get("status") or "resolved") == "pending"]
        candidate = RecommendationCandidate(
            project_id=project["id"],
            workspace=project.get("workspace", ""),
            title=f"Review pending decisions on {project['name']}",
            summary=f"{project['name']}'s health is being dragged down by unresolved decisions.",
            recommendation_type="review_decision",
            priority_score=priority_score,
            confidence_score=confidence,
            reason=(
                f"Health score is {health['score']}/100, and unresolved decisions is the weakest "
                f"contributing signal ({weakest_value}/100)."
            ),
            evidence=evidence,
            suggested_action=f"Resolve the {len(pending) or 'pending'} open decision(s) on this project.",
            estimated_effort="medium",
            impact="Resolving these decisions removes the single biggest drag on the project's health score.",
            ttl_days=5,
        )
    else:
        candidate = RecommendationCandidate(
            project_id=project["id"],
            workspace=project.get("workspace", ""),
            title=f"{project['name']} is at risk",
            summary=f"{project['name']}'s health score has dropped to {health['score']}/100.",
            recommendation_type="review_risk",
            priority_score=priority_score,
            confidence_score=confidence,
            reason=(
                f"Health score is {health['score']}/100 (critical threshold is {CRITICAL_THRESHOLD}); "
                f"the weakest signal is {SIGNAL_LABELS.get(weakest_key, weakest_key)} ({weakest_value}/100)."
            ),
            evidence=evidence,
            suggested_action=f"Investigate and address {SIGNAL_LABELS.get(weakest_key, weakest_key)}.",
            estimated_effort="medium",
            impact="Addressing the weakest signal is the fastest way to bring this project back to healthy.",
            ttl_days=5,
        )
    return [candidate]
