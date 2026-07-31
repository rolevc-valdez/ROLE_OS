"""Reusable-asset counting: images/video/documents/design files/fonts, plus
logo/icon/favicon-named images called out separately. One responsibility:
"how much creative/reference material lives here?" -- no code/doc signal."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.discovery.detectors.inventory import FolderInventory

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv"}
DOCUMENT_EXT = {".pdf"}
DESIGN_FILE_EXT = {".psd", ".ai", ".xd", ".fig", ".sketch"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}

LOGO_RE = re.compile(r"(logo|icon|favicon)", re.I)


@dataclass
class AssetFindings:
    image_count: int = 0
    video_count: int = 0
    document_count: int = 0
    design_file_count: int = 0
    font_count: int = 0
    logo_files: list[str] = field(default_factory=list)


def detect(inventory: FolderInventory) -> AssetFindings:
    findings = AssetFindings()

    for f in inventory.files:
        # Mirrors the original elif chain: a file only ever counts toward
        # one of these buckets, by extension precedence order below.
        if f.ext in IMAGE_EXT:
            findings.image_count += 1
            if LOGO_RE.search(f.stem_lower):
                findings.logo_files.append(f.path)
        elif f.ext in VIDEO_EXT:
            findings.video_count += 1
        elif f.ext in DOCUMENT_EXT:
            findings.document_count += 1
        elif f.ext in DESIGN_FILE_EXT:
            findings.design_file_count += 1
        elif f.ext in FONT_EXT:
            findings.font_count += 1

    return findings
