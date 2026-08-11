"""ProjectContext builder (Sprint C1: Consolidation; Sprint C1B: Rewiring).

ROLE OS accumulated four independent "what is a project" concepts across
five sprints: Project Intelligence (`app.projects`, manually-created
Projects), Discovery + Workspace Adoption (`app.workspace`, scanned/
adopted folders), Epic 2's Advisor (reasons over manual PI data), and
Workspace Advisor 2.0 (reasons over Discovery/git evidence). Sprint 5
bridged PI and Workspace identity (`app.workspace.identity`), but every
page still independently re-assembled its own subset of "project info"
from whichever of these four sources it happened to call.

Sprint C1 built this module but wired it into exactly one screen (Cockpit,
one field, non-blocking) -- see
`docs/architecture/14_PROJECT_CONTEXT_SPRINT_C1_REPORT.md` and the
consolidation-audit artifact this project's Sprint C1B corrects. C1B makes
this module load-bearing: Home, Projects, Workspace, Cockpit, and Advisor
now source their project-shaped API responses through
`build_project_context`/`build_project_contexts_for_workspace`/
`build_project_contexts_for_pi_projects` (see `routers/workspace.py`,
`routers/pi/projects.py`) instead of merely being able to. It also removes
the duplicate logic C1 left behind: the inline next-action mini-extractor,
the disconnected `resume_state` stub, and the cheap asset-count that could
silently disagree with the real Assets index.

This module still does not rewrite Discovery, Workspace, Advisor, or
Cockpit -- none of that logic moves. It is a thin composition layer: given
an identity (a Workspace item id and/or a canonical Project id), it calls
the *existing* enrichment/lookup functions exactly once each and assembles
their output into one `ProjectContext` shape. `enrich_project_item`/
`identity.py` remain the authoritative source of discovery/identity data;
this module only ever reads from them.

Both public entry points (`build_project_context` for one project,
`build_project_contexts_for_workspace` for a list page) funnel through the
same `_assemble` tail so there is exactly one place that decides what a
`ProjectContext` dict looks like.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app import db as knowledge_db
from app.advisor import engine as advisor_engine
from app.config import Settings, get_settings
from app.discovery.next_action import extract_next_action
from app.project_context.health import health_tier
from app.projects import db as projects_db
from app.workspace import advisor as workspace_advisor
from app.workspace import assets_index, service
from app.workspace import resume as resume_workflow

_EMPTY_AI_SUMMARY = {"sessions": [], "latest_session": None, "latest_snapshot": None}
_EMPTY_NEXT_ACTION = {"text": None, "source": "none", "source_path": None, "confidence": 0.0}


def _normalize_workspace_advisor_item(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": rec["recommendation"],
        "reason": rec["reason"],
        "evidence": rec.get("evidence") or [],
        "priority": rec["priority"],
        "confidence": rec["confidence"],
        "action_link": rec.get("action_link"),
        "source": "workspace_advisor",
    }


def _normalize_epic2_recommendation(rec: dict[str, Any]) -> dict[str, Any]:
    confidence_score = rec.get("confidence_score") or 0
    return {
        "title": rec.get("title") or rec.get("suggested_action") or "Recommendation",
        "reason": rec.get("reason", ""),
        "evidence": rec.get("evidence") or [],
        "priority": rec.get("priority_score", 0),
        "confidence": (
            float(confidence_score) / 100.0 if confidence_score > 1 else float(confidence_score)
        ),
        "action_link": None,
        "source": "advisor",
    }


def _knowledge_count(display_name: str, settings: Settings) -> int:
    """Best-effort cross-reference: `knowledge_cards.project` is a free-
    text field on imported ChatGPT conversations (a different, older,
    name-based "project" concept) -- there is no real identity link to
    PI/Workspace, so this is deliberately a soft, case-insensitive name
    match, never a rewrite of that domain's own identity scheme. Any
    lookup failure (no knowledge database configured, empty name) yields
    0, never an error."""
    if not display_name:
        return 0
    try:
        return sum(
            row["count"]
            for row in knowledge_db.list_projects(settings=settings)
            if (row["project"] or "").strip().lower() == display_name.strip().lower()
        )
    except Exception:
        return 0


def _technology_stack(detail: dict[str, Any]) -> list[str]:
    """Frameworks first (more specific), then bare language markers not
    already implied by a detected framework -- read straight from the
    Discovery Engine's own signals (`languages`/`tech_markers`/
    `frameworks`), never re-detected here."""
    frameworks = list(detail.get("frameworks") or [])
    markers = [m for m in (detail.get("tech_markers") or []) if m not in frameworks]
    return frameworks + markers


def _asset_count(enriched_item: dict[str, Any] | None, settings: Settings) -> int:
    """Sprint C1B: the real, filesystem-indexed asset count -- the same
    function `GET /workspace/assets` uses (`assets_index.index_assets_for_
    project`), not the cheap `discovery_detail` counter sum C1 used, which
    counted a different, looser set of files and could disagree with what
    the Assets page actually lists. `enriched_item["asset_count"]` (the old
    field) is left alone on the enriched item itself -- other code may still
    read it -- but `ProjectContext.assets_count` never uses it."""
    if not enriched_item:
        return 0
    root_path = enriched_item.get("root_path")
    if not root_path:
        return 0
    try:
        return len(
            assets_index.index_assets_for_project(
                root_path,
                enriched_item.get("name", ""),
                canonical_project_id=enriched_item.get("canonical_project_id"),
                discovery_item_id=enriched_item.get("id"),
            )
        )
    except OSError:
        return 0


def _resolve_sources(
    *, item_id: str | None, project_id: str | None, settings: Settings
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Resolves the Workspace item (enriched, if any) and the PI Project
    row (if any) behind a single identity, in either direction -- pass an
    `item_id` (Workspace's hash id) or a `project_id` (a real
    `projects.id`, including a canonical one) and get both sides back
    whenever they exist. Never creates a new Project as a side effect
    unless the item is already adopted (the same rule
    `enrich_project_item` already follows)."""
    enriched_item: dict[str, Any] | None = None
    project: dict[str, Any] | None = None

    if item_id:
        item = service.get_item(item_id, settings=settings)
        if item is not None:
            enriched_item = service.enrich_project_item(item, settings=settings)
            canonical_id = enriched_item["canonical_project_id"]
            if canonical_id:
                project = projects_db.get_project(canonical_id, settings=settings)

    if project is None and project_id:
        project = projects_db.get_project(project_id, settings=settings)

    if enriched_item is None and project is not None and project.get("discovery_item_id"):
        linked_item = service.get_item(project["discovery_item_id"], settings=settings)
        if linked_item is not None:
            enriched_item = service.enrich_project_item(linked_item, settings=settings)

    return enriched_item, project


