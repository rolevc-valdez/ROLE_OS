"""Project Identity Reconciliation (Sprint C2.1).

Live verification of Dashboard 2.0 found a real duplicate: "ROLE Commerce
Factory" existed as two separate `projects` rows -- one bridged to a real
discovered folder (`discovery_item_id` set, created automatically at
adoption -- see `app.workspace.identity`), one purely manual (no
`discovery_item_id`, created directly via `POST /pi/projects` at some
point after that folder was already adopted, so Sprint 5's one-time
backward-compat name match in `identity.get_or_create_canonical_project_id`
never had a chance to catch it). This module is the tool that finds and
fixes that class of problem, generally:

- `find_duplicate_candidates()` is read-only -- it only ever *reports*
  evidence, never merges anything, so "do not deduplicate by name
  automatically" holds even when the evidence is strong.
- `merge_projects()` is the only way a merge happens, and it always
  requires the caller to name both the surviving id and the duplicate id
  explicitly -- there is no code path that merges two projects on its own
  initiative. See `app.projects.db.merge_project` for the actual,
  transactional data migration (FK tables, JSON collections,
  `discovery_item_id`); this module adds the one piece of orchestration
  that lives outside the Project Intelligence database: re-syncing the
  Workspace overlay's cached `canonical_project_id` if the discovery link
  moved during the merge.
"""

from __future__ import annotations

import re
from typing import Any

from app.config import Settings, get_settings
from app.projects import db as projects_db
from app.workspace import db as workspace_db
from app.workspace import service as workspace_service


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def _root_path_for(project: dict[str, Any], settings: Settings) -> str | None:
    if not project.get("discovery_item_id"):
        return None
    item = workspace_service.get_item(project["discovery_item_id"], settings=settings)
    return item["root_path"] if item else None


def _git_remote_for(project: dict[str, Any], settings: Settings) -> str | None:
    if not project.get("discovery_item_id"):
        return None
    item = workspace_service.get_item(project["discovery_item_id"], settings=settings)
    if not item:
        return None
    return ((item.get("discovery_detail") or {}).get("git") or {}).get("remote_url") or None


def _evidence_for_pair(
    a: dict[str, Any], b: dict[str, Any], *, settings: Settings
) -> dict[str, Any]:
    """Explainable evidence for one candidate pair -- every signal is
    named and either present or absent, never a single opaque score with
    no way to inspect why. `confidence` is a simple, documented count of
    how many independent signals agree, not a hidden weighting."""
    evidence: list[str] = []

    exact_name = _normalize_name(a["name"]) == _normalize_name(b["name"])
    if exact_name:
        evidence.append(f"normalized exact name match ('{a['name']}' == '{b['name']}')")

    one_discovery_linked = bool(a.get("discovery_item_id")) != bool(b.get("discovery_item_id"))
    both_unlinked_or_linked = bool(a.get("discovery_item_id")) == bool(b.get("discovery_item_id"))
    if one_discovery_linked:
        evidence.append(
            "one project is discovery-linked (has a real folder), the other is purely manual"
        )

    root_a, root_b = _root_path_for(a, settings), _root_path_for(b, settings)
    root_path_match = False
    if root_a and root_b:
        if root_a == root_b:
            root_path_match = True
            evidence.append(f"identical root_path ('{root_a}')")
        elif root_a in root_b or root_b in root_a:
            root_path_match = True
            evidence.append(f"related root_path ('{root_a}' vs '{root_b}')")

    remote_a, remote_b = _git_remote_for(a, settings), _git_remote_for(b, settings)
    remote_match = bool(remote_a) and remote_a == remote_b
    if remote_match:
        evidence.append(f"identical git remote ('{remote_a}')")

    same_workspace = a.get("workspace") == b.get("workspace")
    if same_workspace:
        evidence.append(f"same workspace ('{a.get('workspace')}')")

    already_linked_pair = (
        a.get("discovery_item_id")
        and b.get("discovery_item_id")
        and a["discovery_item_id"] == b["discovery_item_id"]
    )
    if already_linked_pair:
        evidence.append(
            "both rows already resolve to the same discovery item (data-entry duplicate)"
        )

    signals = [
        exact_name,
        root_path_match,
        remote_match,
        one_discovery_linked or already_linked_pair,
    ]
    confidence = sum(1 for s in signals if s)

    # Two independently-created manual projects sharing only a name and a
    # workspace, with no discovery/root-path/remote signal at all, is weak
    # evidence -- explicitly named as such rather than silently omitted.
    if not evidence:
        evidence.append("no matching evidence found")
    elif exact_name and confidence == 1 and both_unlinked_or_linked and not remote_match:
        evidence.append("WEAK: name match only -- no root_path/remote/discovery-link corroboration")

    return {
        "evidence": evidence,
        "confidence": confidence,
        "exact_name_match": exact_name,
        "root_path_match": root_path_match,
        "git_remote_match": remote_match,
        "same_workspace": same_workspace,
        "one_discovery_linked": one_discovery_linked,
    }


def find_duplicate_candidates(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Read-only. Returns every pair of active (non-merged) Projects with
    at least a normalized-exact-name match, each annotated with
    explainable evidence and a `suggested_survivor_id` (the discovery-
    linked side, when exactly one side is linked -- ties/no-link pairs
    leave it `None`, requiring a human to choose). Never merges anything;
    never even ranks a pair as "safe to auto-merge" -- see
    `merge_projects` for the only place a merge actually happens, always
    on an explicit, named pair."""
    settings = settings or get_settings()
    projects = projects_db.list_projects(include_merged=False, settings=settings)

    by_name: dict[str, list[dict[str, Any]]] = {}
    for project in projects:
        by_name.setdefault(_normalize_name(project["name"]), []).append(project)

    candidates = []
    for _name, group in by_name.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                evidence = _evidence_for_pair(a, b, settings=settings)
                suggested_survivor_id = None
                if evidence["one_discovery_linked"]:
                    suggested_survivor_id = a["id"] if a.get("discovery_item_id") else b["id"]
                candidates.append(
                    {
                        "project_a": {
                            "id": a["id"],
                            "name": a["name"],
                            "workspace": a.get("workspace"),
                        },
                        "project_b": {
                            "id": b["id"],
                            "name": b["name"],
                            "workspace": b.get("workspace"),
                        },
                        "suggested_survivor_id": suggested_survivor_id,
                        **evidence,
                    }
                )
    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates


def merge_projects(
    surviving_id: str, duplicate_id: str, settings: Settings | None = None
) -> dict[str, Any]:
    """The only function that actually merges two projects -- always
    requires an explicit, human/caller-named `(surviving_id, duplicate_id)`
    pair (see `routers/pi/reconciliation.py`'s `confirm: true` requirement
    at the API layer). Delegates the transactional data migration to
    `app.projects.db.merge_project`, then re-syncs the Workspace overlay's
    cached `canonical_project_id` if `discovery_item_id` moved onto the
    survivor as part of that merge (i.e. the duplicate was the discovery-
    linked side) -- without this, `app.workspace.identity` would still
    resolve that item to the now-merged-away duplicate id."""
    settings = settings or get_settings()
    result = projects_db.merge_project(surviving_id, duplicate_id, settings=settings)

    summary = result.pop("_merge_summary")
    moved_item_id = summary.get("moved_discovery_item_id")
    if moved_item_id:
        overlay = workspace_db.get_overlay(moved_item_id, settings=settings)
        root_path = overlay["root_path"] if overlay else None
        if root_path:
            workspace_db.set_canonical_project_id(moved_item_id, root_path, surviving_id, settings)

    return {"project": result, **summary}
