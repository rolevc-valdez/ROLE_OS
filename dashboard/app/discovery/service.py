"""Orchestrates a Discovery Engine audit run.

`run_audit` is the single entry point Sprint 1 exposes: scan -> detect ->
classify -> ScanResult. It never opens a database connection and never
writes inside the scanned tree — the only writes it can perform are the
optional report files, written to `output_dir`, which must not be inside
the scanned root (enforced in the CLI) to keep the audit's own output from
polluting a future rescan.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from app.discovery.boundary import assign_boundaries, build_excluded_project
from app.discovery.classifier import classify
from app.discovery.detectors import analyze_folder
from app.discovery.git_reader import read_git_info
from app.discovery.models import ScanResult
from app.discovery.recommendation import apply_container_child_overrides
from app.discovery.scanner import discover_candidates


def run_audit(
    root: Path, max_depth: int = 2, extra_exclusions: list[str] | None = None
) -> ScanResult:
    root = Path(root)
    started = time.monotonic()

    candidates, skipped = discover_candidates(root, max_depth=max_depth, extra_exclusions=extra_exclusions)

    projects = []
    errors: list[str] = []
    for candidate in candidates:
        if candidate.excluded:
            projects.append(
                build_excluded_project(
                    candidate.path, candidate.depth, candidate.parent_path, candidate.exclusion_reason or "excluded"
                )
            )
            continue
        try:
            project = analyze_folder(candidate.path)
        except OSError as exc:
            errors.append(f"failed to analyze {candidate.path}: {exc}")
            continue
        project.depth = candidate.depth
        project.parent_path = str(candidate.parent_path) if candidate.parent_path else None
        project.git = read_git_info(candidate.path)
        classify(project)
        projects.append(project)

    apply_container_child_overrides(projects)
    assign_boundaries(projects)

    duration = time.monotonic() - started
    return ScanResult(
        root=str(root),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=round(duration, 3),
        projects=projects,
        skipped_paths=skipped,
        errors=errors,
        max_depth=max_depth,
    )
