"""Workspace-wide evidence the two existing rule packs never compute:
Knowledge freshness (new) and Discovery freshness (already computed by
`workspace.service.get_freshness`, just not previously turned into an
actionable recommendation -- see `rules.py`).

Per-project evidence (health, git, snapshots, next action, roadmap/TODO
presence, commercial readiness, business priority, dependencies,
capabilities, assets, documentation, recent activity) is deliberately NOT
re-derived here -- it already exists, computed once, on the enriched
Workspace item (`workspace.service.enrich_project_item`) and the PI
`RuleContext` (`app.advisor.engine._build_context`). This module only adds
the two evidence dimensions genuinely missing from both.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings

# Conversation imports are a manual, infrequent action (a user exporting
# and re-importing ChatGPT history), not a continuous background process
# like a git commit -- so "stale" here means a much longer window than
# Discovery's 24-hour scan threshold. 30 days is a deliberate, documented
# choice: long enough that a normal multi-week gap between imports isn't
# flagged, short enough that "the Knowledge Graph hasn't seen a new
# conversation in over a month" is still a meaningful signal.
KNOWLEDGE_STALE_DAYS = 30


def knowledge_freshness(settings: Settings | None = None) -> dict[str, Any]:
    """Mirrors the shape of `workspace.service.get_freshness()` deliberately
    (`last_*`/`hours_since_*`/`is_stale`) so the two freshness signals read
    the same way wherever they're displayed together."""
    settings = settings or get_settings()
    last_import: str | None = None
    try:
        from app.imports import db as imports_db

        runs = imports_db.list_runs(settings=settings, limit=1)
        if runs:
            last_import = runs[0].get("completed_at") or runs[0].get("started_at")
    except Exception:
        # The imports domain's own SQLite file may not exist yet on a fresh
        # install -- an honest "no import on record" (is_stale=True), never
        # a crash, matches how `workspace.service.get_freshness` treats a
        # missing scan.
        last_import = None

    hours_since_import: float | None = None
    is_stale = True
    if last_import:
        try:
            dt = datetime.fromisoformat(last_import.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours_since_import = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
            is_stale = hours_since_import > (KNOWLEDGE_STALE_DAYS * 24)
        except ValueError:
            hours_since_import = None

    return {
        "last_import": last_import,
        "hours_since_import": (
            round(hours_since_import, 1) if hours_since_import is not None else None
        ),
        "stale_threshold_days": KNOWLEDGE_STALE_DAYS,
        "is_stale": is_stale,
    }
