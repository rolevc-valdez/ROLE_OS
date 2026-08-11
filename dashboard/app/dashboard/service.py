"""Dashboard 2.0 (Sprint C2): the executive dashboard's summary builder.

The legacy Dashboard page showed `/import/metrics` -- Explorer's own counts
of *extracted knowledge objects* (Project/Person/Task/Decision/Idea/
Document/Asset entities pulled out of imported ChatGPT conversations).
Those numbers are honestly zero when no conversations have been imported,
even though the real workspace already has adopted projects, commits,
sessions, and recommendations. This module answers the five questions the
sprint brief poses (what's active / what needs attention / what changed /
what should I continue / how healthy is the portfolio) from the data that
actually describes those things: `ProjectContext`, `workspace.service`,
`workspace.advisor`/`workspace.portfolio`, and (for the one piece that is
genuinely a different domain) `app.db`'s Knowledge counts.

This is a *composition* layer, not a new aggregation engine: every number
below is produced by calling an existing function exactly once and
counting/grouping its output -- nothing here re-derives health, next
action, resume availability, or recommendation priority (see each
function's docstring for which existing service it delegates to).
"""

from __future__ import annotations

from typing import Any

from app import db as knowledge_db
from app.assets.service import request_scope as _assets_request_scope
from app.config import Settings, get_settings
from app.db import DatabaseUnavailableError
from app.project_context.builder import all_project_contexts as _all_project_contexts
from app.workspace import advisor as workspace_advisor
from app.workspace import service as workspace_service

RECENT_ACTIVITY_LIMIT = 30
RECENT_ASSETS_LIMIT = 12
RECENT_KNOWLEDGE_LIMIT = 8


def _executive_summary_cards(
    all_contexts: list[dict[str, Any]],
    *,
    home: dict[str, Any],
    knowledge_total: int,
    reusable_assets_count: int,
    recent_commits_count: int,
    recent_snapshot_events: int,
) -> dict[str, Any]:
    """Every count here is a plain `sum`/`len` over data another service
    already computed (see caller) -- no independent scoring."""
    healthy = sum(1 for c in all_contexts if c["health"] == "healthy")
    warning = sum(1 for c in all_contexts if c["health"] == "warning")
    critical = sum(1 for c in all_contexts if c["health"] == "critical")
    dirty = sum(1 for c in all_contexts if (c.get("git") or {}).get("is_dirty"))
    with_next_action = sum(1 for c in all_contexts if (c.get("next_action") or {}).get("text"))
    active_sessions = sum(
        1 for c in all_contexts if (c.get("latest_ai_session") or {}).get("status") == "active"
    )

    return {
        "adopted_projects": len(all_contexts),
        "healthy_projects": healthy,
        "warning_projects": warning,
        "critical_projects": critical,
        "projects_needing_attention": len(home.get("projects_needing_attention") or []),
        "dirty_repositories": dirty,
        "projects_with_next_action": with_next_action,
        "active_ai_sessions": active_sessions,
        "recent_snapshots": recent_snapshot_events,
        "reusable_assets": reusable_assets_count,
        "knowledge_cards": knowledge_total,
        "recent_commits": recent_commits_count,
    }


def _portfolio_status(
    all_contexts: list[dict[str, Any]], enriched_items: list[dict[str, Any]]
) -> dict[str, Any]:
    """Groups (not a strict partition -- a project can be both "healthy"
    and "active"). Active/Inactive reuses `workspace.advisor`'s own
    `last_activity_age_days`/`INACTIVE_DAYS_THRESHOLD` (the same threshold
    `rule_inactive` already uses); Launch-ready reuses `rule_near_
    completion` directly -- a project is launch-ready here exactly when
    that existing rule would recommend shipping it, never a new heuristic.
    Manual (non-discovered) projects have no discovery evidence for
    activity-age/launch-readiness and are honestly left out of those two
    groups rather than guessed at."""

    def _ref(c: dict[str, Any]) -> dict[str, Any]:
        return {"id": c["id"], "display_name": c["display_name"], "item_id": c.get("item_id")}

    healthy = [_ref(c) for c in all_contexts if c["health"] == "healthy"]
    warning = [_ref(c) for c in all_contexts if c["health"] == "warning"]
    critical = [_ref(c) for c in all_contexts if c["health"] == "critical"]

    contexts_by_item_id = {c["item_id"]: c for c in all_contexts if c.get("item_id")}
    active, inactive, launch_ready = [], [], []
    for item in enriched_items:
        context = contexts_by_item_id.get(item["id"])
        if context is None:
            continue
        age = workspace_advisor.last_activity_age_days(item)
        if age is not None and age > workspace_advisor.INACTIVE_DAYS_THRESHOLD:
            inactive.append(_ref(context))
        else:
            active.append(_ref(context))
        if workspace_advisor.rule_near_completion(item) is not None:
            launch_ready.append(_ref(context))

    return {
        "healthy": healthy,
        "warning": warning,
        "critical": critical,
        "active": active,
        "inactive": inactive,
        "launch_ready": launch_ready,
    }


