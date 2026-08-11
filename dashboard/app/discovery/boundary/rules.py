"""Project-boundary heuristics (§1-4 of the Sprint 3 brief).

Transparent, explainable, non-ML -- same design principle as
`classifier.py`/`health.py`/`recommendation/engine.py`. Every decision
carries the specific evidence behind it. Nothing here reads the
filesystem; it only reasons over fields `detectors.py`/`classifier.py`
already populated, plus the parent/child relationships `hierarchy.py`
builds from `parent_path`.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.discovery.detectors import has_own_strong_markers as _has_own_strong_markers_shallow
from app.discovery.models import DiscoveredProject

# §4: folder names that normally stay internal to their parent project.
# Checked *after* a folder's own strong markers (own .git/tech marker) --
# see `hierarchy._assign_child` -- so a numbered folder that happens to be
# its own repository is never forced into this bucket ("use the parent
# context and evidence", not the name alone).
INTERNAL_FOLDER_NAMES = {
    "docs",
    "documentation",
    "assets",
    "images",
    "prompts",
    "templates",
    "references",
    "tests",
    "scripts",
    "workflows",
    "providers",
    "src",
    "app",
    "public",
    "static",
    "config",
    "build",
    "dist",
    "output",
    "node_modules",
    "venv",
    ".venv",
}
NUMBERED_PREFIX_RE = re.compile(r"^\d{2}_")


def matches_internal_folder_name(name: str) -> bool:
    return name.lower() in INTERNAL_FOLDER_NAMES or bool(NUMBERED_PREFIX_RE.match(name))


def has_own_strong_markers(project: DiscoveredProject) -> bool:
    """§2: a folder qualifies on its own (no parent-context needed) when it
    has a real repository or package marker of its own -- not a README,
    not images, not docs, not a generic name.

    Deliberately re-checks the filesystem directly at this folder's own
    root (the same cheap, non-recursive, read-only check `scanner.py`
    already uses to decide whether to descend) rather than trusting
    `project.tech_markers`: that list comes from `detectors/markers.py`'s
    *recursive* inventory walk, so for a container folder it also includes
    marker files that belong to its own nested children -- exactly the
    "own evidence" vs. "child's evidence" distinction this function exists
    to make. `git.is_repo` has no such contamination (git_reader only ever
    checks for `.git` at this exact path), so it's read directly.
    """
    if project.git.is_repo:
        return True
    return _has_own_strong_markers_shallow(Path(project.root_path))


def confidence_from_evidence(
    own_markers: bool, children_with_markers: bool, substantial_structure: bool
) -> float:
    score = 0.0
    if own_markers:
        score += 0.5
    if children_with_markers:
        score += 0.35
    if substantial_structure:
        score += 0.25
    return round(min(score, 1.0), 2)


def is_substantial_structure(project: DiscoveredProject, child_count: int) -> bool:
    """§2 "README plus substantial project structure" / "explicit ... project
    documentation" -- a README alone is explicitly *not* enough (§2's
    negative list); this requires a README plus either a real roadmap/
    changelog or at least three internal folders underneath it."""
    return bool(
        project.has_readme and (child_count >= 3 or project.has_roadmap or project.has_changelog)
    )


def is_independent_despite_nesting(child: DiscoveredProject) -> bool:
    """§3's exception: a nested repository with its own remote, its own
    roadmap/changelog, and high overall confidence looks like a genuinely
    independent product that just happens to sit inside another project's
    folder, rather than a component of it. Deliberately a high bar --
    without it, every nested git repo would default to "repository", which
    is the correct default per §3.
    """
    return (
        child.git.is_repo
        and child.confidence_score >= 0.75
        and bool(child.git.remote_url)
        and (child.has_roadmap or child.has_changelog)
    )
