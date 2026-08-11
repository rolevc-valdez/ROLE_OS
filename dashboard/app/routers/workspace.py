"""Workspace Adoption API (Discovery Engine Sprint 2).

Thin HTTP layer over `app.workspace.service`, which itself only ever calls
the read-only Discovery Engine (`app.discovery.service.run_audit`) and this
domain's own small overlay database. No project metadata is duplicated
here -- see `app.workspace.__init__` for the "filesystem is the source of
truth" contract this API is built to keep.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.project_context.builder import build_project_context, build_project_contexts_for_workspace
from app.workspace import service
from app.workspace.models import (
    AdoptRequest,
    LaunchClaudeCodeRequest,
    LaunchClaudeCodeResult,
    NoteCreate,
    OverlayUpdate,
    OverrideRequest,
    RescanRequest,
    ResumeWorkRequest,
    ResumeWorkResult,
    WorkspaceItem,
    WorkspaceSummary,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _attach_contexts(items: list[dict[str, Any]], *, settings=None) -> list[dict[str, Any]]:
    """Sprint C1B (Rewiring): embeds each item's real `ProjectContext` as
    `item["project_context"]`, built from the *same* enrichment pass
    already computed for `items` (no second enrichment/identity lookup) --
    see `build_project_contexts_for_workspace(enriched_items=...)`. Every
    project-oriented screen this response feeds (Projects page, Workspace
    page) reads health/next-action/resume-state/asset-count off this
    embedded object rather than recomputing any of them."""
    contexts = build_project_contexts_for_workspace(enriched_items=items, settings=settings)
    for item, context in zip(items, contexts):
        item["project_context"] = context
    return items


@router.get("/summary", response_model=WorkspaceSummary)
def get_summary():
    """§8: last scan / stale-data warning, merged into the existing
    summary response (additive fields only -- `WorkspaceSummary` allows
    extras, so this is not a breaking change to the Sprint 2 contract)."""
    summary = service.get_summary()
    summary.update(service.get_freshness())
    return summary


@router.get("/discovered", response_model=list[WorkspaceItem])
def list_discovered(include_ignored: bool = False, view: str | None = None):
    """Default (`view` omitted): every discovered item, flat, exactly as
    this endpoint has always returned it (Sprint 2 contract, unchanged).

    Pass `view=top_level|repositories|excluded|needs_review|all` (§6/§7)
    for the grouped hierarchy the Workspace page now uses by default --
    `all` is equivalent to omitting `view` and exists only so callers can
    be explicit about it.
    """
    if view is None:
        return service.list_workspace_items(include_ignored=include_ignored)
    if view not in service.VALID_HIERARCHY_VIEWS:
        raise HTTPException(status_code=400, detail=f"unknown view: {view}")
    if view == "top_level":
        # Sprint 4: the Projects page's data source -- top-level items,
        # each enriched with next_action/documentation_status/test_status/
        # asset_count (§1 of the brief). Every other view stays the plain,
        # unenriched hierarchy (cheaper, and those items aren't shown on
        # the Projects page). Sprint C1B: each item also carries an
        # embedded `project_context` (see `_attach_contexts`).
        return _attach_contexts(service.list_enriched_top_level_projects())
    return service.list_hierarchy(view=view, include_ignored=include_ignored)


@router.get("/discovered/{item_id}", response_model=WorkspaceItem)
def get_discovered(item_id: str):
    item = service.get_enriched_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="discovered project not found")
    # Sprint C1B (Rewiring): Project Detail's canonical projection -- full
    # cost (Epic 2 recs, timeline, recent activity), one build per detail
    # view, not per list row.
    item["project_context"] = build_project_context(item_id=item_id)
    return item


@router.post("/rescan", response_model=WorkspaceSummary)
def rescan(payload: RescanRequest = Body(default_factory=RescanRequest)):
    try:
        return service.rescan(root=payload.root, max_depth=payload.max_depth)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/discovered/{item_id}/adopt", response_model=WorkspaceItem)
def adopt(item_id: str, payload: AdoptRequest = Body(default_factory=AdoptRequest)):
    item = service.adopt_item(
        item_id,
        priority=payload.priority,
        business_value=payload.business_value,
        status=payload.status,
        tags=payload.tags,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="discovered project not found")
    return item


@router.post("/discovered/{item_id}/ignore", response_model=WorkspaceItem)
def ignore(item_id: str):
    item = service.ignore_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="discovered project not found")
    return item


@router.post("/discovered/{item_id}/unignore", response_model=WorkspaceItem)
def unignore(item_id: str):
    item = service.unignore_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="discovered project not found or not ignored")
    return item


@router.patch("/discovered/{item_id}", response_model=WorkspaceItem)
def update(item_id: str, payload: OverlayUpdate):
    item = service.update_item(item_id, payload.model_dump(exclude_unset=True))
    if item is None:
        raise HTTPException(status_code=404, detail="discovered project not found")
    return item


@router.post("/discovered/{item_id}/notes", response_model=WorkspaceItem)
def add_note(item_id: str, payload: NoteCreate):
    item = service.add_note(item_id, payload.text)
    if item is None:
        raise HTTPException(status_code=404, detail="discovered project not found")
    return item


@router.post("/discovered/{item_id}/resume-work", response_model=ResumeWorkResult)
def resume_work(item_id: str, payload: ResumeWorkRequest = Body(default_factory=ResumeWorkRequest)):
    """§3 (Project Unification): the one primary action every Project page
    exposes. Locates (or, with zero manual creation, starts) the latest AI
    Session for this project's canonical identity, marks it current, builds
    the resume prompt from its latest Snapshot, and resolves where to open
    it -- entirely by calling existing, unmodified `app.projects`
    functionality (see `app.workspace.resume`). 404 if the item was never
    adopted (a canonical identity, and therefore a session, only exists
    for an adopted project).

    Hotfix (Session Intent no-action guard): if ROLE OS cannot derive a
    trustworthy `requested_action`, the result comes back with
    `requires_user_objective=True` and nothing else built -- re-call this
    same endpoint with `payload.user_objective` set once the user has
    answered the Cockpit prompt."""
    user_objective = payload.user_objective.model_dump() if payload.user_objective else None
    result = service.resume_work_for_item(item_id, user_objective=user_objective)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="discovered project not found or not adopted -- adopt it first",
        )
    return result


@router.post("/discovered/{item_id}/launch-claude-code", response_model=LaunchClaudeCodeResult)
def launch_claude_code(item_id: str, payload: LaunchClaudeCodeRequest):
    """Hotfix §4/§7: starts Claude Code in this project's own canonical
    local root -- 404 if the item was never adopted. Any launch failure
    (not Windows, root missing on disk, `Popen` failure) comes back as a
    normal `200` result with `launched: False` and a `message` explaining
    why -- the same "explain, don't 500" convention `app.routers.assets`
    already uses for Open File/Open Folder -- since a failed launch is an
    expected, user-actionable outcome (e.g. Claude Code CLI not on PATH),
    not a server error. Never auto-submits the prompt -- always copies it
    to the clipboard and leaves pasting to the user."""
    result = service.launch_claude_code_for_item(item_id, payload.prompt)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="discovered project not found or not adopted -- adopt it first",
        )
    return result


@router.post("/discovered/{item_id}/override", response_model=WorkspaceItem)
def set_override(item_id: str, payload: OverrideRequest):
    """§8: override the Discovery Engine's computed boundary for this item
    -- "treat as top-level project" or "attach to parent project". Stored
    only in Workspace's own overlay database; the scanned folder and the
    Discovery Engine's own computed `item_kind`/`parent_item_id` are never
    touched (still visible in the response for comparison)."""
    if payload.action not in ("top_level", "attach_to_parent"):
        raise HTTPException(
            status_code=400, detail="action must be 'top_level' or 'attach_to_parent'"
        )
    if payload.action == "attach_to_parent" and not payload.parent_id:
        raise HTTPException(
            status_code=400, detail="parent_id is required when action is 'attach_to_parent'"
        )
    item = service.set_override(item_id, payload.action, payload.parent_id)
    if item is None:
        raise HTTPException(status_code=404, detail="discovered project not found")
    return item


@router.post("/discovered/{item_id}/override/clear", response_model=WorkspaceItem)
def clear_override(item_id: str):
    item = service.clear_override(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="discovered project not found")
    return item


@router.get("/adopted")
def list_adopted():
    """Adopted projects reshaped like `/pi/projects`' response, so the
    Projects page can render manual and discovered projects side by side."""
    return service.list_adopted_as_projects()


# ---------------------------------------------------------------------------
# Sprint 4 (Project Intelligence Wiring): Home, Advisor, Assets, Activity.
# All scoped to *adopted* top-level projects only -- adoption is the
# existing, explicit "yes, track this" signal (§9: excluded folders and
# unadopted discovered folders never feed any of these, by construction,
# since they all build on `list_enriched_top_level_projects(adopted_only=True)`).
# ---------------------------------------------------------------------------


def _embed(
    project_ref: dict[str, Any] | None, contexts_by_item_id: dict[str, dict[str, Any]]
) -> None:
    """`project_ref` here is always a Workspace-item-shaped dict (`id` =
    the discovery item hash, e.g. `service.list_enriched_top_level_
    projects()`'s output) -- contexts must be looked up by
    `ProjectContext.item_id`, not `ProjectContext.id` (which is the
    *canonical* project id once adopted, a different string)."""
    if project_ref and project_ref.get("id") in contexts_by_item_id:
        project_ref["project_context"] = contexts_by_item_id[project_ref["id"]]


@router.get("/home")
def get_home_portfolio():
    """§4: real portfolio signals for the Home page -- last active
    project, most recently modified, projects needing attention, recent
    commits/assets, latest AI session, a suggested project to continue,
    and a Quick Resume action.

    Sprint C1B (Rewiring): every project reference in this response
    (`last_active_project`, `most_recently_modified_project`,
    `suggested_project.project`) carries an embedded `project_context`,
    and `quick_resume` is rebuilt from that same context's canonical
    `next_action`/`resume_state` instead of the ad hoc fields Sprint 4's
    `portfolio.build_home_portfolio` originally computed inline."""
    home = service.get_home_portfolio()
    enriched_items = service.list_enriched_top_level_projects(adopted_only=True)
    contexts = build_project_contexts_for_workspace(enriched_items=enriched_items)
    contexts_by_item_id = {c["item_id"]: c for c in contexts if c.get("item_id")}

    _embed(home.get("last_active_project"), contexts_by_item_id)
    _embed(home.get("most_recently_modified_project"), contexts_by_item_id)
    suggested = home.get("suggested_project")
    if suggested and suggested.get("project"):
        _embed(suggested["project"], contexts_by_item_id)
        context = contexts_by_item_id.get(suggested["project"].get("id"))
        if context and home.get("quick_resume"):
            home["quick_resume"]["action_text"] = (context.get("next_action") or {}).get("text")
            home["quick_resume"]["resume_state"] = context.get("resume_state")
            home["quick_resume"]["project_context"] = context
    for rec in home.get("projects_needing_attention") or []:
        if rec.get("project_id") in contexts_by_item_id:
            rec["project_context"] = contexts_by_item_id[rec["project_id"]]
    return home


@router.get("/advisor")
def get_advisor_recommendations():
    """§5: Workspace Advisor -- rule-based recommendations over real
    discovered-project evidence (git status, docs/tests presence, move
    risk, next-action availability, ...). Every item carries its own
    supporting evidence; nothing is generic filler.

    Sprint C1B (Rewiring): each recommendation carries an embedded
    `project_context` keyed off its `project_id` (the Workspace item id),
    so an Advisor action link resolves to the same canonical resume state
    Home/Cockpit/Project Detail use instead of the recommendation's own
    `action_link` string being the only thing available."""
    recs = service.list_advisor_recommendations()
    enriched_items = service.list_enriched_top_level_projects(adopted_only=True)
    contexts = build_project_contexts_for_workspace(enriched_items=enriched_items)
    contexts_by_id = {c["item_id"]: c for c in contexts if c.get("item_id")}
    for rec in recs:
        if rec.get("project_id") in contexts_by_id:
            rec["project_context"] = contexts_by_id[rec["project_id"]]
    return recs


@router.get("/assets")
def get_assets(project_id: str | None = None):
    """§6: real discovered asset records (no thumbnails yet), grouped by
    project. Pass `project_id` to scope to one project -- restricts the
    filesystem walk to just that project (Sprint C1: Consolidation;
    previously every project was walked regardless, then filtered)."""
    by_project = service.list_project_assets(project_id=project_id)
    if project_id is not None:
        return by_project.get(project_id, [])
    return by_project


@router.get("/activity")
def get_activity(limit: int = 50, project_id: str | None = None):
    """§7: unified recent-activity feed (git commits, filesystem changes,
    adoption events, AI sessions/snapshots, discovered assets), sorted by
    time and deduplicated. Pass `project_id` (Sprint C1: Consolidation) to
    scope to one project -- previously there was no server-side way to do
    this; callers fetched the entire feed and filtered client-side."""
    return service.list_activity_feed(limit=limit, project_id=project_id)
