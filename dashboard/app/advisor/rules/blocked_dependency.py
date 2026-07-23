"""Flags a project that depends on another project which is itself
unhealthy or explicitly blocked/at-risk — the dependency, not this
project, is usually the real bottleneck.

Expects `context.dependencies` entries to be enriched by the engine with
`depends_on_health_score` and `depends_on_status` (looked up from the
dependency's own project record) — this rule doesn't fetch project data
itself, keeping it a pure function of its inputs.
"""

from __future__ import annotations

from app.advisor.models import RecommendationCandidate, RuleContext
from app.advisor.scoring import clamp, confidence_from_availability, priority_weight, weighted_combine

UNHEALTHY_THRESHOLD = 40
BLOCKING_STATUSES = {"blocked", "at_risk"}

WEIGHTS = {"priority": 0.4, "blocker_severity": 0.6}


def _is_blocking(dep: dict) -> bool:
    score = dep.get("depends_on_health_score")
    status = (dep.get("depends_on_status") or "").lower()
    return (score is not None and score < UNHEALTHY_THRESHOLD) or status in BLOCKING_STATUSES


def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]:
    blockers = [d for d in context.dependencies if _is_blocking(d)]
    if not blockers:
        return []

    worst_score = min((d.get("depends_on_health_score") for d in blockers if d.get("depends_on_health_score") is not None), default=UNHEALTHY_THRESHOLD)
    signals = {
        "priority": priority_weight(project.get("priority")),
        "blocker_severity": clamp(100 - worst_score),
    }
    priority_score = weighted_combine(signals, WEIGHTS)
    confidence = confidence_from_availability(
        [d.get("depends_on_health_score") is not None for d in blockers]
    )

    evidence = [
        f"Depends on {d.get('depends_on_project_name', 'a project')} "
        f"(health {d.get('depends_on_health_score', 'unknown')}, status {d.get('depends_on_status', 'unknown')})"
        for d in blockers
    ]

    names = ", ".join(d.get("depends_on_project_name", "a dependency") for d in blockers[:3])
    candidate = RecommendationCandidate(
        project_id=project["id"],
        workspace=project.get("workspace", ""),
        title=f"{project['name']} is blocked by {names}",
        summary=f"{project['name']} depends on {len(blockers)} project(s) that are unhealthy or at risk.",
        recommendation_type="unblock_dependency",
        priority_score=priority_score,
        confidence_score=confidence,
        reason=f"{len(blockers)} of this project's dependencies are unhealthy or explicitly blocked/at-risk.",
        evidence=evidence,
        suggested_action=f"Prioritize unblocking {names} to unblock {project['name']}.",
        estimated_effort="medium",
        impact=f"Unblocking {names} lets {project['name']} move forward again.",
        ttl_days=5,
    )
    return [candidate]
