"""Pipeline-stage safety for `DiscoveredProject` (Sprint 1.5, Refactor 3).

Detection, classification, health scoring, and recommendation are four
sequential stages that each depend on the previous one having already run
(`compute_health` reads `commercial_readiness`/`maturity`/`move_risk`,
which only exist after classification; `recommend` reads `health_score`,
which only exists after health scoring). Before this module, that
dependency was purely implicit in call order inside `classifier.classify`
— nothing stopped a second entry point from calling `compute_health()` on
a project that had never been classified, and nothing would have failed
loudly if it had: `commercial_readiness` defaults to `"unknown"`, which
`health.score_commercial_readiness` silently maps to a plausible-looking
20 instead of raising.

This is deliberately the smallest safeguard that fixes that, not a model
rewrite: one `IntEnum` stamped onto `DiscoveredProject.stage` as each stage
completes, and a `require_stage()` guard called at the top of the two
functions that have real prerequisites. Nothing about `DiscoveredProject`'s
shape, or any detector's/classifier's return type, changes.
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.discovery.models import DiscoveredProject


class PipelineStage(IntEnum):
    """Ordered stages a `DiscoveredProject` passes through. Comparable
    (`IntEnum`) so `require_stage` can check "at least this far along"
    rather than "exactly this stage"."""

    NEW = 0  # freshly constructed, no detector has run yet
    DETECTED = 1  # detectors.analyze_folder has populated raw signals
    CLASSIFIED = 2  # classifier.classify_* has set kind/move_risk/maturity/commercial_readiness
    SCORED = 3  # health.compute_health has set health_score/health_breakdown
    RECOMMENDED = 4  # recommendation engine has set recommendation/recommendation_reasons


class PipelineStageError(RuntimeError):
    """Raised when a stage-dependent function is called before its
    prerequisite stage has completed for that project."""


def require_stage(project: "DiscoveredProject", minimum: PipelineStage, caller: str) -> None:
    """Guard for stage-dependent public functions.

    Raises `PipelineStageError` (rather than silently scoring against
    incomplete/default data) if `project.stage` hasn't reached `minimum`
    yet.
    """
    if project.stage < minimum:
        raise PipelineStageError(
            f"{caller} requires '{project.name}' to have reached pipeline "
            f"stage {minimum.name}, but it is only at {project.stage.name}. "
            f"Run the prerequisite stage (see app.discovery.pipeline.PipelineStage) "
            "before calling this function."
        )
