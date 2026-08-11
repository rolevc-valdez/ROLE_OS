"""Conversation selection: given every AI Session already tied to a
project, pick the one Resume Work should reopen -- and say why, so the
choice is never a silent implementation detail.

`AISession` (`app.projects.models`) has no separate "pinned" field from
`favorite`, and no per-project "preferred assistant/session" setting
distinct from `current` (see Sprint C7.1's investigation) -- so this
module's four tiers map onto the real schema as follows, documented here
rather than left implicit:

1. latest active  -- `status == "active"`, most recently used
2. pinned         -- `favorite == True` (the only "pin"-like flag that
                      exists; there is deliberately no second concept
                      invented for this)
3. preferred      -- `current == True` (a session a user or a prior Resume
                      Work explicitly marked as "the" session for its
                      assistant -- the closest existing concept to a
                      per-project "preferred" session)
4. newest         -- most recent `started_at`, the fallback when nothing
                      above matches

`list_ai_sessions` already returns every session for a project (its own
ORDER BY doesn't matter here -- this module does its own filtering/sorting
regardless of input order).
"""

from __future__ import annotations

from typing import Any


def select_best_session(
    sessions: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    """Returns `(session_or_None, reason)`. `reason` is a short, always-
    present, human-readable explanation of why that session (or none) was
    chosen -- never a silent decision."""
    if not sessions:
        return None, "no existing AI session for this project"

    active = [s for s in sessions if (s.get("status") or "").lower() == "active"]
    if active:
        active.sort(key=lambda s: s.get("last_used_at") or "", reverse=True)
        return active[0], "latest active session"

    pinned = [s for s in sessions if s.get("favorite")]
    if pinned:
        pinned.sort(key=lambda s: s.get("last_used_at") or s.get("started_at") or "", reverse=True)
        return pinned[0], "pinned (favorited) session"

    preferred = [s for s in sessions if s.get("current")]
    if preferred:
        return preferred[0], "previously preferred (marked current) session"

    newest = sorted(sessions, key=lambda s: s.get("started_at") or "", reverse=True)
    return newest[0], "newest session (no active, pinned, or preferred session found)"
