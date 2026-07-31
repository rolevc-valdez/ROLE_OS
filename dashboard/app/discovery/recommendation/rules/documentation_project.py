"""Documentation Project classification -- always routes to manual review:
a docs-only folder needs a human to confirm which real project it belongs
to, something no signal here can determine automatically."""

from __future__ import annotations

from app.discovery.models import DiscoveredProject
from app.discovery.recommendation.models import RecommendationCandidate

PRIORITY = 70


def evaluate(project: DiscoveredProject) -> RecommendationCandidate | None:
    if project.classification != "Documentation Project":
        return None

    return RecommendationCandidate(
        action="Requires manual review",
        reasons=["documentation-only folder -- confirm it belongs with the project it documents"],
        priority=PRIORITY,
    )
