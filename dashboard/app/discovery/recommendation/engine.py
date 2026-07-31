"""The recommendation engine: runs every rule in `rules.RULES`, keeps the
ones that fired, and returns the highest-priority candidate. See
`rules/__init__.py` for the full, documented precedence table.
"""

from __future__ import annotations

from app.discovery.models import DiscoveredProject
from app.discovery.pipeline import PipelineStage, require_stage
from app.discovery.recommendation.rules import RULES

VALID_ACTIONS = (
    "Leave where it is",
    "Move into IA PROJECTS",
    "Archive",
    "Merge with another project",
    "Rename",
    "Requires manual review",
)


def recommend(project: DiscoveredProject) -> tuple[str, list[str]]:
    """Returns (action, reasons). Requires `project` to have already
    reached `PipelineStage.SCORED` (classified *and* health-scored) --
    `real_project`'s rule reads `health_score`, so calling this any earlier
    would silently score against a `None`/default value instead of failing
    loudly.
    """
    require_stage(project, PipelineStage.SCORED, "recommendation.recommend")

    candidates = [rule.evaluate(project) for rule in RULES]
    fired = [c for c in candidates if c is not None]
    # `max` returns the first max-priority element it encounters, which
    # combined with `RULES`' list order gives a deterministic tie-break --
    # ties aren't expected in practice (see rules/__init__.py), but this
    # keeps the result reproducible if one ever occurs.
    winner = max(fired, key=lambda c: c.priority)

    project.stage = PipelineStage.RECOMMENDED
    return winner.action, list(winner.reasons)
