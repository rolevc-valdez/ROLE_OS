"""Highest-precedence rule: anything classified Non-project is never a
candidate for any other action, regardless of move risk or anything else
-- the Discovery Engine has nothing to recommend consolidating."""

from __future__ import annotations

from app.discovery.models import DiscoveredProject
from app.discovery.recommendation.models import RecommendationCandidate

PRIORITY = 100


def evaluate(project: DiscoveredProject) -> RecommendationCandidate | None:
    if project.classification != "Non-project":
        return None

    if project.total_files == 0 or (project.maturity == "stale" and project.total_files < 5):
        return RecommendationCandidate(
            action="Archive",
            reasons=[
                f"classified Non-project, stale, and only {project.total_files} file(s) "
                "-- looks like an empty or abandoned folder"
            ],
            priority=PRIORITY,
        )

    return RecommendationCandidate(
        action="Leave where it is",
        reasons=["classified Non-project -- not something the Discovery Engine should manage"],
        priority=PRIORITY,
    )
