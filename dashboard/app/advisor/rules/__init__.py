"""The eight independent Advisor rules.

Every rule module exposes a single function:

    def evaluate(project: dict, context: RuleContext) -> list[RecommendationCandidate]

Each rule is self-contained, deterministic, and only looks at the data it
needs — the engine (`app.advisor.engine`) is responsible for calling every
rule against every project and collecting whatever candidates come back.
A rule may return an empty list (nothing to recommend), or occasionally
more than one candidate if genuinely distinct issues are both present.
"""

from __future__ import annotations

from . import (
    blocked_dependency,
    capability_opportunity,
    critical_health,
    inactive_high_priority,
    missing_deliverables,
    near_completion,
    overdue_todos,
    stale_project,
)

ALL_RULES = (
    stale_project,
    near_completion,
    blocked_dependency,
    critical_health,
    overdue_todos,
    missing_deliverables,
    inactive_high_priority,
    capability_opportunity,
)

__all__ = ["ALL_RULES"]