def _continue_work(
    home: dict[str, Any], all_contexts: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Reuses `workspace.portfolio.suggested_project_to_continue` (already
    computed inside `get_home_portfolio`, called once) -- no new scorer.
    Embeds the canonical `ProjectContext` for that project so the frontend
    never re-derives next_action/resume_state/latest_activity itself."""
    suggested = home.get("suggested_project")
    if not suggested:
        return None
    project = suggested["project"]
    contexts_by_item_id = {c["item_id"]: c for c in all_contexts if c.get("item_id")}
    context = contexts_by_item_id.get(project["id"])
    return {
        "project_context": context,
        "reasons": suggested.get("reasons") or [],
        "score": suggested.get("score"),
    }


def _needs_attention(
    enriched_items: list[dict[str, Any]], all_contexts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reuses `workspace_advisor.generate_recommendations` verbatim (the
    same rule set Workspace's own `/workspace/advisor` endpoint runs,
    including the one new rule this sprint added, `rule_snapshot_blocker`)
    -- this function performs no scoring of its own, only embeds each
    recommendation's canonical `project_context` so every item links to
    the canonical project identity, per the brief's requirement."""
    recs = workspace_advisor.generate_recommendations(enriched_items)
    contexts_by_item_id = {c["item_id"]: c for c in all_contexts if c.get("item_id")}
    for rec in recs:
        rec["project_context"] = contexts_by_item_id.get(rec["project_id"])
    return recs


def build_dashboard_summary(settings: Settings | None = None) -> dict[str, Any]:
    """The one Dashboard 2.0 endpoint's entire payload -- already shaped,
    so the frontend performs no cross-source joining and no recomputation
    of health/next-action/recommendation-priority/resume-availability/
    project-status (all of that is embedded, canonical, per project)."""
    settings = settings or get_settings()

    # Sprint C5 §12: every call below can independently walk each adopted
    # project's filesystem for its assets (`_all_project_contexts` via each
    # context's `assets_count`, then `list_activity_feed` and
    # `list_project_assets` again). `request_scope()` memoizes that walk by
    # root path for the duration of this one request, so the underlying
    # filesystem is only ever scanned once per project per request.
    with _assets_request_scope():
        all_contexts, enriched_items = _all_project_contexts(settings=settings)
        home = workspace_service.get_home_portfolio(settings=settings)
        freshness = workspace_service.get_freshness(settings=settings)

        recent_activity = workspace_service.list_activity_feed(
            limit=RECENT_ACTIVITY_LIMIT, settings=settings
        )
        recent_commits_count = sum(1 for e in recent_activity if e["type"] == "git_commit")
        recent_snapshot_events = sum(1 for e in recent_activity if e["type"] == "ai_snapshot")

        assets_by_project = workspace_service.list_project_assets(
            settings=settings, adopted_only=True
        )
        all_assets = [a for assets in assets_by_project.values() for a in assets]
        all_assets.sort(key=lambda a: a["modified_at"], reverse=True)
        reusable_assets = [a for a in all_assets if a.get("reusable")]

    # Knowledge is a genuinely separate domain (imported ChatGPT
    # conversations, a different SQLite file) -- its database may not be
    # configured/present at all yet. That is an honest "Knowledge has not
    # been imported" empty state (§11), not a reason to fail the whole
    # Dashboard.
    try:
        knowledge_rows = knowledge_db.list_projects(settings=settings)
        knowledge_total = sum(row["count"] for row in knowledge_rows)
        recent_knowledge = knowledge_db.recent_cards(
            settings=settings, limit=RECENT_KNOWLEDGE_LIMIT
        )
    except DatabaseUnavailableError:
        knowledge_total = 0
        recent_knowledge = []

    return {
        "cards": _executive_summary_cards(
            all_contexts,
            home=home,
            knowledge_total=knowledge_total,
            reusable_assets_count=len(reusable_assets),
            recent_commits_count=recent_commits_count,
            recent_snapshot_events=recent_snapshot_events,
        ),
        "portfolio_status": _portfolio_status(all_contexts, enriched_items),
        "continue_work": _continue_work(home, all_contexts),
        "needs_attention": _needs_attention(enriched_items, all_contexts),
        "recent_activity": recent_activity[:RECENT_ACTIVITY_LIMIT],
        "recent_assets": all_assets[:RECENT_ASSETS_LIMIT],
        "recent_knowledge": {
            "total_count": knowledge_total,
            "recent_cards": recent_knowledge,
        },
        "data_freshness": freshness,
        "total_projects_tracked": len(all_contexts),
    }
