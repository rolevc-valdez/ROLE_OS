"""Hardcoded absolute-path detection -- the one detector that reads file
*contents*, not just directory-entry metadata. The shared `FolderInventory`
walk already paid the cost (and the risk -- symlinks, permissions) of
enumerating every file; this module only opens the subset of already-
enumerated files whose extension suggests they're text/config, under its
own explicit, testable byte/file budget, so one expensive detector can
never starve another's budget or blow past the audit's overall runtime."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.discovery.detectors.inventory import FolderInventory
from app.discovery.models import AbsolutePathReference

TEXT_SCAN_EXT = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".ps1",
    ".bat",
    ".cmd",
    ".sh",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".cfg",
    ".ini",
    ".toml",
    ".code-workspace",
}

# Absolute-path references commonly sit inside quoted strings, and real
# paths on this machine contain spaces/parentheses (e.g. "My Drive
# (user@example.com)"), so we only stop at a closing quote/angle-bracket
# or end of line, not at whitespace.
ABS_WIN_RE = re.compile(r"[A-Za-z]:\\+[^\r\n\"'<>|]+")
ABS_POSIX_RE = re.compile(r"/(?:home|Users|mnt|root)/[^\r\n\"'<>|]+")

# This detector's own budget -- explicit and testable, not shared with any
# other detector's cost.
MAX_SCAN_FILES = 500
MAX_SCAN_BYTES = 200_000
MAX_REFS_KEPT = 25


@dataclass
class AbsolutePathFindings:
    absolute_path_refs: list[AbsolutePathReference] = field(default_factory=list)
    absolute_path_ref_count: int = 0


def _scan_file(file_path: Path, byte_budget: int) -> tuple[list[AbsolutePathReference], int]:
    """Read up to `byte_budget` bytes of a text file, read-only, looking
    for hardcoded absolute-path strings. Never writes to the file."""
    refs: list[AbsolutePathReference] = []
    read_bytes = 0
    try:
        size = file_path.stat().st_size
        if size <= 0:
            return refs, 0
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, start=1):
                read_bytes += len(line.encode("utf-8", errors="ignore"))
                if read_bytes > byte_budget:
                    break
                for pattern in (ABS_WIN_RE, ABS_POSIX_RE):
                    match = pattern.search(line)
                    if match:
                        refs.append(
                            AbsolutePathReference(
                                file=str(file_path),
                                line=lineno,
                                snippet=match.group(0)[:200],
                            )
                        )
    except OSError:
        pass
    return refs, read_bytes


def detect(
    inventory: FolderInventory,
    *,
    max_scan_files: int = MAX_SCAN_FILES,
    max_scan_bytes: int = MAX_SCAN_BYTES,
    max_refs_kept: int = MAX_REFS_KEPT,
) -> AbsolutePathFindings:
    findings = AbsolutePathFindings()

    budget_files = max_scan_files
    budget_bytes = max_scan_bytes

    for f in inventory.files:
        if f.ext not in TEXT_SCAN_EXT or budget_files <= 0:
            continue
        refs, bytes_read = _scan_file(Path(f.path), budget_bytes)
        budget_files -= 1
        budget_bytes -= bytes_read
        for ref in refs:
            findings.absolute_path_ref_count += 1
            if len(findings.absolute_path_refs) < max_refs_kept:
                findings.absolute_path_refs.append(ref)

    return findings
