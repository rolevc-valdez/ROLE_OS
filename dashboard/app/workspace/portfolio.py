"""Home page portfolio aggregation (Sprint 4 §4): real signals over
discovered/adopted projects instead of an empty/zero-centric Home. Pure
aggregation over data `service`/`activity`/`advisor` already computed.
"""

from __future__ import annotations

from typing import Any

from app.workspace.advisor import last_activity_age_days


def _sort_key_activity(item: dict[str, Any]) -> float:
    age = last_activity_age_days(item)
    return age if age is not None else float("inf")


def last_active_project(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [i for i in items if last_activity_age_days(i) is not None]
    if not candidates:
        return None
    return min(candidates, key=_sort_key_activity)


def most_recently_modified_project(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [i for i in items if i.get("last_modified")]
    if not candidates:
        return None
    return max(candidates, key=lambda i: i["last_modified"])


def projects_needing_attention(
    recommendations: list[dict[str, Any]], limit: int = 5
) -> list[dict[str, Any]]:
    seen_projects: set[str] = set()
    result = []
    for rec in recommendations:
        if rec["project_id"] in seen_projects:
            continue
        seen_projects.add(rec["project_id"])
        result.append(rec)
        if len(result) >= limit:
            break
    return result


def suggested_project_to_continue(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A simple, explainable score: has a next action, recent activity,
    and higher business value all push a project up -- no ML, no hidden
    weighting beyond what's printed in `reasons`."""
    scored = []
    for item in items:
        if not item.get("adopted"):
            continue
        next_action = item.get("next_action") or {}
        if not next_action.get("text"):
            continue
        age = last_activity_age_days(item)
        score = float(next_action.get("confidence") or 0)
        reasons = [f"has a next action (source: {next_action.get('source')})"]
        if age is not None and age <= 14:
            score += 0.5
            reasons.append(f"active in the last {int(age)} day(s)")
        if item.get("business_value") in ("high", "critical"):
            score += 0.3
            reasons.append(f"business value: {item.get('business_value')}")
        scored.append((score, item, reasons))
    if not scored:
        return None
    scored.sort(key=lambda t: t[0], reverse=True)
    score, item, reasons = scored[0]
    return {"project": item, "score": round(score, 2), "reasons": reasons}


def build_home_portfolio(
    items: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    recent_activity: list[dict[str, Any]],
    latest_ai_session: dict[str, Any] | None,
    recent_assets: list[dict[str, Any]],
) -> dict[str, Any]:
    suggestion = suggested_project_to_continue(items)
    quick_resume = None
    if suggestion:
        p = suggestion["project"]
        na = p.get("next_action") or {}
        # Sprint 5 §4: Quick Resume must always point to the canonical
        # Project Identity -- `item_id` is what the Resume Work API call
        # itself needs (it's keyed by the Workspace item), but
        # `canonical_project_id` (resolved by `enrich_project_item`,
        # never guessed here) is where the flow actually lands, in
        # Cockpit, once resumed.
        quick_resume = {
            "item_id": p["id"],
            "canonical_project_id": p.get("canonical_project_id"),
            "project_name": p["name"],
            "action_text": na.get("text"),
        }

    return {
        "last_active_project": last_active_project(items),
        "most_recently_modified_project": most_recently_modified_project(items),
        "projects_needing_attention": projects_needing_attention(recommendations),
        "recent_commits": [e for e in recent_activity if e["type"] == "git_commit"][:10],
        "recent_assets": recent_assets[:10],
        "latest_ai_session": latest_ai_session,
        "suggested_project": suggestion,
        "quick_resume": quick_resume,
        "total_projects": len(items),
        "total_adopted": sum(1 for i in items if i.get("adopted")),
    }
