"""The one read-only filesystem walk every detector is built from.

`build_inventory()` walks a folder tree exactly once -- never opens a file
for writing, never deletes/renames/creates anything, and never follows a
symlink or NTFS junction (recorded in `reparse_points_skipped` instead of
being descended into, so a cyclic link can never cause an infinite walk).
It records only raw structural facts (which files and directories exist,
their names/extensions/mtimes) with zero interpretation -- no detector's
"is this a README" / "is this a test file" logic lives here. Every
detector in this package is a pure function over the resulting
`FolderInventory`, so adding a new detector never means walking the
filesystem again.

File *contents* are a different story: a detector that needs to read a
file's bytes (today, only `absolute_paths.py`) still has to open that file
itself. That is not "duplicating traversal" -- the expensive, risky part
this module guards (directory enumeration, symlink/junction safety,
permission handling) happens exactly once here; reading a handful of
already-enumerated files' contents is a per-detector cost that only the
detectors which need it pay.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.discovery.detectors.constants import IGNORE_DIR_NAMES, MAX_FILES


@dataclass(frozen=True)
class FileRecord:
    path: str
    name: str
    stem_lower: str
    ext: str


@dataclass(frozen=True)
class DirRecord:
    path: str
    name: str
    name_lower: str
    parent_name_lower: str


@dataclass
class FolderInventory:
    """Raw, read-only facts about one folder tree. No detector-specific
    interpretation -- every field here is a structural fact a human could
    verify by looking at the filesystem, not a judgment call."""

    root: Path
    files: list[FileRecord] = field(default_factory=list)
    dirs: list[DirRecord] = field(default_factory=list)
    reparse_points_skipped: list[str] = field(default_factory=list)
    scan_errors: list[str] = field(default_factory=list)
    total_files: int = 0
    total_dirs: int = 0
    last_modified: str | None = None
    truncated: bool = False


def _is_reparse_point(entry: "os.DirEntry") -> bool:
    """True for symlinks and Windows junctions/reparse points."""
    try:
        if entry.is_symlink():
            return True
        st = entry.stat(follow_symlinks=False)
        attrs = getattr(st, "st_file_attributes", 0)
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def build_inventory(root: Path) -> FolderInventory:
    """Walk `root` once (read-only) and return the raw facts detectors
    consume. Mirrors the exact traversal order/budget of Sprint 1's
    `analyze_folder` walk so detector output is byte-for-byte equivalent."""
    inventory = FolderInventory(root=root)

    stack = [root]
    file_count = 0
    dir_count = 0
    max_mtime = 0.0

    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except PermissionError as exc:
            inventory.scan_errors.append(f"permission denied: {current} ({exc})")
            continue
        except OSError as exc:
            inventory.scan_errors.append(f"error reading {current}: {exc}")
            continue

        for entry in entries:
            if _is_reparse_point(entry):
                inventory.reparse_points_skipped.append(entry.path)
                continue

            if entry.is_dir(follow_symlinks=False):
                dir_count += 1
                if entry.name in IGNORE_DIR_NAMES:
                    continue
                inventory.dirs.append(
                    DirRecord(
                        path=entry.path,
                        name=entry.name,
                        name_lower=entry.name.lower(),
                        parent_name_lower=Path(current).name.lower(),
                    )
                )
                if file_count < MAX_FILES:
                    stack.append(Path(entry.path))
                continue

            if not entry.is_file(follow_symlinks=False):
                continue

            file_count += 1
            if file_count > MAX_FILES:
                inventory.truncated = True
                continue

            try:
                stat = entry.stat(follow_symlinks=False)
                max_mtime = max(max_mtime, stat.st_mtime)
            except OSError:
                pass

            name = entry.name
            inventory.files.append(
                FileRecord(
                    path=entry.path,
                    name=name,
                    stem_lower=name.lower(),
                    ext=Path(name).suffix.lower(),
                )
            )

    inventory.total_files = file_count
    inventory.total_dirs = dir_count
    if max_mtime:
        inventory.last_modified = datetime.fromtimestamp(max_mtime, tz=timezone.utc).isoformat()

    return inventory
