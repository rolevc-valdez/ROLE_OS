"""Flags active projects that are close to done — a small, achievable push
finishes them off. Looks at deliverables and open todos together as one
"remaining work" measure.
"""

from __future__ import annotations

from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.scoring import (
    clamp,
    completion_ratio,
    confidence_from_availability,
    effort_from_count,
    priority_weight,
    weighted_combine,
)

INACTIVE_STATUSES = {"completed", "archived", "done", "cancelled"}
MIN_RATIO = 0.65
MAX_REMAINING = 4

WEIGHTS = {"completion": 0.6, "priority": 0.25, "impact": 0.15}


def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]:
    if (project.get("status") or "").lower() in INACTIVE_STATUSES:
        return []

    deliverables = project.get("deliverables") or []
    todos = project.get("todos") or []

    remaining_deliverables = [d for d in deliverables if (d.get("status") or "planned") != "delivered"]
    remaining_todos = [t for t in todos if (t.get("status") or "open") != "done"]
    remaining = len(remaining_deliverables) + len(remaining_todos)
    total = len(deliverables) + len(todos)

    ratio = completion_ratio(total - remaining, total)
    if ratio is None or ratio < MIN_RATIO or remaining == 0 or remaining > MAX_REMAINING:
        return []

    dependents = context.dependents or []
    signals = {
        "completion": clamp(ratio * 100),
        "priority": priority_weight(project.get("priority")),
        "impact": clamp(len(dependents) * 25),
    }
    priority_score = weighted_combine(signals, WEIGHTS)
    confidence = confidence_from_availability([total > 0, project.get("updated_at") is not None])

    evidence = [f"{total - remaining}/{total} tracked items complete"]
    if remaining_deliverables:
        evidence.append(f"{len(remaining_deliverables)} deliverable(s) remaining")
    if remaining_todos:
        evidence.append(f"{len(remaining_todos)} open to-do(s) remaining")
    if dependents:
        evidence.append(f"{len(dependents)} dependent project(s) waiting on this")

    impact = "Finishing this closes out the project."
    if dependents:
        names = ", ".join(d.get("dependent_project_name", "another project") for d in dependents[:3])
        impact = f"Completing it will unblock {names}."

    candidate = RecommendationCandidate(
        project_id=project["id"],
        workspace=project.get("workspace", ""),
        title=f"Finish {project['name']} — almost there",
        summary=f"{project['name']} is {round(ratio * 100)}% complete with only {remaining} item(s) left.",
        recommendation_type="continue_project",
        priority_score=priority_score,
        confidence_score=confidence,
        reason=(
            f"The project is {round(ratio * 100)}% complete and only has {remaining} remaining "
            f"deliverable(s)/to-do(s), so finishing it now is a small, high-leverage push."
        ),
        evidence=evidence,
        suggested_action=f"Finish the remaining {remaining} item(s) to close out the project.",
        estimated_effort=effort_from_count(remaining),
        impact=impact,
        ttl_days=7,
    )
    return [candidate]
