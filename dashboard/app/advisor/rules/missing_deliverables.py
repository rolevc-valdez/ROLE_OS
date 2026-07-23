"""Flags an active project with tracked deliverables that haven't been
delivered yet — a more general signal than `near_completion` (which only
fires when the project is *almost entirely* done); this fires whenever
there's meaningful undelivered work, regardless of overall completion
ratio.
"""

from __future__ import annotations

from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.scoring import clamp, confidence_from_availability, effort_from_count, priority_weight, weighted_combine

INACTIVE_STATUSES = {"completed", "archived", "done", "cancelled"}
MAX_MISSING = 6

WEIGHTS = {"priority": 0.45, "deliverable_pressure": 0.55}


def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]:
    if (project.get("status") or "").lower() in INACTIVE_STATUSES:
        return []

    deliverables = project.get("deliverables") or []
    if not deliverables:
        return []

    missing = [d for d in deliverables if (d.get("status") or "planned") != "delivered"]
    if not missing or len(missing) > MAX_MISSING:
        return []

    signals = {
        "priority": priority_weight(project.get("priority")),
        "deliverable_pressure": clamp(len(missing) * 15),
    }
    priority_score = weighted_combine(signals, WEIGHTS)
    confidence = confidence_from_availability([True])

    evidence = [f"{len(missing)}/{len(deliverables)} deliverables not yet delivered"]
    evidence.extend(f"“{d['text']}”" for d in missing[:3] if d.get("text"))

    candidate = RecommendationCandidate(
        project_id=project["id"],
        workspace=project.get("workspace", ""),
        title=f"{len(missing)} deliverable(s) pending on {project['name']}",
        summary=f"{project['name']} has {len(missing)} of {len(deliverables)} deliverables still pending.",
        recommendation_type="finish_deliverable",
        priority_score=priority_score,
        confidence_score=confidence,
        reason=f"{len(missing)} tracked deliverable(s) have not been marked delivered yet.",
        evidence=evidence,
        suggested_action=f"Deliver the remaining {len(missing)} deliverable(s).",
        estimated_effort=effort_from_count(len(missing)),
        impact="Delivering these closes out tracked commitments for this project.",
        ttl_days=7,
    )
    return [candidate]
