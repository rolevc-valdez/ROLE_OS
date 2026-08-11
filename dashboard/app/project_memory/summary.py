"""Bounded, deterministic "Project Summary" extraction for the Resume
Prompt (hotfix following real-world Resume Work validation).

The prompt's other sections (Current Objective, Where We Left Off,
Pending Work, Next Action) all assume the reader already knows what the
project IS -- none of them ever actually says so. A fresh Claude
conversation given only those sections still had to ask "What is this
project?" before it could do anything useful with "Pending Work" or
"Next Action". This module answers that question first.

Same discipline as `app.discovery.next_action`: plain, bounded (20KB)
text reads and regex extraction, no AI/LLM call, and every result names
its own source -- never a generated sentence pretending to be prose from
a file that doesn't say it. If nothing is found anywhere in the priority
list below, the summary says so honestly instead of inventing one.

Source priority (first real text found wins, never merged/blended):
    README.md -> PROJECT.md -> ROADMAP.md -> ProjectContext -> Discovery
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_MAX_READ_BYTES = 20_000
_MAX_SUMMARY_WORDS = 150

_HEADING_RE = re.compile(r"^(#+)\s*(.+?)\s*$", re.MULTILINE)
_METADATA_LINE_RE = re.compile(r"^\*\*[^*]+\*\*\s*:")  # e.g. "**Version:** 1.0"
_BADGE_OR_IMAGE_RE = re.compile(r"^\s*(\[!\[.*\]\(.*\)\]\(.*\)|!\[.*\]\(.*\))\s*$")
_HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$")

# Section headings likely to hold an actual project description, tried
# before falling back to the first plain paragraph -- matched as a
# substring of the heading text (case-insensitive), so "## What ROLE OS
# is" matches "what" and "## Purpose" matches "purpose".
_SUMMARY_HEADING_KEYWORDS = ("purpose", "overview", "about", "what")


def _find_case_insensitive(root: Path, name: str) -> Path | None:
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower() == name.lower():
                return entry
    except OSError:
        pass
    return None


def _read_text(path: Path) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(_MAX_READ_BYTES)
    except OSError:
        return None


def _first_paragraph(section: str) -> str | None:
    """The first run of real prose lines in `section`, stopping at the
    first blank line once some body text has been collected -- skips
    blank lines, bold metadata lines (`**Version:** ...`), badges/shield
    images, and horizontal rules."""
    body_lines: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            if body_lines:
                break
            continue
        if (
            _METADATA_LINE_RE.match(stripped)
            or _BADGE_OR_IMAGE_RE.match(stripped)
            or _HR_RE.match(stripped)
        ):
            continue
        body_lines.append(stripped)
    if not body_lines:
        return None
    return " ".join(body_lines)


def _text_after_heading(text: str, heading_end: int) -> str | None:
    rest = text[heading_end:]
    next_heading = _HEADING_RE.search(rest)
    section = rest[: next_heading.start()] if next_heading else rest
    return _first_paragraph(section)


def _from_named_section(text: str) -> str | None:
    for match in _HEADING_RE.finditer(text):
        heading_text = match.group(2).strip().lower()
        if any(keyword in heading_text for keyword in _SUMMARY_HEADING_KEYWORDS):
            found = _text_after_heading(text, match.end())
            if found:
                return found
    return None


def _from_intro_paragraph(text: str) -> str | None:
    """Falls back to the first real prose paragraph after the title
    heading (or the very start of the file, if it has no heading at
    all)."""
    headings = list(_HEADING_RE.finditer(text))
    if not headings:
        return _first_paragraph(text)
    return _text_after_heading(text, headings[0].end())


def _bounded_words(text: str, max_words: int = _MAX_SUMMARY_WORDS) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def _from_markdown_file(root: Path, filename: str) -> tuple[str, str] | None:
    path = _find_case_insensitive(root, filename)
    if not path:
        return None
    text = _read_text(path)
    if not text:
        return None
    excerpt = _from_named_section(text) or _from_intro_paragraph(text)
    return (_bounded_words(excerpt), str(path)) if excerpt else None


def _from_project_context(context: dict[str, Any]) -> str | None:
    """Falls back to already-known, structured `ProjectContext` facts --
    never a generated description, only a plain restatement of fields
    that are already there (classification, technology stack, business
    value, status)."""
    display_name = context.get("display_name") or "This project"
    facts: list[str] = []
    classification = context.get("classification")
    if classification and classification != "Unknown":
        facts.append(f"a {classification}")
    tech_stack = context.get("technology_stack") or []
    if tech_stack:
        facts.append(f"built with {', '.join(tech_stack[:6])}")
    business_value = context.get("business_value")
    if business_value:
        facts.append(f"business value: {business_value}")
    status = context.get("status")
    if status:
        facts.append(f"status: {status}")
    if not facts:
        return None
    return f"{display_name} is " + ", ".join(facts) + "."


def _from_discovery_signals(context: dict[str, Any]) -> str | None:
    """Last resort before an honest "not found": Discovery-derived facts
    on `ProjectContext` not already covered by `_from_project_context`
    (document/documentation/test signals, and where the project actually
    lives)."""
    display_name = context.get("display_name") or "This project"
    facts: list[str] = []
    if context.get("documents_count"):
        facts.append(f"{context['documents_count']} document(s) indexed")
    if context.get("documentation_status"):
        facts.append(f"documentation status: {context['documentation_status']}")
    if context.get("test_status"):
        facts.append(f"tests: {context['test_status']}")
    if context.get("root_path"):
        facts.append(f"located at {context['root_path']}")
    if not facts:
        return None
    return f"{display_name} -- " + "; ".join(facts) + "."


def build_project_summary(context: dict[str, Any]) -> dict[str, Any]:
    """The one Project Summary builder for the Resume Prompt. Returns
    `{"text": str, "source": str, "source_path": str | None}` -- `text`
    is always non-empty and bounded to 150 words. Never invents a
    description: if no real text is found anywhere in the priority
    list (README -> PROJECT.md -> ROADMAP -> ProjectContext ->
    Discovery), `text` says so plainly instead."""
    root_path = context.get("root_path")
    if root_path:
        root = Path(root_path)
        if root.is_dir():
            for filename in ("README.md", "PROJECT.md", "ROADMAP.md"):
                found = _from_markdown_file(root, filename)
                if found:
                    text, path = found
                    return {"text": text, "source": filename, "source_path": path}

    project_context_summary = _from_project_context(context)
    if project_context_summary:
        return {"text": project_context_summary, "source": "ProjectContext", "source_path": None}

    discovery_summary = _from_discovery_signals(context)
    if discovery_summary:
        return {"text": discovery_summary, "source": "Discovery", "source_path": None}

    display_name = context.get("display_name") or "This project"
    return {
        "text": (
            f"{display_name} -- no description found in README/PROJECT.md/ROADMAP, "
            "and no structured project details (technology stack, classification) "
            "are available yet."
        ),
        "source": "none",
        "source_path": None,
    }