def _assemble(
    *,
    enriched_item: dict[str, Any] | None,
    project: dict[str, Any] | None,
    settings: Settings,
    include_epic2_recs: bool,
    include_timeline: bool,
    include_recent_activity: bool = False,
    include_resume_state: bool = True,
) -> dict[str, Any]:
    """The one place a `ProjectContext` dict gets built, from an
    already-resolved Workspace item and/or PI Project row. `include_epic2_
    recs`/`include_timeline`/`include_recent_activity` are cost knobs, not
    shape differences (all `True` for a single-project fetch, cheaper ones
    `False` for the bulk list variants, which would otherwise re-run the
    Epic 2 advisor engine, a full timeline query, or a filesystem activity
    scan once per project on a list page).

    `include_resume_state` (Sprint C7.1) exists solely to break a real
    recursion: `resume_state` comes from `workspace.resume.preview_resume_
    state`, which (to build an accurate preview prompt) now builds Project
    Memory, which itself calls `build_project_context` for the same
    project -- computing `resume_state` again there would recurse forever.
    `app.project_memory.service.build_project_memory` is the one caller
    that passes `include_resume_state=False`; every other caller keeps the
    default (`True`) and sees no behavior change at all."""
    canonical_id = (enriched_item or {}).get("canonical_project_id") or (
        project["id"] if project else None
    )
    detail = (enriched_item or {}).get("discovery_detail") or {}
    git = detail.get("git") or {}
    if enriched_item is not None:
        ai_summary = enriched_item.get("ai_sessions") or dict(_EMPTY_AI_SUMMARY)
    elif canonical_id:
        # No Workspace item (a purely-manual Project) -- `enrich_project_
        # item` never ran, so nothing has looked up its AI sessions yet;
        # do it directly rather than silently reporting "no sessions."
        ai_summary = service.get_ai_session_summary(canonical_id, settings=settings)
    else:
        ai_summary = dict(_EMPTY_AI_SUMMARY)

    display_name = (enriched_item or {}).get("name") or (project or {}).get("name") or "Untitled"
    health_score = (enriched_item or {}).get("health_score")
    health_score_source = "discovery" if enriched_item is not None else None
    if health_score is None and project is not None:
        health_score = project.get("health_score")
        health_score_source = "project_intelligence" if health_score is not None else None

    # Sprint C1B: next_action always resolves through the one deterministic
    # extractor, `discovery.next_action.extract_next_action` -- never a
    # separate inline mini-implementation. For a discovered item, that
    # already happened in `enrich_project_item` (`get_next_action_for_
    # item`), so we just read its result. A purely-manual Project has no
    # root_path/git/docs for the extractor's file-based sources, but it can
    # still have a real AI Session snapshot -- the extractor's own
    # `ai_session` branch handles that case (and only that case) without
    # touching the filesystem, so calling it here with an empty root_path
    # is safe and gives the exact same confidence (0.95) the discovered-item
    # path would for the same signal, instead of C1's separate hardcoded
    # 0.6. No snapshot hint and no Workspace item means an honest "Not yet
    # defined" (confidence 0.0), never a guess.
    if enriched_item is not None:
        next_action = enriched_item.get("next_action") or dict(_EMPTY_NEXT_ACTION)
    else:
        snapshot = ai_summary.get("latest_snapshot") or {}
        if snapshot.get("next_prompt") or snapshot.get("pending_work"):
            result = extract_next_action(
                "",
                ai_session_next_prompt=snapshot.get("next_prompt"),
                ai_session_pending_work=snapshot.get("pending_work"),
            )
            next_action = dataclasses.asdict(result)
        else:
            next_action = dict(_EMPTY_NEXT_ACTION)

    advisor_summary: list[dict[str, Any]] = []
    if enriched_item is not None:
        advisor_summary.extend(
            _normalize_workspace_advisor_item(r)
            for r in workspace_advisor.generate_recommendations([enriched_item])
        )
    if include_epic2_recs and canonical_id:
        try:
            epic2_recs = advisor_engine.get_recommendations(
                project_id=canonical_id, settings=settings
            )
        except Exception:
            epic2_recs = []
        advisor_summary.extend(_normalize_epic2_recommendation(r) for r in epic2_recs)
    advisor_summary.sort(key=lambda r: r["priority"], reverse=True)

    # Timeline = AI Sessions + Snapshots (PI's own project timeline).
    # Recent Activity = git commits + filesystem changes + adoption events
    # + AI sessions/snapshots + discovered assets (Workspace's unified
    # activity feed). These are deliberately two different datasets behind
    # two different labels (Sprint C1B §8) -- Timeline never includes git/
    # filesystem/asset events, Recent Activity is not restricted to AI
    # session activity.
    timeline: list[dict[str, Any]] = []
    if include_timeline and canonical_id:
        timeline = projects_db.list_project_timeline(canonical_id, settings=settings)

    recent_activity: list[dict[str, Any]] = []
    if include_recent_activity and enriched_item is not None:
        from app.workspace import activity as activity_module

        assets_by_project = (
            {
                enriched_item["id"]: [
                    assets_index.asset_record_to_dict(r)
                    for r in assets_index.index_assets_for_project(
                        enriched_item.get("root_path", ""),
                        enriched_item.get("name", ""),
                        canonical_project_id=enriched_item.get("canonical_project_id"),
                        discovery_item_id=enriched_item.get("id"),
                    )
                ]
            }
            if enriched_item.get("root_path")
            else {}
        )
        recent_activity = activity_module.build_activity_feed(
            [enriched_item], assets_by_project=assets_by_project, limit=50
        )

    is_adopted = bool((enriched_item or {}).get("adopted"))
    fallback_id = (enriched_item or {}).get("id") or ""
    resume_state = (
        resume_workflow.preview_resume_state(canonical_id, settings=settings)
        if include_resume_state
        else {}
    )

    return {
        "id": canonical_id or fallback_id,
        "canonical_id": canonical_id or fallback_id,
        "discovery_item_id": (enriched_item or {}).get("id"),
        "project_id": (project or {}).get("id"),
        "display_name": display_name,
        "root_path": (enriched_item or {}).get("root_path"),
        "workspace": (project or {}).get("workspace")
        or ("Discovered" if enriched_item else "Products"),
        "status": (project or {}).get("status") or (enriched_item or {}).get("status"),
        "health": health_tier(health_score),
        "health_score": health_score,
        "health_score_source": health_score_source,
        "confidence": (enriched_item or {}).get("confidence_score"),
        "move_risk": (enriched_item or {}).get("move_risk"),
        "classification": (enriched_item or {}).get("classification"),
        "technology_stack": _technology_stack(detail),
        "business_value": (enriched_item or {}).get("business_value"),
        "git": git,
        "commits": git.get("recent_commits") or [],
        "latest_activity": (enriched_item or {}).get("last_modified")
        or (project or {}).get("updated_at"),
        "latest_snapshot": ai_summary.get("latest_snapshot"),
        "latest_ai_session": ai_summary.get("latest_session"),
        "next_action": next_action,
        "advisor_summary": advisor_summary,
        "assets_count": _asset_count(enriched_item, settings),
        "documents_count": detail.get("document_count", 0),
        "documentation_status": (enriched_item or {}).get("documentation_status"),
        "test_status": (enriched_item or {}).get("test_status"),
        "knowledge_count": _knowledge_count(display_name, settings),
        "timeline": timeline,
        "recent_activity": recent_activity,
        "resume_state": resume_state,
        "data_freshness": service.get_freshness(settings=settings),
        "item_id": (enriched_item or {}).get("id"),
        "is_discovered": enriched_item is not None,
        "is_adopted": is_adopted,
    }


