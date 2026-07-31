"""Software Project / Website / Mixed Project classification -- the "is
this a real, healthy-enough, low-enough-risk project?" rule. Only reached
when `high_move_risk` (priority 90) didn't already fire."""

from __future__ import annotations

from app.discovery.models import DiscoveredProject
from app.discovery.recommendation.models import RecommendationCandidate

PRIORITY = 60

REAL_PROJECT_KINDS = {"Software Project", "Website", "Mixed Project"}
HEALTH_SCORE_THRESHOLD = 50


def evaluate(project: DiscoveredProject) -> RecommendationCandidate | None:
    if project.classification not in REAL_PROJECT_KINDS:
        return None

    if project.maturity == "stale":
        return RecommendationCandidate(
            action="Archive",
            reasons=[f"real project but stale (classification={project.classification})"],
            priority=PRIORITY,
        )

    score = project.health_score if project.health_score is not None else 0
    if project.move_risk in {"low", "medium"} and score >= HEALTH_SCORE_THRESHOLD:
        return RecommendationCandidate(
            action="Move into IA PROJECTS",
            reasons=[
                f"{project.classification.lower()} with health score {score} and "
                f"{project.move_risk} move risk -- safe to consolidate into IA PROJECTS"
            ],
            priority=PRIORITY,
        )

    return RecommendationCandidate(
        action="Requires manual review",
        reasons=[
            f"{project.classification.lower()} but health score {score} is below the "
            "confidence threshold for an automatic move"
        ],
        priority=PRIORITY,
    )
