"""Mission Control (Sprint C5): builds the single `GET /mission-control`
payload.

Product brief: within 10 seconds of opening ROLE OS, answer "what should I
work on today, where did I leave off, what changed, what needs attention,
and what's closest to producing real value" -- as one decision-and-
continuation screen, not a second Dashboard.

This module is pure composition. Every section below delegates to an
existing service exactly once per request:

- `app.project_context.builder.all_project_contexts` -- the one canonical
  "every tracked project" list (health, next_action, resume_state,
  latest_snapshot/session, advisor_summary already embedded).
- `app.workspace.service.get_home_portfolio` -- Home's existing ranking
  (`suggested_project_to_continue`), reused verbatim as the Primary Focus
  card's recommendation.
- `app.operational_intelligence.get_operational_intelligence` (Sprint C6) --
  the one canonical Operational Intelligence Engine; Today's Focus, Needs
  Attention, Value Signal, and the Daily Session suggestion's objective/
  expected-result text are four different *views* over its already-
  normalized, already-deduped, already-sorted output, never a second
  scoring engine of Mission Control's own.
- `app.workspace.service.list_activity_feed` -- Recent Activity and the
  "since last time" baseline filter both read this one feed.
- `app.session.db` -- the existing Daily Session domain (`get_active_
  session`/`list_sessions`), read as-is; Mission Control does not
  reimplement Start/End My Day, only surfaces the current state and links
  to `/session`.

No new score, no new "every project" definition, no second filesystem walk
beyond what `app.assets.service.request_scope()` already collapses into one
walk per project for the whole request (see `build_mission_control`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.assets.service import request_scope
from app.config import Settings, get_settings
from app.executive_decision import get_executive_decision
from app.operational_intelligence import get_operational_intelligence
from app.project_context.builder import all_project_contexts as _all_project_contexts
from app.session import db as session_db
from app.session.modes import list_modes
from app.workspace import service as workspace_service

TODAYS_FOCUS_LIMIT = 3
NEEDS_ATTENTION_LIMIT = 8
RECENT_ACTIVITY_LIMIT = 20
SINCE_LAST_TIME_LIMIT = 20
SINCE_LAST_TIME_FEED_LIMIT = 100
FALLBACK_WINDOW_HOURS = 24
LAUNCH_RECOMMENDATION_TITLE = "Consider shipping/launching"

# Recent Activity's own `filesystem_modified` events (a folder's mtime
# changed, no other signal) are explicitly out of scope for "Since Last
# Time" -- the brief calls this out as noise to avoid, not a change worth
# surfacing.
_NOISE_EVENT_TYPES = frozenset({"filesystem_modified"})


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _context_lookup(all_contexts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {c["item_id"]: c for c in all_contexts if c.get("item_id")}


def _primary_focus(
    home: dict[str, Any],
    contexts_by_item_id: dict[str, dict[str, Any]],
    all_contexts: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """The one dominant card (§1). Reuses `workspace.portfolio.suggested_
    project_to_continue`'s output (already computed once inside `home`) --
    no independent scoring. An honest empty state, with the best available
    action, when nothing can be recommended (no adopted project has both a
    next action and evidence to rank it)."""
    suggested = home.get("suggested_project")
    if not suggested:
        if not all_contexts:
            return {
                "available": False,
                "message": "No projects tracked yet.",
                "best_action": {"label": "Rescan Workspace", "action": "rescan_workspace"},
            }
        return {
            "available": False,
            "message": "No project currently has both a clear next action and enough "
            "evidence to recommend -- review a project below to set one.",
            "best_action": {"label": "Open Explorer", "action_link": "#/explorer"},
        }

    project = suggested["project"]
    context = contexts_by_item_id.get(project["id"])
    return {
        "available": True,
        "project_context": context,
        "reasons": suggested.get("reasons") or [],
        "score": suggested.get("score"),
    }


def _project_key(rec: dict[str, Any]) -> str:
    project = rec.get("project")
    if not project:
        return "__workspace__"
    return project.get("canonical_project_id") or project.get("item_id") or "__workspace__"


def _dedupe_recs_by_project(recs: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    """One recommendation per project (or one workspace-wide item), highest
    priority first -- `recs` is already sorted desc by (priority,
    confidence) (the Operational Intelligence Engine's own contract, see
    `app.operational_intelligence.engine`'s "Conflict resolution" section),
    so a first-seen-wins pass here is enough; nothing here re-scores or
    re-ranks."""
    seen: set[str] = set()
    result = []
    for rec in recs:
        key = _project_key(rec)
        if key in seen:
            continue
        seen.add(key)
        result.append(rec)
        if len(result) >= limit:
            break
    return result


def _focus_item(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": rec["project"],
        "action": rec["recommendation"],
        "reason": rec["reason"],
        "evidence": rec["evidence"],
        "priority": rec["priority"],
        "confidence": rec["confidence"],
        "expected_benefit": rec["expected_benefit"],
        "action_link": rec["action_link"],
    }


def _severity_for_priority(priority: int) -> str:
    if priority >= 70:
        return "critical"
    if priority >= 40:
        return "warning"
    return "info"


def _todays_focus(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    top = _dedupe_recs_by_project(recommendations, limit=TODAYS_FOCUS_LIMIT)
    return [_focus_item(rec) for rec in top]


def _needs_attention(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """§4: unresolved issues, most severe first -- a wider, differently-
    limited slice of the same Operational Intelligence output Today's Focus
    draws from. A stale Discovery scan (previously hand-appended here) is
    now just another recommendation the engine itself produces
    (`rule_discovery_scan_stale`, `project=None`) -- no special-casing
    needed anymore."""
    top = _dedupe_recs_by_project(recommendations, limit=NEEDS_ATTENTION_LIMIT)
    items = [
        {
            "project": rec["project"],
            "severity": _severity_for_priority(rec["priority"]),
            "reason": rec["reason"],
            "evidence": rec["evidence"],
            "suggested_action": rec["suggested_action"],
            "expected_benefit": rec["expected_benefit"],
            "action_link": rec["action_link"],
        }
        for rec in top
    ]
    items.sort(key=lambda i: {"critical": 0, "warning": 1, "info": 2}[i["severity"]])
    return items


def _value_signal(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    """§5: "closest to producing real value," using only evidence another
    rule already computed (`rule_near_completion`'s own "Consider shipping/
    launching" recommendation, evaluated by health score + commercial
    readiness). No revenue/market-potential is ever fabricated; an honest
    "insufficient evidence" is returned when no project qualifies."""
    launch_candidates = [
        r for r in recommendations if r["recommendation"] == LAUNCH_RECOMMENDATION_TITLE
    ]
    if launch_candidates:
        best = launch_candidates[0]  # `recommendations` sorted desc by priority already
        return {
            "available": True,
            "label": "Closest to Launch",
            "project": best["project"],
            "reason": best["reason"],
            "evidence": best["evidence"],
            "expected_benefit": best["expected_benefit"],
            "action_link": best["action_link"],
        }
    return {
        "available": False,
        "label": "Best Current Opportunity",
        "message": "No project currently has both a high enough health score and a "
        "client-ready/production commercial-readiness signal -- insufficient evidence "
        "to name one as closest to launch.",
    }


def _portfolio_strip(
    all_contexts: list[dict[str, Any]], attention_project_ids: set[str]
) -> list[dict[str, Any]]:
    """§6: compact, one row per adopted project -- not a second Projects
    page. `attention_project_ids` are canonical/item ids already surfaced
    in Needs Attention, so the strip's flag never disagrees with it."""
    strip = []
    for c in all_contexts:
        if not c.get("is_adopted"):
            continue
        strip.append(
            {
                "item_id": c.get("item_id"),
                "canonical_project_id": c.get("id"),
                "display_name": c.get("display_name"),
                "health": c.get("health"),
                "status": c.get("status"),
                "latest_activity": c.get("latest_activity"),
                "has_next_action": bool((c.get("next_action") or {}).get("text")),
                "needs_attention": c.get("item_id") in attention_project_ids,
            }
        )
    return strip


def _resolve_since_last_time_baseline(settings: Settings) -> tuple[datetime, bool, str]:
    """Baseline = the user's own last completed or active session
    (`completed_at`, else `created_at`, most recent first -- `list_sessions`
    already sorts that way). Falls back to a 24h window, clearly labeled,
    when no session has ever been recorded (§3)."""
    sessions = session_db.list_sessions(limit=5, settings=settings)
    for session in sessions:
        ts = _parse_ts(session.get("completed_at") or session.get("created_at"))
        if ts is not None:
            label = (
                f"Since your last session ({session['date']})"
                if session.get("status") == "completed"
                else f"Since your current session started ({session['date']})"
            )
            return ts, False, label
    fallback = datetime.now(timezone.utc)
    from datetime import timedelta

    fallback -= timedelta(hours=FALLBACK_WINDOW_HOURS)
    return (
        fallback,
        True,
        f"No prior session on record -- showing the last {FALLBACK_WINDOW_HOURS} hours",
    )


def _since_last_time(settings: Settings) -> dict[str, Any]:
    baseline_ts, is_fallback, label = _resolve_since_last_time_baseline(settings)
    feed = workspace_service.list_activity_feed(limit=SINCE_LAST_TIME_FEED_LIMIT, settings=settings)
    events = []
    for event in feed:
        if event["type"] in _NOISE_EVENT_TYPES:
            continue
        ts = _parse_ts(event.get("timestamp"))
        if ts is None or ts <= baseline_ts:
            continue
        events.append(event)
        if len(events) >= SINCE_LAST_TIME_LIMIT:
            break
    return {
        "baseline": baseline_ts.isoformat(),
        "baseline_is_fallback": is_fallback,
        "label": label,
        "events": events,
    }


def _top_recommendation_for_project(
    recommendations: list[dict[str, Any]], *, item_id: str | None, canonical_project_id: str | None
) -> dict[str, Any] | None:
    for rec in recommendations:  # already sorted desc by (priority, confidence)
        project = rec.get("project")
        if not project:
            continue
        if (
            canonical_project_id and project.get("canonical_project_id") == canonical_project_id
        ) or (item_id and project.get("item_id") == item_id):
            return rec
    return None


def _daily_session(
    settings: Settings, home: dict[str, Any], recommendations: list[dict[str, Any]]
) -> dict[str, Any]:
    """§9: surfaces the existing Daily Session domain's own state -- does
    not replace `/session`, only shows it and links there. `Start My Day`'s
    *project* comes straight from the same Home ranking the Primary Focus
    card uses (`suggested_project`, no separate ranking); its *objective*/
    *expected result* text (Sprint C6: Daily Session's Operational
    Intelligence consumption point) comes from that project's top
    Operational Intelligence recommendation when one exists, falling back
    to the raw next-action text otherwise."""
    active = session_db.get_active_session(settings)
    if active:
        return {
            "has_active_session": True,
            "session": {
                "id": active["id"],
                "project_name": active["project_name"],
                "mode": active["mode"],
                "objective": active["objective"],
                "expected_result": active["expected_result"],
                "status": active["status"],
            },
            "action": {
                "label": "End My Day",
                "action": "complete_session",
                "session_id": active["id"],
            },
        }

    suggested = home.get("suggested_project")
    modes = list_modes()
    default_mode = modes[0]["id"] if modes else None
    if not suggested:
        return {
            "has_active_session": False,
            "suggestion": None,
            "action": {"label": "Start My Day", "action": "start_session"},
        }
    project = suggested["project"]
    next_action = project.get("next_action") or {}
    top_rec = _top_recommendation_for_project(
        recommendations,
        item_id=project.get("id"),
        canonical_project_id=project.get("canonical_project_id"),
    )
    if top_rec:
        objective = top_rec["suggested_action"] or top_rec["recommendation"]
        expected_result = top_rec["expected_benefit"]
    else:
        objective = next_action.get("text") or "Continue this project"
        expected_result = (
            f"Progress on: {next_action.get('text')}"
            if next_action.get("text")
            else "Meaningful progress on this project"
        )
    return {
        "has_active_session": False,
        "suggestion": {
            "project_name": project.get("name"),
            "item_id": project.get("id"),
            "canonical_project_id": project.get("canonical_project_id"),
            "mode": default_mode,
            "objective": objective,
            "expected_result": expected_result,
        },
        "action": {"label": "Start My Day", "action": "start_session"},
    }


def _snapshot_continuity(primary_focus: dict[str, Any] | None) -> dict[str, Any]:
    """§10: whichever project the Primary Focus card recommends is the one
    Snapshot Continuity reports on -- a second, independently-ranked
    project here would contradict the card above it."""
    if not primary_focus or not primary_focus.get("available"):
        return {"available": False}
    context = primary_focus.get("project_context")
    if not context:
        return {"available": False}
    snapshot = context.get("latest_snapshot")
    if not snapshot:
        return {
            "available": True,
            "has_snapshot": False,
            "message": "Create a snapshot before switching or ending the day.",
            "canonical_project_id": context.get("id"),
        }
    return {
        "available": True,
        "has_snapshot": True,
        "canonical_project_id": context.get("id"),
        "summary": snapshot.get("summary"),
        "pending_work": snapshot.get("pending_work"),
        "next_prompt": snapshot.get("next_prompt"),
        "timestamp": snapshot.get("created_at"),
    }


_QUICK_ACTIONS = [
    {"label": "Resume Work", "action": "resume_work"},
    {"label": "Start New AI Session", "action_link": "#/session"},
    {"label": "Create Snapshot", "action": "create_snapshot"},
    {"label": "Rescan Workspace", "action": "rescan_workspace"},
    {"label": "Open Explorer", "action_link": "#/explorer"},
    {"label": "Open Assets", "action_link": "#/assets"},
    {"label": "Review Advisor", "action_link": "#/advisor"},
]


def build_mission_control(settings: Settings | None = None) -> dict[str, Any]:
    """The one `GET /mission-control` payload -- already shaped, so the
    frontend performs no cross-source joining, ranking, deduplication, or
    empty-state decision of its own (§13)."""
    settings = settings or get_settings()

    # §12: one filesystem walk per project for this whole request, shared
    # across `all_project_contexts` (assets_count), `get_home_portfolio`,
    # `list_activity_feed` (called twice below, once for the general feed
    # and once for Since Last Time's wider window), Operational
    # Intelligence, and Executive Decision's own `compute_relationships`
    # call (Sprint C10's shared-assets detector reuses the exact walk
    # already done above, never a second one) -- see
    # `app.assets.service.request_scope`.
    with request_scope():
        all_contexts, enriched_items = _all_project_contexts(settings=settings)
        home = workspace_service.get_home_portfolio(settings=settings)
        freshness = workspace_service.get_freshness(settings=settings)
        recent_activity = workspace_service.list_activity_feed(
            limit=RECENT_ACTIVITY_LIMIT, settings=settings
        )
        since_last_time = _since_last_time(settings)

        contexts_by_item_id = _context_lookup(all_contexts)
        # Sprint C6: the one canonical Operational Intelligence Engine call
        # for this whole request -- Today's Focus, Needs Attention, Value
        # Signal, and the Daily Session suggestion's objective/expected-
        # result text are four views over this single already-sorted,
        # already-deduped list.
        recommendations = get_operational_intelligence(
            settings=settings, all_contexts=all_contexts, enriched_items=enriched_items
        )

        # Sprint C10: reuses this same request's `all_contexts`/
        # `enriched_items`/`recommendations` -- Executive Decision only
        # adds its own (cheap, ~2ms) scoring/ranking pass plus one
        # `compute_relationships` call on top, never a second whole-
        # workspace context/Operational Intelligence pass.
        executive_decision = get_executive_decision(
            settings=settings,
            all_contexts=all_contexts,
            enriched_items=enriched_items,
            operational_intelligence_recs=recommendations,
        )

    primary_focus = _primary_focus(home, contexts_by_item_id, all_contexts)
    todays_focus = _todays_focus(recommendations)
    needs_attention = _needs_attention(recommendations)
    attention_project_ids = {
        i["project"]["item_id"]
        for i in needs_attention
        if i.get("project") and i["project"].get("item_id")
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_freshness": freshness,
        "executive_decision": executive_decision["decision"],
        "ranked_projects": executive_decision["ranked_projects"],
        "primary_focus": primary_focus,
        "todays_focus": todays_focus,
        "since_last_time": since_last_time,
        "needs_attention": needs_attention,
        "value_signal": _value_signal(recommendations),
        "portfolio": _portfolio_strip(all_contexts, attention_project_ids),
        "recent_activity": recent_activity,
        "daily_session": _daily_session(settings, home, recommendations),
        "snapshot_continuity": _snapshot_continuity(primary_focus),
        "quick_actions": _QUICK_ACTIONS,
        "total_projects_tracked": len(all_contexts),
    }
