"""Orchestrates Workspace Adoption: cached Discovery scans + user overlay.

`root_path` (from the Discovery Engine) is the only identity a discovered
folder has, so every item's API id is a deterministic hash of it -- stable
across rescans as long as the folder doesn't move, and requiring no write
just to look at the discovered list.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.discovery.identity import compute_item_id
from app.discovery.next_action import extract_next_action
from app.discovery.service import run_audit
from app.projects import db as projects_db
from app.workspace import activity, advisor, assets_index, db, identity, portfolio
from app.workspace import resume as resume_workflow


def discovery_id(root_path: str) -> str:
    return compute_item_id(root_path)


def rescan(
    settings: Settings | None = None, root: str | None = None, max_depth: int = 2
) -> dict[str, Any]:
    """Runs the real, read-only Discovery Engine against `root` (or the
    configured default) and caches the result. Never touches the scanned
    tree -- see `app.discovery.service.run_audit`."""
    settings = settings or get_settings()
    target_root = root or settings.discovery_root
    if not target_root:
        raise ValueError("no discovery root configured (set ROLE_OS_DISCOVERY_ROOT or pass `root`)")

    result = run_audit(
        Path(target_root), max_depth=max_depth, extra_exclusions=settings.discovery_extra_exclusions
    )
    projects = [dataclasses.asdict(p) for p in result.projects]
    db.save_scan_cache(
        root=result.root,
        scanned_at=result.scanned_at,
        duration_seconds=result.duration_seconds,
        projects=projects,
        settings=settings,
    )
    return get_summary(settings)


def _cached_projects(settings: Settings | None = None) -> list[dict[str, Any]]:
    cache = db.load_scan_cache(settings)
    return cache["projects"] if cache else []


def _default_overlay(item_id: str, root_path: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "root_path": root_path,
        "adopted": False,
        "ignored": False,
        "priority": "medium",
        "business_value": "medium",
        "status": "new",
        "tags": [],
        "notes": [],
        "adopted_at": None,
        "override_action": None,
        "override_parent_id": None,
        "canonical_project_id": None,
    }


def _merge(project: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    git = project.get("git") or {}
    override_action = overlay.get("override_action")

    # §8: "detected boundary" (the Discovery Engine's own computed fields,
    # always preserved below as-is) vs. the *effective* grouping the
    # Workspace UI actually uses, which a user override can change without
    # ever touching the computed fields themselves.
    effective_is_top_level = project.get("is_top_level_project", False)
    effective_parent_item_id = project.get("parent_item_id")
    if override_action == "top_level":
        effective_is_top_level = True
        effective_parent_item_id = None
    elif override_action == "attach_to_parent":
        effective_is_top_level = False
        effective_parent_item_id = overlay.get("override_parent_id")

    return {
        "id": overlay["id"],
        "name": project["name"],
        "root_path": project["root_path"],
        "parent_path": project.get("parent_path"),
        "depth": project.get("depth", 1),
        "classification": project.get("classification", "Unknown"),
        "git_is_repo": git.get("is_repo", False),
        "git_branch": git.get("branch"),
        "git_last_commit_date": git.get("last_commit_date"),
        "git_is_dirty": git.get("is_dirty"),
        "health_score": project.get("health_score"),
        "confidence_score": project.get("confidence_score", 0.0),
        "move_risk": project.get("move_risk", "low"),
        "maturity": project.get("maturity", "unknown"),
        "commercial_readiness": project.get("commercial_readiness", "unknown"),
        "recommendation": project.get("recommendation", "Requires manual review"),
        "last_modified": project.get("last_modified"),
        "adopted": overlay["adopted"],
        "ignored": overlay["ignored"],
        "priority": overlay["priority"],
        "business_value": overlay["business_value"],
        "status": overlay["status"],
        "tags": overlay["tags"],
        "notes": overlay["notes"],
        "adopted_at": overlay["adopted_at"],
        # Sprint 3: project-boundary/hierarchy fields, as computed by the
        # Discovery Engine (never altered by an override).
        "item_kind": project.get("item_kind", "unknown"),
        "parent_item_id": project.get("parent_item_id"),
        "project_root_id": project.get("project_root_id"),
        "hierarchy_depth": project.get("hierarchy_depth", 0),
        "is_top_level_project": project.get("is_top_level_project", False),
        "is_nested_repository": project.get("is_nested_repository", False),
        "is_internal_folder": project.get("is_internal_folder", False),
        "is_excluded": project.get("is_excluded", False),
        "exclusion_reason": project.get("exclusion_reason"),
        "boundary_confidence": project.get("boundary_confidence", 0.0),
        "boundary_evidence": project.get("boundary_evidence", []),
        # User override (§8/§9) -- None unless explicitly set; never
        # written to the scanned folder, only to this overlay row.
        "override_action": override_action,
        "override_parent_id": overlay.get("override_parent_id"),
        "effective_is_top_level_project": effective_is_top_level,
        "effective_parent_item_id": effective_parent_item_id,
        # Sprint 5 (Project Unification): the bridge to this item's real
        # ROLE OS Project row, if one has been resolved yet (only ever set
        # by `identity.get_or_create_canonical_project_id`, never written
        # here) -- None for an item that has never been adopted.
        "canonical_project_id": overlay.get("canonical_project_id"),
        # Full discovered signal set, for the "Review" detail view -- never
        # persisted, always re-read from the live cached scan.
        "discovery_detail": project,
    }


def list_workspace_items(
    *, include_ignored: bool = False, settings: Settings | None = None
) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    overlays = db.list_overlays(settings)
    items = []
    for project in _cached_projects(settings):
        item_id = discovery_id(project["root_path"])
        overlay = overlays.get(item_id) or _default_overlay(item_id, project["root_path"])
        if overlay["ignored"] and not include_ignored:
            continue
        items.append(_merge(project, overlay))
    items.sort(key=lambda i: (not i["adopted"], i["name"].lower()))
    return items


_NESTED_KINDS = ("repository", "component")
_INTERNAL_KINDS = ("internal_folder", "documentation", "asset_library")
VALID_HIERARCHY_VIEWS = ("top_level", "repositories", "excluded", "needs_review", "all")


def list_hierarchy(
    *, view: str = "top_level", include_ignored: bool = False, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """§6/§7: the grouped Workspace view -- top-level projects with their
    repositories/components/internal folders rolled up underneath, instead
    of one flat peer row per discovered folder.

    `view`:
      - "top_level" (default): only top-level projects, each with an
        embedded `children` list and repository/component/asset/
        documentation counts.
      - "repositories": a flat list of nested repository/component items
        (across every parent), each carrying its parent's name/id.
      - "excluded": folders the Discovery Engine excluded (§5), each with
        its exclusion reason.
      - "needs_review": ambiguous items (`item_kind == "unknown"`) at any
        depth.
      - "all": every item, flat, regardless of kind -- the same shape
        `GET /workspace/discovered` has always returned.

    A user override (§8) changes an item's *effective* top-level/parent
    status here without ever touching the Discovery Engine's own computed
    fields (still visible per-item as `item_kind`/`parent_item_id`/etc.).
    """
    assert view in VALID_HIERARCHY_VIEWS, f"unknown hierarchy view: {view}"
    items = list_workspace_items(include_ignored=include_ignored, settings=settings)
    by_id = {item["id"]: item for item in items}

    if view == "all":
        return items

    if view == "excluded":
        return [i for i in items if i["item_kind"] == "excluded"]

    if view == "needs_review":
        return [i for i in items if i["item_kind"] == "unknown"]

    if view == "repositories":
        nested = [i for i in items if i["item_kind"] in _NESTED_KINDS]
        for item in nested:
            parent = by_id.get(item["effective_parent_item_id"])
            item["parent_name"] = parent["name"] if parent else None
        return nested

    # view == "top_level"
    top_level_ids = {i["id"] for i in items if i["effective_is_top_level_project"]}
    top_level_items = []
    for item in items:
        if item["id"] not in top_level_ids:
            continue
        children = [
            c
            for c in items
            if c["id"] not in top_level_ids and c["effective_parent_item_id"] == item["id"]
        ]
        item = dict(item)
        item["children"] = children
        item["repository_count"] = sum(1 for c in children if c["item_kind"] == "repository")
        item["component_count"] = sum(1 for c in children if c["item_kind"] == "component")
        item["documentation_count"] = sum(1 for c in children if c["item_kind"] == "documentation")
        item["asset_library_count"] = sum(1 for c in children if c["item_kind"] == "asset_library")
        item["internal_folder_count"] = sum(
            1 for c in children if c["item_kind"] in _INTERNAL_KINDS
        )
        top_level_items.append(item)

    # A non-top-level item that *does* have a parent reference (its own
    # discovery-computed parent, or a user "attach to parent" override) but
    # that parent id no longer resolves to a live top-level item -- e.g. a
    # stale override left pointing at something a later rescan removed --
    # is shown as its own top-level entry instead of silently disappearing.
    # Items with no parent reference at all (`unknown`/`non_project` depth-1
    # folders that were never promoted) are deliberately *not* included
    # here -- those belong in the "needs_review"/"all" views, not the
    # default top-level list.
    for item in items:
        if item["id"] in top_level_ids:
            continue
        parent_ref = item["effective_parent_item_id"]
        if parent_ref is not None and parent_ref not in top_level_ids:
            orphan = dict(item)
            orphan["children"] = []
            orphan["repository_count"] = 0
            orphan["component_count"] = 0
            orphan["documentation_count"] = 0
            orphan["asset_library_count"] = 0
            orphan["internal_folder_count"] = 0
            top_level_items.append(orphan)

    top_level_items.sort(key=lambda i: (not i["adopted"], i["name"].lower()))
    return top_level_items


def set_override(
    item_id: str, action: str, parent_id: str | None = None, settings: Settings | None = None
) -> dict[str, Any] | None:
    settings = settings or get_settings()
    project = _find_project(item_id, settings)
    if project is None:
        return None
    db.set_override(item_id, project["root_path"], action, parent_id, settings=settings)
    return get_item(item_id, settings)


def clear_override(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    if db.clear_override(item_id, settings) is None:
        return None
    return get_item(item_id, settings)


def get_item(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    for project in _cached_projects(settings):
        if discovery_id(project["root_path"]) == item_id:
            overlay = db.get_overlay(item_id, settings) or _default_overlay(
                item_id, project["root_path"]
            )
            return _merge(project, overlay)
    return None


def _find_project(item_id: str, settings: Settings) -> dict[str, Any] | None:
    for project in _cached_projects(settings):
        if discovery_id(project["root_path"]) == item_id:
            return project
    return None


def adopt_item(
    item_id: str,
    *,
    priority: str = "medium",
    business_value: str = "medium",
    status: str = "active",
    tags: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    settings = settings or get_settings()
    project = _find_project(item_id, settings)
    if project is None:
        return None
    db.adopt(
        item_id,
        project["root_path"],
        priority=priority,
        business_value=business_value,
        status=status,
        tags=tags,
        settings=settings,
    )
    # Sprint 5: every adopted project becomes a first-class ROLE OS
    # Project the moment it's adopted -- this is what makes AI Sessions/
    # Timeline/Resume Work available with zero manual creation (§2).
    identity.get_or_create_canonical_project_id(
        item_id, project["root_path"], project["name"], settings=settings
    )
    return get_item(item_id, settings)


def ignore_item(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    project = _find_project(item_id, settings)
    if project is None:
        return None
    db.ignore(item_id, project["root_path"], settings)
    return get_item(item_id, settings)


def unignore_item(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    if db.unignore(item_id, settings) is None:
        return None
    return get_item(item_id, settings)


def update_item(
    item_id: str, patch: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any] | None:
    settings = settings or get_settings()
    project = _find_project(item_id, settings)
    if project is None:
        return None
    db.update_overlay(item_id, project["root_path"], patch, settings)
    return get_item(item_id, settings)


def add_note(item_id: str, text: str, settings: Settings | None = None) -> dict[str, Any] | None:
    settings = settings or get_settings()
    project = _find_project(item_id, settings)
    if project is None:
        return None
    db.add_note(item_id, project["root_path"], text, settings)
    return get_item(item_id, settings)


def get_summary(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    cache = db.load_scan_cache(settings)
    overlays = db.list_overlays(settings)
    cached_ids = {discovery_id(p["root_path"]) for p in (cache["projects"] if cache else [])}
    adopted = sum(1 for i, o in overlays.items() if o["adopted"] and i in cached_ids)
    ignored = sum(1 for i, o in overlays.items() if o["ignored"] and i in cached_ids)
    return {
        "root": cache["root"] if cache else (settings.discovery_root or None),
        "last_scan": cache["scanned_at"] if cache else None,
        "projects_found": cache["project_count"] if cache else 0,
        "projects_adopted": adopted,
        "projects_ignored": ignored,
    }


def list_adopted_as_projects(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Adopted items reshaped for the Projects page: same field names the
    manually-created Project list already uses, so the UI can render both
    kinds of project in one list without special-casing either."""
    settings = settings or get_settings()
    items = [
        i for i in list_workspace_items(include_ignored=False, settings=settings) if i["adopted"]
    ]
    projects = []
    for item in items:
        projects.append(
            {
                "id": item["id"],
                "name": item["name"],
                "workspace": "Discovered",
                "description": item["root_path"],
                "status": item["status"],
                "health_score": item["health_score"] if item["health_score"] is not None else 0,
                "priority": item["priority"],
                "tags": item["tags"],
                "owner": "",
                "updated_at": item["adopted_at"] or item["last_modified"] or "",
                "is_discovered": True,
                "root_path": item["root_path"],
                "business_value": item["business_value"],
                "move_risk": item["move_risk"],
            }
        )
    return projects


