"""Context Package (hotfix following real-world Resume Work validation).

Real dogfooding showed the flaw: `relevant_resources` was a bounded list
of *absolute Windows paths*. That is provenance, not context -- a fresh
Claude web conversation has no filesystem access and correctly refused to
"read" them. This module is what actually fixes that: it reads the
adopted project's own supported text files itself, and returns bounded,
redacted, deterministic excerpts of their real content for the Resume
Prompt to embed. Local paths remain metadata only from here on.

No LLM, no embeddings -- plain bounded reads, regex heading extraction
(same discipline as `app.project_memory.summary`), and a fixed character
budget, all deterministic and explainable.

Security: reuses `app.discovery.boundary.exclusions.is_excluded` (the
same exclusion rules Discovery's own scanner trusts) plus its own
`.env`/binary/path-traversal checks and a secret-redaction pass -- never
embeds credentials, and never reads outside the adopted project root.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.discovery.boundary.exclusions import is_excluded

# ---------------------------------------------------------------------------
# Budget (§4 of the brief) -- configurable, sane defaults.
# ---------------------------------------------------------------------------
MAX_RESOURCES = 8
MAX_CHARS_PER_RESOURCE = 2_000
MAX_TOTAL_CHARS = 12_000
_MAX_READ_BYTES = 200_000

# ---------------------------------------------------------------------------
# Supported resources (§2) -- the named project documents below, selected
# by extraction priority (never every Markdown file in the repo -- "do
# not dump every file"). Explicitly never binaries, databases, images,
# video, .env files, or generated dependency trees (enforced in
# `_is_safe_to_embed` below, reusing Discovery's own exclusion config for
# the dependency-tree/build-output part of that list).
# ---------------------------------------------------------------------------
_ENV_FILE_RE = re.compile(r"^\.env(\..+)?$", re.IGNORECASE)

_EXCERPT_REASONS: dict[str, str] = {
    "README.md": "Defines the project and its purpose.",
    "SYSTEM.md": "Defines the system architecture.",
    "ARCHITECTURE.md": "Defines the system architecture.",
    "PROJECT.md": "Defines the project's identity and scope.",
    "PRD.md": "Defines the product requirements relevant to the task.",
    "ROADMAP.md": "Defines the current milestone or phase.",
    "NEXT_ACTION.md": "Defines the immediate next action.",
    "TODO.md": "Lists outstanding work items.",
    "CHANGELOG.md": "Shows the most recent (Unreleased) changes.",
    "DECISION_LOG.md": "Records prior decisions relevant to this work.",
}

# ---------------------------------------------------------------------------
# Extraction priority (§3) -- selected by the requested action's own
# wording, never by dumping every file.
# ---------------------------------------------------------------------------
_STATUS_PRIORITY = (
    "README.md",
    "ROADMAP.md",
    "TODO.md",
    "NEXT_ACTION.md",
    "CHANGELOG.md",
    "DECISION_LOG.md",
)
_ARCHITECTURE_PRIORITY = (
    "SYSTEM.md",
    "ARCHITECTURE.md",
    "DECISION_LOG.md",
    "README.md",
)
_IMPLEMENTATION_PRIORITY = (
    "PRD.md",
    "ARCHITECTURE.md",
    "SYSTEM.md",
    "README.md",
    "TODO.md",
    "NEXT_ACTION.md",
)

_ARCHITECTURE_KEYWORDS = (
    "architecture",
    "system design",
    "redesign",
    "restructure the",
)
_IMPLEMENTATION_VERB_RE = re.compile(
    r"\b(implement|fix|add|build|wire|write|create|refactor|migrate|deploy|update)\b",
    re.IGNORECASE,
)


def _priority_for(requested_action: str | None) -> tuple[str, ...]:
    text = (requested_action or "").lower()
    if any(keyword in text for keyword in _ARCHITECTURE_KEYWORDS):
        return _ARCHITECTURE_PRIORITY
    if _IMPLEMENTATION_VERB_RE.search(text):
        return _IMPLEMENTATION_PRIORITY
    return _STATUS_PRIORITY


# ---------------------------------------------------------------------------
# Secret redaction (§8) -- extends Project Memory's existing "never
# invent, never leak" discipline to "never embed a credential either".
# ---------------------------------------------------------------------------
_SECRET_PATTERNS: tuple[re.Pattern, ...] = (
    # key/value style: API_KEY=..., "password": "...", token: '...'
    re.compile(
        r"(?im)^([ \t]*[\w.\-]*(?:api[_-]?key|secret|token|password|passwd|access[_-]?key)"
        r"[\w.\-]*\s*[:=]\s*)(['\"]?)([A-Za-z0-9\-_/+.=]{6,})(\2)"
    ),
    # OpenAI/Anthropic-style bearer secrets
    re.compile(r"\b(sk|rk|ak)-[A-Za-z0-9]{16,}\b"),
    # AWS access key ids
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Shopify tokens / recovery-code style secrets
    re.compile(r"\bshp(at|ca|pa|ss)_[A-Za-z0-9]{20,}\b", re.IGNORECASE),
    # PEM private keys
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    # connection strings carrying inline credentials
    re.compile(r"(?i)\b\w+://[^\s:/@]+:[^\s@]+@[^\s]+"),
)


def _redact(text: str) -> tuple[str, bool]:
    redacted = False

    def _replace(match: re.Match) -> str:
        nonlocal redacted
        redacted = True
        groups = match.groups()
        if len(groups) >= 3:
            # key/value pattern: keep the key, redact only the value
            return f"{groups[0]}[REDACTED]{groups[-1] if groups[-1] else ''}"
        return "[REDACTED]"

    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_replace, text)
    return text, redacted


# ---------------------------------------------------------------------------
# File discovery / safety
# ---------------------------------------------------------------------------


def _find_case_insensitive(root: Path, name: str) -> Path | None:
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower() == name.lower():
                return entry
    except OSError:
        return None
    return None


def _looks_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(2048)
    except OSError:
        return True
    return b"\x00" in chunk


def _is_safe_to_embed(path: Path, root: Path) -> tuple[bool, str | None]:
    """Path-traversal/symlink-escape guard (§8): the resolved file must
    stay inside the resolved adopted root. Then Discovery's own exclusion
    config (dependency trees, build output, etc.), then `.env`, then a
    binary sniff -- in that order, cheapest checks first."""
    try:
        resolved = path.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
    except OSError:
        return False, "unresolvable path"
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return False, "outside adopted project root"
    if _ENV_FILE_RE.match(resolved.name):
        return False, "environment file excluded"
    excluded, reason = is_excluded(resolved, resolved_root)
    if excluded:
        return False, reason
    if _looks_binary(resolved):
        return False, "binary file excluded"
    return True, None


def _read_text(path: Path) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(_MAX_READ_BYTES)
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Bounded heading/section extraction -- same discipline as
# `app.project_memory.summary`, generalized to keep whole sections (not
# just the first paragraph) so a real excerpt can be embedded.
# ---------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^(#+)\s*(.+?)\s*$", re.MULTILINE)


def _sections(text: str) -> list[tuple[str | None, str]]:
    headings = list(_HEADING_RE.finditer(text))
    if not headings:
        return [(None, text.strip())]
    sections: list[tuple[str | None, str]] = []
    for index, match in enumerate(headings):
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections.append((match.group(2).strip(), text[start:end].strip()))
    return sections


def _pick_section(
    sections: list[tuple[str | None, str]], keywords: tuple[str, ...]
) -> tuple[str, str] | None:
    for heading, body in sections:
        if heading and body and any(keyword in heading.lower() for keyword in keywords):
            return heading, body
    return None


def _select_excerpt(filename: str, text: str) -> tuple[str | None, str]:
    """Deterministic section selection: file-specific preferred heading
    first (e.g. CHANGELOG's "Unreleased", ROADMAP's current phase),
    falling back to an "overview"-style heading, then the first section
    with real content, then the whole (stripped) text."""
    sections = _sections(text)
    name_lower = filename.lower()

    if name_lower == "changelog.md":
        picked = _pick_section(sections, ("unreleased",))
        if picked:
            return picked

    if name_lower == "roadmap.md":
        picked = _pick_section(sections, ("current", "phase", "milestone", "active"))
        if picked:
            return picked

    picked = _pick_section(sections, ("overview", "purpose", "about", "what"))
    if picked:
        return picked

    for heading, body in sections:
        if body:
            return heading, body

    return None, text.strip()


_TRUNCATION_SUFFIX = " …"


def _truncate(text: str, limit: int) -> tuple[str, int]:
    """Deterministic, sentence/line-boundary-preserving truncation --
    never a mid-word cut when a reasonable boundary exists. The result
    (including the truncation suffix) never exceeds `limit` characters."""
    if limit <= 0:
        return "", len(text)
    if len(text) <= limit:
        return text, 0
    budget = max(0, limit - len(_TRUNCATION_SUFFIX))
    cut = text[:budget]
    last_period = cut.rfind(". ")
    last_newline = cut.rfind("\n")
    boundary = max(last_period, last_newline)
    if boundary > budget * 0.5:
        cut = cut[: boundary + 1]
    omitted = len(text) - len(cut)
    return cut.rstrip() + _TRUNCATION_SUFFIX, omitted


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _empty_package(missing: str, *, context_sufficient: bool = False) -> dict[str, Any]:
    return {
        "resources": [],
        "context_sufficient": context_sufficient,
        "missing_context": [missing],
        "embedded_resource_count": 0,
        "embedded_character_count": 0,
    }


def build_context_package(
    root_path: str | None,
    requested_action: str | None,
    requested_action_source: str | None,
    *,
    max_resources: int = MAX_RESOURCES,
    max_chars_per_resource: int = MAX_CHARS_PER_RESOURCE,
    max_total_chars: int = MAX_TOTAL_CHARS,
) -> dict[str, Any]:
    """The one Context Package builder. Returns
    `{resources, context_sufficient, missing_context,
    embedded_resource_count, embedded_character_count}`.

    `resources` is a bounded list of dicts (§1): `resource_name`,
    `relative_path`, `resource_type`, `modified_at`, `selected_heading`,
    `excerpt`, `excerpt_reason`, `omitted_character_count`,
    `sensitive_content_redacted`. Deterministic, no LLM/embeddings."""
    if not root_path:
        # No filesystem-backed project root at all (e.g. a Project row
        # created without adopting a folder) -- there is nothing local to
        # embed, but that's not a failure the guard should block on; it's
        # simply out of scope for this project.
        return _empty_package("no project root path configured", context_sufficient=True)

    root = Path(root_path)
    if not root.is_dir():
        return _empty_package(f"project root not found: {root_path}")

    priority = list(_priority_for(requested_action))

    if requested_action_source and (
        "/" in requested_action_source or "\\" in requested_action_source
    ):
        source_name = Path(requested_action_source).name
        if source_name not in priority:
            priority.insert(0, source_name)

    resources: list[dict[str, Any]] = []
    missing_context: list[str] = []
    total_chars = 0
    seen_names: set[str] = set()

    for filename in priority:
        if len(resources) >= max_resources or total_chars >= max_total_chars:
            break
        if filename.lower() in seen_names:
            continue
        path = _find_case_insensitive(root, filename)
        if not path:
            continue
        seen_names.add(filename.lower())

        safe, reason = _is_safe_to_embed(path, root)
        if not safe:
            missing_context.append(f"{filename} excluded ({reason})")
            continue

        text = _read_text(path)
        if not text or not text.strip():
            continue

        heading, body = _select_excerpt(filename, text)
        redacted_body, was_redacted = _redact(body)

        remaining_budget = max(0, min(max_chars_per_resource, max_total_chars - total_chars))
        if remaining_budget <= 0:
            missing_context.append(f"{filename} omitted (context budget exhausted)")
            break

        excerpt, omitted = _truncate(redacted_body, remaining_budget)
        try:
            relative_path = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            relative_path = path.name

        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            modified_at = None

        resources.append(
            {
                "resource_name": path.name,
                "relative_path": relative_path,
                "resource_type": "markdown",
                "modified_at": modified_at,
                "selected_heading": heading,
                "excerpt": excerpt,
                "excerpt_reason": _EXCERPT_REASONS.get(
                    path.name, "Relevant to the requested action."
                ),
                "omitted_character_count": omitted,
                "sensitive_content_redacted": was_redacted,
            }
        )
        total_chars += len(excerpt)

    embedded_resource_count = len(resources)
    embedded_character_count = total_chars
    context_sufficient = embedded_resource_count > 0
    if not context_sufficient:
        missing_context.append("no supported project documentation found under the adopted root")

    return {
        "resources": resources,
        "context_sufficient": context_sufficient,
        "missing_context": missing_context,
        "embedded_resource_count": embedded_resource_count,
        "embedded_character_count": embedded_character_count,
    }
