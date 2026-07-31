"""Launcher script inventory: batch/cmd files and PowerShell scripts.
Both are move-safety signals (they commonly embed absolute paths), grouped
in one module because they're the same one-line "match this extension"
check twice, not because they're the same concern -- each has its own
`Findings` type and is registered separately."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.discovery.detectors.inventory import FolderInventory


@dataclass
class BatchScriptFindings:
    batch_scripts: list[str] = field(default_factory=list)


def detect_batch(inventory: FolderInventory) -> BatchScriptFindings:
    findings = BatchScriptFindings()
    for f in inventory.files:
        if f.ext in (".bat", ".cmd"):
            findings.batch_scripts.append(f.path)
    return findings


@dataclass
class PowerShellScriptFindings:
    powershell_scripts: list[str] = field(default_factory=list)


def detect_powershell(inventory: FolderInventory) -> PowerShellScriptFindings:
    findings = PowerShellScriptFindings()
    for f in inventory.files:
        if f.ext == ".ps1":
            findings.powershell_scripts.append(f.path)
    return findings
