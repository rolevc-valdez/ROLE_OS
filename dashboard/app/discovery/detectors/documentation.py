"""README / ROADMAP / CHANGELOG / TODO / LICENSE presence, plus docs
folders. One responsibility: "what does this folder say about itself in
plain-text project documentation?" -- no code/test/asset signal here."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.discovery.detectors.inventory import FolderInventory

README_RE = re.compile(r"^readme(\..*)?$", re.I)
ROADMAP_RE = re.compile(r"^roadmap(\..*)?$", re.I)
CHANGELOG_RE = re.compile(r"^changelog(\..*)?$", re.I)
TODO_RE = re.compile(r"^todo(\..*)?$", re.I)
LICENSE_RE = re.compile(r"^licen[sc]e(\..*)?$", re.I)

DOC_DIR_NAMES = {"docs", "documentation", "doc"}


@dataclass
class DocumentationFindings:
    has_readme: bool = False
    has_roadmap: bool = False
    has_changelog: bool = False
    has_todo: bool = False
    has_license: bool = False
    doc_folders: list[str] = field(default_factory=list)


def detect(inventory: FolderInventory) -> DocumentationFindings:
    findings = DocumentationFindings()

    for d in inventory.dirs:
        if d.name_lower in DOC_DIR_NAMES:
            findings.doc_folders.append(d.path)

    for f in inventory.files:
        if README_RE.match(f.name):
            findings.has_readme = True
        if ROADMAP_RE.match(f.name):
            findings.has_roadmap = True
        if CHANGELOG_RE.match(f.name):
            findings.has_changelog = True
        if TODO_RE.match(f.name):
            findings.has_todo = True
        if LICENSE_RE.match(f.name):
            findings.has_license = True

    return findings