def build_project_context(
    *,
    item_id: str | None = None,
    project_id: str | None = None,
    settings: Settings | None = None,
    include_resume_state: bool = True,
    include_epic2_recs: bool = True,
) -> dict[str, Any] | None:
    """The single Project Context builder. Pass whichever identity you
    have -- a Workspace discovery item id, a PI/canonical project id, or
    both if already known -- and get back every field a UI screen needs to
    describe that project. Returns `None` only if neither identity
    resolves to anything at all.

    `include_resume_state` defaults to `True` for every normal caller; see
    `_assemble`'s docstring for the one caller (`app.project_memory`) that
    passes `False` to avoid a real recursion. `include_epic2_recs`
    (Sprint C7.1) similarly defaults to `True`; `app.project_memory`
    passes `False` there too when it doesn't need `advisor_summary` at all
    (Project Memory reads next_action/git/latest_snapshot only) --
    avoiding a redundant Epic 2 Advisor refresh (itself an O(every PI
    project) pass) on top of the one Operational Intelligence already
    triggers when it wants a recommendation."""
    settings = settings or get_settings()
    enriched_item, project = _resolve_sources(
        item_id=item_id, project_id=project_id, settings=settings
    )
    if enriched_item is None and project is None:
        return None
    return _assemble(
        enriched_item=enriched_item,
        project=project,
        settings=settings,
        include_epic2_recs=include_epic2_recs,
        include_timeline=True,
        include_recent_activity=True,
        include_resume_state=include_resume_state,
    )


