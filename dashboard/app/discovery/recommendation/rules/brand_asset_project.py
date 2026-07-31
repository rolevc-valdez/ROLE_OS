"""Brand / Asset Project classification -- a creative-asset collection,
not a codebase. Only reached when `high_move_risk` (priority 90) didn't
already fire."""

from __future__ import annotations

from app.discovery.models import DiscoveredProject
from app.discovery.recommendation.models import RecommendationCandidate

PRIORITY = 80


def evaluate(project: DiscoveredProject) -> RecommendationCandidate | None:
    if project.classification != "Brand / Asset Project":
        return None

    if project.maturity == "stale":
        return RecommendationCandidate(
            action="Archive",
            reasons=["stale asset collection with no code or docs signal"],
            priority=PRIORITY,
        )

    return RecommendationCandidate(
        action="Leave where it is",
        reasons=["asset collection, not a codebase -- keep with other creative assets"],
        priority=PRIORITY,
    )
