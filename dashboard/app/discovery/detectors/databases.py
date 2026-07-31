"""SQLite database file inventory -- both an asset-discovery signal and,
indirectly, a move-safety one (a script referencing one of these by
absolute path is caught by `absolute_paths.py`, not here)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.discovery.detectors.inventory import FolderInventory

DB_EXT = {".db", ".sqlite", ".sqlite3"}


@dataclass
class DatabaseFindings:
    sqlite_files: list[str] = field(default_factory=list)


def detect(inventory: FolderInventory) -> DatabaseFindings:
    findings = DatabaseFindings()
    for f in inventory.files:
        if f.ext in DB_EXT:
            findings.sqlite_files.append(f.path)
    return findings
