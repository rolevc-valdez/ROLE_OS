"""Conversation transport (ROLE OS v1.4 Context Engine; Sprint C7.1: the
prompt-building half of this module moved to `app.project_memory.prompt`
-- "Project Memory owns the prompt, the AI Session never does"). This
module now only resolves *where* to open a conversation, never *what* to
say in it. Pure lookup over data already owned by `app.projects.db` -- no
AI/LLM call, no persistence of its own, no OS-level action (opening the
saved `conversation_url` happens client-side in `static/js/app.js`, the
same pattern as the v1.2 AI Launcher and the v1.3 AI Workspace).
"""

from __future__ import annotations

from typing import Any

# Sprint 5 (Project Unification): shared with `resolve_conversation_url`
# below -- moved here from `app.routers.pi.ai_sessions`'s private
# `_resolve_open` so `app.workspace.resume`'s "Resume Work" orchestration
# (§3 of the brief) can reuse the exact same resolution logic instead of
# duplicating the assistant-homepage table. `ai_sessions.py`'s own
# `/open` and `/resume` endpoints now call this function too -- same
# inputs, same outputs, zero behavior change (see its docstring history).
ASSISTANT_HOMEPAGES = {
    "claude": "https://claude.ai",
    "chatgpt": "https://chatgpt.com",
    "gemini": "https://gemini.google.com",
}


def resolve_conversation_url(session: dict[str, Any]) -> tuple[str | None, bool, str | None]:
    """Returns (url, used_saved_conversation, message)."""
    saved_url = (session.get("conversation_url") or "").strip()
    if saved_url:
        return saved_url, True, None

    homepage = ASSISTANT_HOMEPAGES.get(session["assistant"])
    if homepage:
        return homepage, False, "No conversation saved yet."

    return (
        None,
        False,
        "No conversation saved yet. No homepage is known for the 'other' assistant type.",
    )