def build_project_contexts_for_workspace(
    *,
    adopted_only: bool = True,
    settings: Settings | None = None,
    enriched_items: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Bulk variant for list pages (Home/Projects/Workspace): reuses
    `list_enriched_top_level_projects` (the same single enrichment pass
    those pages already share) instead of calling `build_project_context`
    once per item, which would re-run the identity/AI-session lookups a
    second time for every project on the page. Epic 2 recs, the full
    Timeline, and the filesystem-scanning Recent Activity feed are left off
    each item here (cost knobs above) -- a list page doesn't render any of
    them; fetch the single-item context for that.

    Pass `enriched_items` when the caller already computed the enrichment
    pass itself (Sprint C1B: `routers/workspace.py` does this for `/workspace
    /discovered?view=top_level` and `/workspace/home`, so the enrichment
    only runs once per request even though both the raw response and the
    embedded `project_context` need it).
    """
    settings = settings or get_settings()
    if enriched_items is None:
        enriched_items = service.list_enriched_top_level_projects(
            adopted_only=adopted_only, settings=settings
        )
    contexts = []
    for enriched_item in enriched_items:
        canonical_id = enriched_item.get("canonical_project_id")
        project = projects_db.get_project(canonical_id, settings=settings) if canonical_id else None
        contexts.append(
            _assemble(
                enriched_item=enriched_item,
                project=project,
                settings=settings,
                include_epic2_recs=False,
                include_timeline=False,
            )
        )
    return contexts


def build_project_contexts_for_pi_projects(
    *,
    project_ids: list[str] | None = None,
    settings: Settings | None = None,
    include_epic2_recs: bool = False,
    include_timeline: bool = False,
) -> dict[str, dict[str, Any]]:
    """Bulk variant keyed by PI project id, for `/pi/projects` (Cockpit's
    project switcher and the manual side of the Projects page) -- covers
    purely-manual Projects that `build_project_contexts_for_workspace`
    never sees (it only iterates Workspace/Discovery items). Pass
    `project_ids` to scope to a known set (e.g. one page of results);
    omitted, every PI project is built. Cost knobs default to cheap (no
    Epic 2 recs, no timeline) for the list case; pass both `True` for a
    single-project fetch."""
    settings = settings or get_settings()
    if project_ids is not None:
        projects = [projects_db.get_project(pid, settings=settings) for pid in project_ids]
    else:
        projects = projects_db.list_projects(settings=settings)

    contexts: dict[str, dict[str, Any]] = {}
    for project in projects:
        if not project:
            continue
        enriched_item = None
        discovery_item_id = project.get("discovery_item_id")
        if discovery_item_id:
            linked_item = service.get_item(discovery_item_id, settings=settings)
            if linked_item is not None:
                enriched_item = service.enrich_project_item(linked_item, settings=settings)
        contexts[project["id"]] = _assemble(
            enriched_item=enriched_item,
            project=project,
            settings=settings,
            include_epic2_recs=include_epic2_recs,
            include_timeline=include_timeline,
        )
    return contexts


def all_project_contexts(
    settings: Settings | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Sprint C3 (Explorer 2.0 hardening): "every tracked project" --
    discovered-and-adopted (via `list_enriched_top_level_projects
    (adopted_only=True)`, the same enrichment pass Home/Advisor/Assets/
    Activity already share) plus purely-manual PI projects (no
    `discovery_item_id`, so an adopted item's own canonical PI row is
    never double-counted). This one function is the single place that
    definition lives -- `app.dashboard.service` and `app.explorer.service`
    both call it instead of each keeping their own private copy (the
    consolidation audit that opened Sprint C3's follow-up flagged the
    duplicate as exactly the kind of "no duplicated aggregation" violation
    this project keeps correcting).

    Returns `(all_contexts, enriched_workspace_items)` -- the raw enriched
    items are still needed by `workspace_advisor`'s rule functions, which
    read discovery-only fields `ProjectContext` doesn't carry (e.g.
    `discovery_detail`, `item_kind`).
    """
    settings = settings or get_settings()
    enriched_items = service.list_enriched_top_level_projects(adopted_only=True, settings=settings)
    workspace_contexts = build_project_contexts_for_workspace(
        enriched_items=enriched_items, settings=settings
    )
    manual_projects = [
        p for p in projects_db.list_projects(settings=settings) if not p.get("discovery_item_id")
    ]
    manual_contexts = list(
        build_project_contexts_for_pi_projects(
            project_ids=[p["id"] for p in manual_projects], settings=settings
        ).values()
    )
    return workspace_contexts + manual_contexts, enriched_items
