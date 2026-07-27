"""Deterministic, rule-based extractors for the seven supported knowledge
object types. Pattern-matching only -- no external AI/LLM call, no
generation, no summarization. Every extractor returns `(title, confidence)`
pairs; `title` is verbatim text pulled from the conversation (a matched
line, a detected filename, a capitalized name), never rewritten.

Deliberately self-contained: does not import `builder/extractors/` (that
package does its own, separate job -- classifying a conversation into a
*specific* known project like "ROLE_MASTER_FACTORY" for the Builder
pipeline). This module's job is generic, type-only extraction across any
imported conversation.
"""

from __future__ import annotations

import re
from typing import Iterable

PROJECT_PATTERNS = [r"\bproyecto\b", r"\bproject\b", r"\biniciativa\b", r"lanzamiento de", r"launch of"]
DECISION_PATTERNS = [r"\bdecid", r"\baprob", r"quedamos", r"vamos a usar", r"se define", r"\bagreed\b", r"\bdecision\b"]
TASK_PATTERNS = [r"\bpendiente", r"\bfalta\b", r"\bto-?do\b", r"\btask\b", r"hay que", r"necesitamos", r"siguiente paso"]
IDEA_PATTERNS = [r"\bidea\b", r"podr[ií]amos", r"\bwhat if\b", r"se me ocurre", r"\bpropuesta\b", r"brainstorm", r"\bsuggest"]

PEOPLE_RE = re.compile(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,2}\b")
PEOPLE_BLOCKED = {
    "Google Drive", "Microsoft Excel", "Windows Notepad", "ChatGPT Plus", "Business Central",
    "ROLE OS", "Knowledge OS", "Master Factory",
}

DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "txt", "md", "csv", "xlsx", "xls", "pptx", "ppt", "json"}
ASSET_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "svg", "mp4", "mov", "mp3", "wav", "zip"}
FILE_RE = re.compile(
    r"\b[^\s/\\]+\.(?:" + "|".join(sorted(DOCUMENT_EXTENSIONS | ASSET_EXTENSIONS)) + r")\b",
    re.I,
)

_MIN_CONFIDENCE = 0.55
_STEP_CONFIDENCE = 0.1
_MAX_CONFIDENCE = 0.9
_FILE_CONFIDENCE = 0.85


def lines_from_content(content: list[dict]) -> list[str]:
    """Split every message's text into candidate line fragments, the same
    "sentence-like line" heuristic the Builder's extractors use."""
    out: list[str] = []
    for message in content:
        text = message.get("text") or ""
        for raw in text.splitlines():
            line = re.sub(r"^[\-*•\d.\s]+", "", raw).strip()
            if 8 <= len(line) <= 400:
                out.append(line)
    return out


def full_text(content: list[dict]) -> str:
    return "\n".join(message.get("text") or "" for message in content)


def _pick(lines: Iterable[str], patterns: list[str], limit: int = 10) -> list[tuple[str, float]]:
    """Return up to `limit` unique lines matching any pattern, each paired
    with a confidence that rises slightly with the number of keyword hits
    in that line."""
    rx = re.compile("|".join(patterns), re.I)
    out: list[tuple[str, float]] = []
    seen: set[str] = set()
    for line in lines:
        if line in seen:
            continue
        hits = len(rx.findall(line))
        if hits:
            confidence = min(_MAX_CONFIDENCE, _MIN_CONFIDENCE + _STEP_CONFIDENCE * (hits - 1))
            out.append((line, confidence))
            seen.add(line)
            if len(out) >= limit:
                break
    return out


def extract_projects(lines: list[str], limit: int = 10) -> list[tuple[str, float]]:
    return _pick(lines, PROJECT_PATTERNS, limit)


def extract_decisions(lines: list[str], limit: int = 10) -> list[tuple[str, float]]:
    return _pick(lines, DECISION_PATTERNS, limit)


def extract_tasks(lines: list[str], limit: int = 10) -> list[tuple[str, float]]:
    return _pick(lines, TASK_PATTERNS, limit)


def extract_ideas(lines: list[str], limit: int = 10) -> list[tuple[str, float]]:
    return _pick(lines, IDEA_PATTERNS, limit)


def extract_people(text: str, limit: int = 12) -> list[tuple[str, float]]:
    counts: dict[str, int] = {}
    for name in PEOPLE_RE.findall(text):
        if name in PEOPLE_BLOCKED or len(name) > 50:
            continue
        counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [(name, min(_MAX_CONFIDENCE, 0.5 + 0.1 * count)) for name, count in ranked]


def _extract_files(text: str, extensions: set[str], limit: int) -> list[tuple[str, float]]:
    seen: list[str] = []
    for match in FILE_RE.finditer(text):
        filename = match.group(0)
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext in extensions and filename not in seen:
            seen.append(filename)
            if len(seen) >= limit:
                break
    return [(f, _FILE_CONFIDENCE) for f in seen]


def extract_documents(text: str, limit: int = 20) -> list[tuple[str, float]]:
    return _extract_files(text, DOCUMENT_EXTENSIONS, limit)


def extract_assets(text: str, limit: int = 20) -> list[tuple[str, float]]:
    return _extract_files(text, ASSET_EXTENSIONS, limit)


def extract_all(content: list[dict]) -> dict[str, list[tuple[str, float]]]:
    """Run every extractor for one conversation's content. Returns a dict
    keyed by the seven supported object types."""
    lines = lines_from_content(content)
    text = full_text(content)
    return {
        "Project": extract_projects(lines),
        "Person": extract_people(text),
        "Task": extract_tasks(lines),
        "Decision": extract_decisions(lines),
        "Idea": extract_ideas(lines),
        "Document": extract_documents(text),
        "Asset": extract_assets(text),
    }
