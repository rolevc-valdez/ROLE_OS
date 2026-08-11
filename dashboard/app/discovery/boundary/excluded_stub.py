"""Builds a lightweight `DiscoveredProject` stub for an excluded folder.

Deliberately does **not** call `detectors.analyze_folder` -- an excluded
folder must not be walked at all (§5: "not be rescanned recursively unless
explicitly configured"), so this only ever uses the name/path the scanner
already had from its own directory listing.
"""

from __future__ import annotations

from pathlib import Path

from app.discovery.identity import compute_item_id
from app.discovery.models import DiscoveredProject
from app.discovery.pipeline import PipelineStage


def build_excluded_project(
    path: Path, depth: int, parent_path: Path | None, reason: str
) -> DiscoveredProject:
    project = DiscoveredProject(
        root_path=str(path),
        name=path.name,
        depth=depth,
        parent_path=str(parent_path) if parent_path else None,
    )
    project.classification = "Non-project"
    project.move_risk = "low"
    project.move_risk_reasons = ["excluded folders are not scanned, so no move-risk signal exists"]
    project.maturity = "unknown"
    project.commercial_readiness = "not-commercial"
    project.recommendation = "Leave where it is"
    project.recommendation_reasons = [reason]

    project.item_id = compute_item_id(project.root_path)
    project.item_kind = "excluded"
    project.is_excluded = True
    project.exclusion_reason = reason
    project.boundary_confidence = 1.0
    project.boundary_evidence = [reason]

    # Bypasses the detect/classify/score/recommend pipeline entirely and by
    # design -- there is nothing to detect in a folder we never walk -- so
    # jump straight to the final stage rather than leaving it at NEW, which
    # would make it look like an unfinished/broken scan to any future
    # `require_stage` guard.
    project.stage = PipelineStage.RECOMMENDED
    return project