# ---------------------------------------------------------------------------
# Sprint 4 (Project Intelligence Wiring): next-action, AI session lookup,
# and documentation/test status labels -- read-only enrichment layered on
# top of everything above, never persisted, always recomputed live.
# ---------------------------------------------------------------------------


_EMPTY_AI_SESSION_SUMMARY = {"sessions": [], "latest_session": None, "latest_snapshot": None}


def get_ai_session_summary(
    canonical_project_id: str | None, settings: Settings | None = None
) -> dict[str, Any]:
    """Reads `app.projects.db`'s ai_sessions/snapshots tables for a
    Workspace item's **canonical Project id** (Sprint 5 -- see
    `app.workspace.identity`). `canonical_project_id` is `None` for an
    item that has never been adopted (nothing to look up yet, honestly
    "Not yet defined" rather than an error)."""
    settings = settings or get_settings()
    if canonical_project_id is None:
        return dict(_EMPTY_AI_SESSION_SUMMARY)
    sessions = projects_db.list_ai_sessions(canonical_project_id, settings=settings)
    latest_session = sessions[0] if sessions else None
    latest_snapshot = None
    if latest_session:
        latest_snapshot = projects_db.get_latest_snapshot(latest_session["id"], settings=settings)
    return {
        "sessions": sessions,
        "latest_session": latest_session,
        "latest_snapshot": latest_snapshot,
    }


