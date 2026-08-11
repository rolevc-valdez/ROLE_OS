"""Session naming (Sprint C7.1): every AI Session Resume Work creates (or
retitles, if it inherited a generic name) is named `<Project Name> --
<Objective>`, e.g. "ROLE Commerce Factory -- Shopify Adapter" -- never a
placeholder like "Resume Work", "Untitled", or "Session 1".
"""

from __future__ import annotations

_DISALLOWED_TITLES = {"", "resume work", "untitled", "untitled session", "session 1"}
_MAX_OBJECTIVE_CHARS = 80


def needs_retitle(title: str | None) -> bool:
    return (title or "").strip().lower() in _DISALLOWED_TITLES


def session_title_for(project_name: str, objective: str) -> str:
    objective = (objective or "").strip() or "Continue this project"
    if len(objective) > _MAX_OBJECTIVE_CHARS:
        objective = objective[: _MAX_OBJECTIVE_CHARS - 1].rstrip() + "…"
    return f"{project_name} — {objective}"
