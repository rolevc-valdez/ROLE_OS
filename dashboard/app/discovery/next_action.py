"""Deterministic, explainable "next action" extraction (Sprint 4).

Searches, in priority order, for a concrete "what should I do next" signal
for a project folder: an AI Session Snapshot hint (passed in by the
caller -- this module has no database access), `NEXT_ACTION.md`,
`TODO.md`/a `## TODO` section, `ROADMAP.md`'s current milestone, README's
"Next Steps" section, CHANGELOG's unreleased section, and finally the
latest git commit message (also passed in). No AI/LLM call anywhere --
plain text/regex extraction, same style as the rest of `app.discovery`.

Every result carries its source and a confidence, so "the system invented
this" is never a possible complaint -- it either found real text at a real
path, or it says so and returns nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_MAX_READ_BYTES = 20_000

_CONFIDENCE_BY_SOURCE = {
    "ai_session": 0.95,
    "NEXT_ACTION.md": 0.9,
    "TODO.md": 0.75,
    "TODO section": 0.7,
    "ROADMAP.md": 0.65,
    "README Next Steps": 0.6,
    "CHANGELOG unreleased": 0.5,
    "latest git commit": 0.3,
    "none": 0.0,
}


@dataclass
class NextActionResult:
    text: str | None
    source: str
    source_path: str | None
    confidence: float
    extracted_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(_MAX_READ_BYTES)
    except OSError:
        return None


def _first_non_empty_lines(text: str, max_lines: int = 5) -> str | None:
    lines = [
        ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    if not lines:
        return None
    return "\n".join(lines[:max_lines])


def _find_case_insensitive(root: Path, name: str) -> Path | None:
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower() == name.lower():
                return entry
    except OSError:
        pass
    return None


def _from_next_action_file(root: Path) -> tuple[str, str] | None:
    path = _find_case_insensitive(root, "NEXT_ACTION.md")
    if not path:
        return None
    text = _read_text(path)
    if not text:
        return None
    excerpt = _first_non_empty_lines(text)
    return (excerpt, str(path)) if excerpt else None


_TODO_ITEM_RE = re.compile(r"^\s*[-*]\s*\[ \]\s*(.+)$", re.MULTILINE)
_TODO_LINE_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)


def _from_todo_file(root: Path) -> tuple[str, str] | None:
    path = _find_case_insensitive(root, "TODO.md") or _find_case_insensitive(root, "TODO.txt")
    if not path:
        return None
    text = _read_text(path)
    if not text:
        return None
    match = _TODO_ITEM_RE.search(text) or _TODO_LINE_RE.search(text)
    excerpt = match.group(1).strip() if match else _first_non_empty_lines(text)
    return (excerpt, str(path)) if excerpt else None


_HEADING_RE_TEMPLATE = r"^#+\s*{}\s*$"


def _section_after_heading(text: str, heading_pattern: str, max_lines: int = 6) -> str | None:
    heading_re = re.compile(
        _HEADING_RE_TEMPLATE.format(heading_pattern), re.IGNORECASE | re.MULTILINE
    )
    match = heading_re.search(text)
    if not match:
        return None
    rest = text[match.end() :]
    next_heading = re.search(r"^#+\s", rest, re.MULTILINE)
    section = rest[: next_heading.start()] if next_heading else rest
    return _first_non_empty_lines(section, max_lines)


def _from_todo_section(root: Path) -> tuple[str, str] | None:
    for filename in ("README.md", "ROADMAP.md"):
        path = _find_case_insensitive(root, filename)
        if not path:
            continue
        text = _read_text(path)
        if not text:
            continue
        excerpt = _section_after_heading(text, r"TODO")
        if excerpt:
            return excerpt, str(path)
    return None


def _from_roadmap(root: Path) -> tuple[str, str] | None:
    path = _find_case_insensitive(root, "ROADMAP.md")
    if not path:
        return None
    text = _read_text(path)
    if not text:
        return None
    # "Current milestone": the first unchecked item, or else the first
    # heading's own line plus whatever immediately follows it.
    unchecked = _TODO_ITEM_RE.search(text)
    if unchecked:
        return unchecked.group(1).strip(), str(path)
    heading = re.search(r"^#+\s*(.+)$", text, re.MULTILINE)
    if heading:
        excerpt = _first_non_empty_lines(text[heading.end() :]) or heading.group(1).strip()
        return excerpt, str(path)
    return None


def _from_readme_next_steps(root: Path) -> tuple[str, str] | None:
    path = _find_case_insensitive(root, "README.md")
    if not path:
        return None
    text = _read_text(path)
    if not text:
        return None
    excerpt = _section_after_heading(text, r"Next Steps")
    return (excerpt, str(path)) if excerpt else None


def _from_changelog_unreleased(root: Path) -> tuple[str, str] | None:
    path = _find_case_insensitive(root, "CHANGELOG.md")
    if not path:
        return None
    text = _read_text(path)
    if not text:
        return None
    excerpt = _section_after_heading(text, r"\[?Unreleased\]?", max_lines=3)
    return (excerpt, str(path)) if excerpt else None


def extract_next_action(
    root_path: str | Path,
    *,
    ai_session_next_prompt: str | None = None,
    ai_session_pending_work: str | None = None,
    last_commit_message: str | None = None,
    last_commit_date: str | None = None,
) -> NextActionResult:
    """Read-only. Never writes, never invents a value -- if nothing is
    found anywhere in the priority list, `text` is `None` (render as "Not
    yet defined")."""
    root = Path(root_path)

    ai_hint = (ai_session_next_prompt or "").strip() or (ai_session_pending_work or "").strip()
    if ai_hint:
        return NextActionResult(
            text=ai_hint,
            source="ai_session",
            source_path=None,
            confidence=_CONFIDENCE_BY_SOURCE["ai_session"],
            extracted_at=_now_iso(),
        )

    if not root.is_dir():
        return NextActionResult(
            text=None, source="none", source_path=None, confidence=0.0, extracted_at=_now_iso()
        )

    for finder, source in (
        (_from_next_action_file, "NEXT_ACTION.md"),
        (_from_todo_file, "TODO.md"),
        (_from_todo_section, "TODO section"),
        (_from_roadmap, "ROADMAP.md"),
        (_from_readme_next_steps, "README Next Steps"),
        (_from_changelog_unreleased, "CHANGELOG unreleased"),
    ):
        found = finder(root)
        if found:
            text, path = found
            return NextActionResult(
                text=text,
                source=source,
                source_path=path,
                confidence=_CONFIDENCE_BY_SOURCE[source],
                extracted_at=_now_iso(),
            )

    if last_commit_message:
        text = last_commit_message + (f" ({last_commit_date})" if last_commit_date else "")
        return NextActionResult(
            text=text,
            source="latest git commit",
            source_path=None,
            confidence=_CONFIDENCE_BY_SOURCE["latest git commit"],
            extracted_at=_now_iso(),
        )

    return NextActionResult(
        text=None, source="none", source_path=None, confidence=0.0, extracted_at=_now_iso()
    )