def _documentation_status(discovery_detail: dict[str, Any]) -> str:
    has_readme = discovery_detail.get("has_readme")
    has_roadmap = discovery_detail.get("has_roadmap")
    has_changelog = discovery_detail.get("has_changelog")
    doc_folders = discovery_detail.get("doc_folders") or []
    if has_readme and (has_roadmap or has_changelog) and doc_folders:
        return "Complete (README, roadmap/changelog, docs folder)"
    if has_readme and (has_roadmap or has_changelog):
        return "Good (README + roadmap/changelog)"
    if has_readme:
        return "Minimal (README only)"
    return "Missing"


def _test_status(discovery_detail: dict[str, Any]) -> str:
    if not discovery_detail.get("has_tests"):
        return "Not detected"
    count = discovery_detail.get("test_file_count") or 0
    return f"Detected ({count} test file(s))" if count else "Detected"


def get_next_action_for_item(
    item: dict[str, Any], ai_summary: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any]:
    settings = settings or get_settings()
    snapshot = ai_summary["latest_snapshot"] or {}
    detail = item.get("discovery_detail") or {}
    git = detail.get("git") or {}
    result = extract_next_action(
        item["root_path"],
        ai_session_next_prompt=snapshot.get("next_prompt"),
        ai_session_pending_work=snapshot.get("pending_work"),
        last_commit_message=git.get("last_commit_message"),
        last_commit_date=git.get("last_commit_date"),
    )
    return dataclasses.asdict(result)


