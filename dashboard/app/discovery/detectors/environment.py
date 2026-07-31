"""`.env`/`.env.*` file inventory -- a move-safety signal (likely
machine/environment-specific config), not a classification signal."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.discovery.detectors.inventory import FolderInventory

ENV_FILE_RE = re.compile(r"^\.env(\..+)?$", re.I)


@dataclass
class EnvironmentFindings:
    env_files: list[str] = field(default_factory=list)


def detect(inventory: FolderInventory) -> EnvironmentFindings:
    findings = EnvironmentFindings()
    for f in inventory.files:
        if ENV_FILE_RE.match(f.name):
            findings.env_files.append(f.path)
    return findings
