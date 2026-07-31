"""Obsidian vault presence: a `.obsidian` config directory. Move-safety
relevant -- an Obsidian vault's own config can reference the vault's
absolute path in workspace/plugin settings."""

from __future__ import annotations

from dataclasses import dataclass

from app.discovery.detectors.inventory import FolderInventory


@dataclass
class ObsidianFindings:
    has_obsidian_vault: bool = False


def detect(inventory: FolderInventory) -> ObsidianFindings:
    findings = ObsidianFindings()
    for d in inventory.dirs:
        if d.name_lower == ".obsidian":
            findings.has_obsidian_vault = True
    return findings
