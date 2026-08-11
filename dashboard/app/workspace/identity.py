"""Canonical Project Identity (Sprint 5: Project Unification).

The bridge between Workspace/Discovery (keyed by a `sha1(root_path)`
item id) and Project Intelligence / AI Sessions / Timeline (keyed by a
real `projects.id`). For the user there is only one concept, "Project" --
this module is what makes that true underneath: every adopted Workspace
item resolves to (or gets) a real row in `role_os_projects.db`, so AI
Sessions, Snapshots, and the Timeline work for it with **zero** rewrite of
`app.projects` -- they simply operate on a real project id, the same as
they always have for a manually-created Project.

Never destroys or overwrites existing Project data: an existing manually-
created Project is only ever *linked* (one nullable column set), never
renamed, restructured, or deleted. A brand-new Project created here is
deliberately minimal -- name + a "Discovered" workspace bucket -- because
all the rich data (git, health, docs, tests, ...) already lives in the
Workspace scan cache and must never be duplicated into it (the same rule
Sprint 2 established for the overlay table).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.config import Settings, get_settings
from app.projects import db as projects_db
from app.workspace import db

DISCOVERED_WORKSPACE_NAME = "Discovered"


def get_or_create_canonical_project_id(
    item_id: str, root_path: str, item_name: str, settings: Settings | None = None
) -> str:
    """Resolves (or creates) the canonical `projects.id` for a discovered
    item. Idempotent and self-healing:

    1. If the overlay already has a `canonical_project_id` that still
       resolves to a real Project, return it unchanged.
    2. Else, check `projects.discovery_item_id` directly -- the two
       databases (`role_os_workspace.db`'s overlay cache and
       `role_os_projects.db`) are independently owned and can drift out
       of sync with each other (e.g. one gets reset/restored without the
       other); the `projects` table is the source of truth for "is this
       item already linked," not the overlay's cached copy of the answer.
       If found, re-sync the overlay and return it.
    3. Else, look for an existing *unlinked* manually-created Project with
       the exact same name (§7's backward-compatibility migration) and
       link it instead of creating a duplicate.
    4. Else, create a new minimal Project (name + "Discovered" workspace)
       and link it.

    Safe to call on every adopt, and on every read of an already-adopted
    item -- steps 2-4 only ever run once per item, after which step 1
    short-circuits everything.
    """
    settings = settings or get_settings()

    overlay = db.get_overlay(item_id, settings)
    existing_link = overlay.get("canonical_project_id") if overlay else None
    if existing_link:
        # `get_project` (Sprint C2.1) transparently follows a merge, so
        # `project["id"]` may differ from `existing_link` if the Project
        # this overlay used to point at has since been merged into
        # another one -- re-sync the cached link to the survivor so every
        # later read is a direct hit, not a redirect through `get_project`
        # every time.
        project = projects_db.get_project(existing_link, settings)
        if project is not None:
            if project["id"] != existing_link:
                db.set_canonical_project_id(item_id, root_path, project["id"], settings)
            return project["id"]
        # Stale link (the Project row was deleted out-of-band) -- fall
        # through and resolve a fresh one rather than returning a
        # dangling id.

    already_linked = projects_db.get_project_by_discovery_item_id(item_id, settings)
    if already_linked is not None:
        db.set_canonical_project_id(item_id, root_path, already_linked["id"], settings)
        return already_linked["id"]

    match = projects_db.find_unlinked_project_by_name(item_name, settings)
    if match is not None:
        try:
            projects_db.link_project_to_discovery_item(match["id"], item_id, settings)
        except sqlite3.IntegrityError:
            # `discovery_item_id` is unique, but `name` is not: another
            # project (a duplicate-named one) already holds this item_id
            # despite the check above -- a concurrent write. The name
            # match was a false positive; fall through to minting a fresh
            # minimal project rather than crashing the caller.
            pass
        else:
            db.set_canonical_project_id(item_id, root_path, match["id"], settings)
            return match["id"]

    created = projects_db.create_project(
        name=item_name, workspace=DISCOVERED_WORKSPACE_NAME, settings=settings
    )
    try:
        projects_db.link_project_to_discovery_item(created["id"], item_id, settings)
    except sqlite3.IntegrityError:
        # Another concurrent call linked this exact item_id in the
        # window since we checked -- re-resolve to that winner rather
        # than leaving an orphaned, unlinked Project row behind.
        winner = projects_db.get_project_by_discovery_item_id(item_id, settings)
        if winner is not None:
            db.set_canonical_project_id(item_id, root_path, winner["id"], settings)
            return winner["id"]
        raise
    db.set_canonical_project_id(item_id, root_path, created["id"], settings)
    return created["id"]


def get_canonical_project_id(item_id: str, settings: Settings | None = None) -> str | None:
    """Read-only lookup -- never creates one, never writes the overlay's
    resync (unlike `get_or_create_canonical_project_id` above). Used
    anywhere that must not have the side effect of minting a new Project
    (e.g. rendering the flat discovered list). Still resolves through a
    merge (Sprint C2.1): `get_project` follows `merged_into_project_id`,
    so this always returns the *surviving* id, never a merged-away one."""
    settings = settings or get_settings()
    overlay = db.get_overlay(item_id, settings)
    if not overlay or not overlay.get("canonical_project_id"):
        return None
    project = projects_db.get_project(overlay["canonical_project_id"], settings)
    return project["id"] if project is not None else None


def get_canonical_project(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    project_id = get_canonical_project_id(item_id, settings)
    return projects_db.get_project(project_id, settings) if project_id else None
