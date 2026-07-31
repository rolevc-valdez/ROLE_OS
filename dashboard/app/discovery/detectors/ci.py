"""GitHub Actions presence: a `.github/workflows` directory."""

from __future__ import annotations

from dataclasses import dataclass

from app.discovery.detectors.inventory import FolderInventory


@dataclass
class CiFindings:
    has_github_actions: bool = False


def detect(inventory: FolderInventory) -> CiFindings:
    findings = CiFindings()
    for d in inventory.dirs:
        if d.name_lower == "workflows" and d.parent_name_lower == ".github":
            findings.has_github_actions = True
    return findings
