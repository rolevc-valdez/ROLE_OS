"""Read-only signal extraction for one candidate folder (Sprint 1.5:
detector registry architecture -- see `docs/product/DECISIONS.md`).

`analyze_folder()` is the single public entry point (unchanged signature
from Sprint 1): it builds one shared `FolderInventory` (the only
filesystem walk -- see `inventory.py`), then runs every independent
detector in `registry.DETECTOR_REGISTRY` over that same inventory and
merges their findings into a `DiscoveredProject`. No detector re-walks the
filesystem, no detector can silently clobber another's fields (see
`registry.run_all`'s collision guard), and every detector is testable on
its own with a hand-built `FolderInventory` -- no real filesystem needed.

`IGNORE_DIR_NAMES`, `TOP_LEVEL_MARKER_FILES`, `has_own_strong_markers`, and
`is_candidate_signal` are re-exported here unchanged for
`scanner.py`/callers that imported them from the old flat `detectors.py`
module -- this package replaces that module, not its public API.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.discovery.detectors.constants import IGNORE_DIR_NAMES, TOP_LEVEL_MARKER_FILES
from app.discovery.detectors.documentation import README_RE
from app.discovery.detectors.inventory import build_inventory
from app.discovery.detectors.registry import DETECTOR_REGISTRY, run_all
from app.discovery.models import DiscoveredProject
from app.discovery.pipeline import PipelineStage

__all__ = [
    "IGNORE_DIR_NAMES",
    "TOP_LEVEL_MARKER_FILES",
    "has_own_strong_markers",
    "is_candidate_signal",
    "analyze_folder",
    "DETECTOR_REGISTRY",
]


def has_own_strong_markers(path: Path) -> bool:
    """True if `path` itself looks like a self-contained project root.

    Used by the scanner to decide whether to also look one level deeper
    (a container/monorepo folder) or stop here.
    """
    try:
        if (path / ".git").exists():
            return True
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file() and entry.name in TOP_LEVEL_MARKER_FILES:
                    return True
    except OSError:
        return False
    return False


def is_candidate_signal(path: Path) -> bool:
    """Minimal-signal check used to admit a *nested* (depth-2+) folder."""
    try:
        if (path / ".git").exists():
            return True
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    if entry.name in TOP_LEVEL_MARKER_FILES:
                        return True
                    if README_RE.match(entry.name):
                        return True
    except OSError:
        return False
    return False


def analyze_folder(root: Path) -> DiscoveredProject:
    """Walk `root` once (read-only) and populate a DiscoveredProject by
    running every registered detector over the resulting inventory."""
    inventory = build_inventory(root)

    project = DiscoveredProject(root_path=str(root), name=root.name, depth=0)

    for field_name, value in run_all(inventory).items():
        setattr(project, field_name, value)

    project.total_files = inventory.total_files
    project.total_dirs = inventory.total_dirs
    project.last_modified = inventory.last_modified
    project.truncated = inventory.truncated
    project.reparse_points_skipped = inventory.reparse_points_skipped
    project.scan_errors = inventory.scan_errors

    project.stage = PipelineStage.DETECTED
    return project
