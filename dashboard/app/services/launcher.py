"""AI Launcher service (ROLE OS v1.2).

Reduces starting an AI-assisted work session to one click: assembles the
session-initialization prompt from data already owned by the Daily
Session domain (`app.session`) and the ecosystem decisions adapter, and
tells the caller which URL(s) to open for the chosen AI tool.

This module owns no persistence of its own -- it only reads. It also
never touches the clipboard, the browser, or any OS-level automation
itself: per v1.2's explicit scope, copying the prompt and opening the
target site(s) happen client-side, in the browser tab the dashboard is
already running in (see `static/js/app.js`'s `wireAiLauncher`). No
Playwright, no typing automation, nothing beyond returning text and URLs.
"""

from __future__ import annotations

from typing import Any

AI_TOOL_URLS: dict[str, tuple[str, ...]] = {
    "claude": ("https://claude.ai",),
    "chatgpt": ("https://chatgpt.com",),
}
AI_TOOL_URLS["both"] = AI_TOOL_URLS["claude"] + AI_TOOL_URLS["chatgpt"]

VALID_TOOLS = tuple(AI_TOOL_URLS.keys())


def resolve_launch_urls(tool: str) -> list[str]:
    """Returns the URL(s) to open for a given tool ('claude', 'chatgpt',
    or 'both'). Raises `ValueError` for anything else."""
    try:
        return list(AI_TOOL_URLS[tool])
    except KeyError:
        raise ValueError(
            f"Unknown AI tool '{tool}'. Expected one of: {', '.join(VALID_TOOLS)}"
        ) from None


def _pending_tasks_block(registry_project: dict[str, Any] | None) -> str:
    if not registry_project:
        return "(none recorded -- session has no linked project)"

    lines = []
    milestone = (registry_project.get("milestone") or "").strip()
    next_action = (registry_project.get("next_action") or "").strip()
    if milestone:
        lines.append(f"- Current milestone: {milestone}")
    if next_action:
        lines.append(f"- Next action: {next_action}")

    return "\n".join(lines) if lines else "(none recorded)"


def _recent_decisions_block(decisions: list[dict[str, Any]]) -> str:
    if not decisions:
        return "(none available)"
    return "\n".join(f"- {d['id']} ({d['date']}): {d['decision']}" for d in decisions)


def build_launch_prompt(
    *,
    session: dict[str, Any],
    registry_project: dict[str, Any] | None,
    decisions: list[dict[str, Any]],
) -> str:
    """Builds the AI Launcher's session-initialization prompt from the
    active session, its linked project registry entry (if any), and
    recent ecosystem decisions. Pure string templating -- no AI/LLM call,
    consistent with every other prompt/record generator in this domain
    (see `app.session.markdown`).
    """
    return f"""Initialize using SYSTEM.md.

ROLE OS Session

Mode:
{session['mode']}

Project:
{session['project_name']}

Today's Objective:
{session['objective']}

Pending Tasks:
{_pending_tasks_block(registry_project)}

Recent Decisions:
{_recent_decisions_block(decisions)}

Read only the documentation required for this mode and project.

At the beginning of the session:

1. Summarize current project status.
2. Identify the highest-impact next milestone.
3. List blockers.
4. Confirm the specific deliverable for this session.
5. Wait for approval before making destructive or architectural changes."""