def enrich_project_item(
    item: dict[str, Any],
    settings: Settings | None = None,
    ai_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Adds next_action/documentation_status/test_status/ai_sessions/
    canonical_project_id to an already-merged workspace item (from
    `list_hierarchy`/`get_item`). Used by the Projects page, Project
    Detail, Home, and the Workspace Advisor -- one definition, so they can
    never disagree with each other.

    Sprint 5: for an *adopted* item, this is also where a missing
    canonical Project identity gets resolved (self-healing -- see
    `app.workspace.identity`), so AI Sessions/Timeline/Resume Work work
    the moment any of these callers reads the item, with no separate
    migration step required.

    `ai_summary` may be passed in by a caller that already computed it
    (Sprint C1: `get_enriched_item`/`ProjectContext` do this) to avoid a
    second, redundant `get_ai_session_summary` round trip for the same
    item -- if omitted, it's computed here exactly as before.
    """
    settings = settings or get_settings()
    detail = item.get("discovery_detail") or {}

    if item.get("adopted"):
        canonical_project_id = identity.get_or_create_canonical_project_id(
            item["id"], item["root_path"], item["name"], settings=settings
        )
    else:
        canonical_project_id = identity.get_canonical_project_id(item["id"], settings=settings)

    if ai_summary is None:
        ai_summary = get_ai_session_summary(canonical_project_id, settings=settings)

    enriched = dict(item)
    enriched["canonical_project_id"] = canonical_project_id
    # Sprint C1 (Consolidation): attach the already-computed AI session
    # summary directly, so every caller of `enrich_project_item`/
    # `list_enriched_top_level_projects` (Home, Projects, Advisor,
    # Workspace) sees the same real session data instead of each
    # recomputing (or, as `get_home_portfolio` previously did, silently
    # never computing) its own copy.
    enriched["ai_sessions"] = ai_summary
    enriched["next_action"] = get_next_action_for_item(item, ai_summary, settings=settings)
    enriched["documentation_status"] = _documentation_status(detail)
    enriched["test_status"] = _test_status(detail)
    enriched["asset_count"] = (
        (detail.get("image_count") or 0)
        + (detail.get("video_count") or 0)
        + (detail.get("document_count") or 0)
        + (detail.get("design_file_count") or 0)
        + (detail.get("font_count") or 0)
    )
    return enriched


def list_enriched_top_level_projects(
    *, adopted_only: bool = False, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """The core data source for Projects/Home/Advisor: every top-level
    project (§6/§7 of Sprint 3), enriched with next-action/documentation/
    test/asset signals. Excluded and internal-folder items are never
    included -- `list_hierarchy(view="top_level")` already only returns
    real top-level projects (Sprint 3 §9's guarantee carries forward)."""
    settings = settings or get_settings()
    items = list_hierarchy(view="top_level", settings=settings)
    if adopted_only:
        items = [i for i in items if i["adopted"]]
    return [enrich_project_item(i, settings=settings) for i in items]


def list_project_assets(
    *,
    settings: Settings | None = None,
    adopted_only: bool = True,
    project_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """§6: real discovered asset records per adopted project, keyed by
    project item id. Walks each project's `root_path` fresh (bounded,
    read-only, never copies a file) -- see `assets_index.py`.

    `project_id` (Sprint C1: Consolidation) restricts the walk to a single
    item -- previously every caller wanting one project's assets (e.g. the
    Discovered Project Detail page) still had every adopted project's
    filesystem walked."""
    settings = settings or get_settings()
    items = list_hierarchy(view="top_level", settings=settings)
    if adopted_only:
        items = [i for i in items if i["adopted"]]
    if project_id:
        items = [i for i in items if i["id"] == project_id]
    return {
        item["id"]: [
            assets_index.asset_record_to_dict(r)
            for r in assets_index.index_assets_for_project(
                item["root_path"],
                item["name"],
                canonical_project_id=item.get("canonical_project_id"),
                discovery_item_id=item["id"],
            )
        ]
        for item in items
    }


def list_activity_feed(
    *, limit: int = 50, project_id: str | None = None, settings: Settings | None = None
) -> list[dict[str, Any]]:
    """`project_id` (Sprint C1: Consolidation) restricts the feed to a
    single project -- previously the Discovered Project Detail page had no
    server-side way to ask for this, and instead fetched the *entire*
    feed (every adopted project) and filtered it client-side in
    `app.js`."""
    settings = settings or get_settings()
    enriched = list_enriched_top_level_projects(adopted_only=True, settings=settings)
    if project_id:
        enriched = [i for i in enriched if i["id"] == project_id]
    assets_by_project = list_project_assets(
        settings=settings, adopted_only=True, project_id=project_id
    )
    return activity.build_activity_feed(enriched, assets_by_project=assets_by_project, limit=limit)


def list_advisor_recommendations(settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    enriched = list_enriched_top_level_projects(adopted_only=True, settings=settings)
    return advisor.generate_recommendations(enriched)


def get_home_portfolio(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    enriched = list_enriched_top_level_projects(adopted_only=True, settings=settings)
    recommendations = advisor.generate_recommendations(enriched)
    assets_by_project = list_project_assets(settings=settings, adopted_only=True)
    recent_activity = activity.build_activity_feed(
        enriched, assets_by_project=assets_by_project, limit=50
    )

    latest_ai_session = None
    for item in enriched:
        session = (item.get("ai_sessions") or {}).get("latest_session")
        if session and (
            latest_ai_session is None
            or (session.get("last_used_at") or "") > (latest_ai_session.get("last_used_at") or "")
        ):
            latest_ai_session = session

    all_assets = [a for assets in assets_by_project.values() for a in assets]
    all_assets.sort(key=lambda a: a["modified_at"], reverse=True)

    return portfolio.build_home_portfolio(
        enriched, recommendations, recent_activity, latest_ai_session, all_assets
    )


STALE_THRESHOLD_HOURS = 24


def get_freshness(settings: Settings | None = None) -> dict[str, Any]:
    """§8: last scan / last refresh / stale-data warning."""
    settings = settings or get_settings()
    summary = get_summary(settings=settings)
    last_scan = summary.get("last_scan")
    hours_since_scan = None
    is_stale = False
    if last_scan:
        from datetime import datetime, timezone

        try:
            dt = datetime.fromisoformat(last_scan.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours_since_scan = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
            is_stale = hours_since_scan > STALE_THRESHOLD_HOURS
        except ValueError:
            pass
    else:
        is_stale = True

    return {
        "last_scan": last_scan,
        "hours_since_scan": round(hours_since_scan, 1) if hours_since_scan is not None else None,
        "stale_threshold_hours": STALE_THRESHOLD_HOURS,
        "is_stale": is_stale,
    }


def get_enriched_item(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    """Project Detail's data source: the full merged item (including
    non-top-level ones, e.g. a repository/component being reviewed
    directly), the same enrichment `list_enriched_top_level_projects`
    applies, plus the full AI Sessions summary and Project Timeline (§6
    "History") -- both keyed by the resolved canonical Project id, so a
    freshly-adopted item's history is real from the first read, not a
    second, separately-computed guess.

    Sprint C1 (Consolidation): resolves the canonical id and computes the
    AI session summary exactly once here, then hands it to
    `enrich_project_item` (which now accepts a precomputed `ai_summary`)
    instead of each computing its own -- this used to run the same
    `list_ai_sessions`/`get_latest_snapshot` lookup twice per call.
    """
    settings = settings or get_settings()
    item = get_item(item_id, settings=settings)
    if item is None:
        return None

    if item.get("adopted"):
        canonical_project_id = identity.get_or_create_canonical_project_id(
            item["id"], item["root_path"], item["name"], settings=settings
        )
    else:
        canonical_project_id = identity.get_canonical_project_id(item["id"], settings=settings)
    ai_summary = get_ai_session_summary(canonical_project_id, settings=settings)

    enriched = enrich_project_item(item, settings=settings, ai_summary=ai_summary)
    enriched["timeline"] = (
        projects_db.list_project_timeline(canonical_project_id, settings=settings)
        if canonical_project_id
        else []
    )
    return enriched


def resume_work_for_item(
    item_id: str,
    settings: Settings | None = None,
    *,
    user_objective: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Sprint 5 §3: the one primary action a Project page exposes. Only
    valid for an *adopted* item -- an unadopted, merely-discovered folder
    has no canonical identity to resume work against (adopt it first).
    `user_objective` (hotfix): the no-action guard's own answer, passed
    straight through to `app.workspace.resume.resume_work`."""
    settings = settings or get_settings()
    project = _find_project(item_id, settings)
    if project is None:
        return None
    overlay = db.get_overlay(item_id, settings)
    if not overlay or not overlay.get("adopted"):
        return None
    canonical_project_id = identity.get_or_create_canonical_project_id(
        item_id, project["root_path"], project["name"], settings=settings
    )
    result = resume_workflow.resume_work(
        canonical_project_id, settings=settings, user_objective=user_objective
    )
    if result is not None:
        result["item_id"] = item_id
    return result


def launch_claude_code_for_item(
    item_id: str, prompt: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    """Hotfix §7/§10: the Windows one-click launcher. Only valid for an
    *adopted*, non-excluded item, same guard as `resume_work_for_item`
    (plus the excluded-folder check, second hotfix §3) -- an unadopted or
    boundary-excluded folder has no business being launched into, and
    this must never launch Claude Code in an arbitrary, unvetted
    directory. `root_path` always comes from this lookup, never from the
    caller, so the working directory handed to `app.workspace.launcher.
    launch_claude_code` is always the project's own validated, canonical
    local root."""
    from app.workspace.launcher import LauncherError, launch_claude_code

    settings = settings or get_settings()
    project = _find_project(item_id, settings)
    if project is None:
        return None
    overlay = db.get_overlay(item_id, settings)
    if not overlay or not overlay.get("adopted"):
        return None
    if project.get("is_excluded"):
        return {
            "launched": False,
            "working_directory": project["root_path"],
            "executable": None,
            "cli_available": False,
            "prompt_copied": False,
            "message": (
                f"{project['name']} is a boundary-excluded folder (reason: "
                f"{project.get('exclusion_reason') or 'excluded by the Discovery Engine'}) -- "
                "Claude Code will not be launched into it."
            ),
        }

    try:
        result = launch_claude_code(project["root_path"], prompt)
    except LauncherError as exc:
        return {
            "launched": False,
            "working_directory": project["root_path"],
            "executable": None,
            "cli_available": False,
            "prompt_copied": False,
            "message": str(exc),
        }
    return result
