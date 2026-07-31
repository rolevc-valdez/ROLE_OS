"""Lowest-precedence rule: always fires (never returns None), so the
engine always has at least one candidate. Catches classifications that
don't match any other rule (today, just `Unknown`)."""

from __future__ import annotations

from app.discovery.models import DiscoveredProject
from app.discovery.recommendation.models import RecommendationCandidate

PRIORITY = 0


def evaluate(project: DiscoveredProject) -> RecommendationCandidate:
    return RecommendationCandidate(
        action="Requires manual review",
        reasons=[f"unclassified signal mix (classification={project.classification})"],
        priority=PRIORITY,
    )
