"""Root-level candidate discovery (§6 of the Import Engine proposal).

Read-only: only ever calls `os.scandir`/`Path.exists`, never writes,
deletes, or renames anything under the scanned root.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.discovery.boundary.exclusions import is_excluded
from app.discovery.detectors import IGNORE_DIR_NAMES, has_own_strong_markers, is_candidate_signal


@dataclass
class Candidate:
    path: Path
    depth: int
    parent_path: Path | None
    excluded: bool = False
    exclusion_reason: str | None = None


def _safe_subdirs(path: Path, skipped: list[str]) -> list[os.DirEntry]:
    dirs: list[os.DirEntry] = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                if entry.is_symlink():
                    skipped.append(entry.path)
                    continue
                try:
                    st = entry.stat(follow_symlinks=False)
                    if getattr(st, "st_file_attributes", 0) & 0x400:  # reparse point
                        skipped.append(entry.path)
                        continue
                except OSError:
                    continue
                if entry.name in IGNORE_DIR_NAMES:
                    continue
                dirs.append(entry)
    except PermissionError:
        skipped.append(f"permission denied: {path}")
    except OSError as exc:
        skipped.append(f"error reading {path}: {exc}")
    return dirs


def discover_candidates(
    root: Path, max_depth: int = 2, extra_exclusions: list[str] | None = None
) -> tuple[list[Candidate], list[str]]:
    """Return direct (depth 1) folders under `root`, plus nested (depth 2+)
    project folders found inside any depth-1 folder that doesn't already
    look like a self-contained project (a "container"/monorepo folder).

    Depth-1 folders are always returned (even if they turn out to classify
    as Non-project) so the report can show what was found and rejected.
    Deeper folders are only returned if they show a minimal project signal,
    to avoid flooding the report with every subfolder of a container.

    An excluded folder (§5: `app.discovery.boundary.exclusions`) is still
    returned -- so it can be reported with its exclusion reason -- but its
    children are never enumerated: exclusion is not recursively re-checked
    or re-scanned, by design.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"discovery root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"discovery root is not a directory: {root}")

    skipped: list[str] = []
    candidates: list[Candidate] = []

    for entry in _safe_subdirs(root, skipped):
        depth1_path = Path(entry.path)
        excluded, reason = is_excluded(depth1_path, root, extra_exclusions)
        candidates.append(
            Candidate(path=depth1_path, depth=1, parent_path=None, excluded=excluded, exclusion_reason=reason)
        )
        if excluded:
            continue  # never descend into an excluded folder's children

        if max_depth < 2:
            continue
        if has_own_strong_markers(depth1_path):
            continue

        for nested_entry in _safe_subdirs(depth1_path, skipped):
            nested_path = Path(nested_entry.path)
            nested_excluded, nested_reason = is_excluded(nested_path, root, extra_exclusions)
            if nested_excluded:
                candidates.append(
                    Candidate(
                        path=nested_path,
                        depth=2,
                        parent_path=depth1_path,
                        excluded=True,
                        exclusion_reason=nested_reason,
                    )
                )
                continue
            if is_candidate_signal(nested_path):
                candidates.append(
                    Candidate(path=nested_path, depth=2, parent_path=depth1_path)
                )

    return candidates, skipped
