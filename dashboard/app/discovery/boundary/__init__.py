"""Project-boundary / hierarchy model (Discovery Engine Sprint 3).

Distinguishes a real top-level project from a nested repository, a
component, an internal structure folder, a documentation/asset folder, an
excluded folder, and a non-project -- so the Workspace page can present
real project structure instead of a flat directory listing. See
`docs/architecture/11_PROJECT_BOUNDARY_SPRINT3_REPORT.md` for the full
algorithm and rationale.

Deliberately separate from `classifier.classification` (Software Project/
Website/...): that field answers "what kind of thing is this", this
package answers "where does this sit in the real project tree".
"""

from __future__ import annotations

from app.discovery.boundary.excluded_stub import build_excluded_project
from app.discovery.boundary.exclusions import is_excluded, load_exclusion_config
from app.discovery.boundary.hierarchy import assign_boundaries
from app.discovery.boundary.rules import (
    INTERNAL_FOLDER_NAMES,
    matches_internal_folder_name,
)

ITEM_KINDS = (
    "project",
    "repository",
    "component",
    "documentation",
    "asset_library",
    "internal_folder",
    "excluded",
    "non_project",
    "unknown",
)

__all__ = [
    "INTERNAL_FOLDER_NAMES",
    "ITEM_KINDS",
    "assign_boundaries",
    "build_excluded_project",
    "is_excluded",
    "load_exclusion_config",
    "matches_internal_folder_name",
]
