"""Technology/language indicators: top-level tech marker files
(`package.json`, `pyproject.toml`, ...) plus a language histogram from file
extensions. `frameworks` is part of `DiscoveredProject`'s shape but has no
detector in Sprint 1 or this refactor -- it was never populated before
this change either, so it stays an always-empty list (parity, not an
omission)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.discovery.detectors.constants import TOP_LEVEL_MARKER_FILES
from app.discovery.detectors.inventory import FolderInventory

LANGUAGE_EXT_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".swift": "Swift",
    ".kt": "Kotlin",
}


@dataclass
class MarkerFindings:
    tech_markers: list[str] = field(default_factory=list)
    languages: dict[str, int] = field(default_factory=dict)


def detect(inventory: FolderInventory) -> MarkerFindings:
    findings = MarkerFindings()

    for f in inventory.files:
        # NOTE: a `go.mod` file is matched by *both* checks below (it's in
        # TOP_LEVEL_MARKER_FILES *and* matches `stem_lower == "go.mod"`),
        # so it is appended to `tech_markers` twice. That is a pre-existing
        # Sprint 1 quirk, not something introduced by this refactor --
        # fixing it would change `len(tech_markers)`, which feeds
        # `classifier.classify_confidence`, which could silently change a
        # go.mod project's classification. Preserved deliberately for
        # behavioral parity; see the Sprint 1.5 completion report.
        if f.name in TOP_LEVEL_MARKER_FILES:
            findings.tech_markers.append(f.path)
        if f.stem_lower.endswith(".csproj") or f.stem_lower == "go.mod":
            findings.tech_markers.append(f.path)

        if f.ext in LANGUAGE_EXT_MAP:
            lang = LANGUAGE_EXT_MAP[f.ext]
            findings.languages[lang] = findings.languages.get(lang, 0) + 1

    return findings
