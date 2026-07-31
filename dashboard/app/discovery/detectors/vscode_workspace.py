"""VS Code `*.code-workspace` file inventory -- move-safety relevant, since
these commonly embed absolute folder paths."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.discovery.detectors.inventory import FolderInventory


@dataclass
class VscodeWorkspaceFindings:
    vscode_workspace_files: list[str] = field(default_factory=list)


def detect(inventory: FolderInventory) -> VscodeWorkspaceFindings:
    findings = VscodeWorkspaceFindings()
    for f in inventory.files:
        if f.stem_lower.endswith(".code-workspace"):
            findings.vscode_workspace_files.append(f.path)
    return findings
