"""Second-highest precedence: high move risk overrides every classification
-specific rule below it (Brand/Asset, Documentation, real-project) -- safety
of relocation trumps what kind of folder this is. It does not override
`non_project` (priority 100): a Non-project folder's move risk is
irrelevant, since nothing is being moved either way."""

from __future__ import annotations

from app.discovery.models import DiscoveredProject
from app.discovery.recommendation.models import RecommendationCandidate

PRIORITY = 90


def evaluate(project: DiscoveredProject) -> RecommendationCandidate | None:
    if project.classification == "Non-project" or project.move_risk != "high":
        return None

    return RecommendationCandidate(
        action="Requires manual review",
        reasons=[
            f"move risk is high ({'; '.join(project.move_risk_reasons)}) -- "
            "fix hardcoded paths/config before relocating"
        ],
        priority=PRIORITY,
    )
