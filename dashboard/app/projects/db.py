"""SQLite persistence layer for the Project Intelligence domain (Epic 1).

Owns its own database file (see `Settings.projects_db_path`), separate from
the builder-generated knowledge database. Schema creation is idempotent and
runs automatically on every connection, so no manual migration step is
required — the database and default workspaces are created on first use.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

DEFAULT_WORKSPACES = ["Personal", "Kontoor", "Unger", "Products", "Ideas", "Library"]

# Project fields that are stored as simple JSON-list-of-object collections
# and share identical CRUD behavior (add/list/update/delete an item with an
# id, created_at, and free-form fields).
COLLECTION_FIELDS = ("notes", "decisions", "todos", "deliverables", "assets", "prompts")

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    health_score INTEGER DEFAULT 0,
    priority TEXT DEFAULT 'medium',
    tags TEXT NOT NULL DEFAULT '[]',
    owner TEXT DEFAULT '',
    notes TEXT NOT NULL DEFAULT '[]',
    decisions TEXT NOT NULL DEFAULT '[]',
    todos TEXT NOT NULL DEFAULT '[]',
    deliverables TEXT NOT NULL DEFAULT '[]',
    assets TEXT NOT NULL DEFAULT '[]',
    prompts TEXT NOT NULL DEFAULT '[]',
    conversations TEXT NOT NULL DEFAULT '[]',
    related_projects TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_workspace ON projects(workspace_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

CREATE TABLE IF NOT EXISTS capabilities (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_capabilities_project ON capabilities(project_id);

CREATE TABLE IF NOT EXISTS capability_consumers (
    id TEXT PRIMARY KEY,
    capability_id TEXT NOT NULL REFERENCES capabilities(id),
    consumer_project_id TEXT NOT NULL REFERENCES projects(id),
    created_at TEXT NOT NULL,
    UNIQUE(capability_id, consumer_project_id)
);
CREATE INDEX IF NOT EXISTS idx_consumers_capability ON capability_consumers(capability_id);
CREATE INDEX IF NOT EXISTS idx_consumers_project ON capability_consumers(consumer_project_id);

CREATE TABLE IF NOT EXISTS dependencies (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    depends_on_project_id TEXT NOT NULL REFERENCES projects(id),
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(project_id, depends_on_project_id)
);
CREATE INDEX IF NOT EXISTS idx_deps_project ON dependencies(project_id);
CREATE INDEX IF NOT EXISTS idx_deps_depends_on ON dependencies(depends_on_project_id);

CREATE TABLE IF NOT EXISTS ai_workspace (
    project_id TEXT PRIMARY KEY REFERENCES projects(id),
    claude_url TEXT NOT NULL DEFAULT '',
    chatgpt_url TEXT NOT NULL DEFAULT '',
    gemini_url TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    preferred_model TEXT NOT NULL DEFAULT '',
    last_opened_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    title TEXT NOT NULL DEFAULT '',
    assistant TEXT NOT NULL,
    conversation_url TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    preferred_model TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    last_used_at TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    favorite INTEGER NOT NULL DEFAULT 0,
    current INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_sessions_project ON ai_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_ai_sessions_assistant ON ai_sessions(project_id, assistant);

CREATE TABLE IF NOT EXISTS ai_session_snapshots (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES ai_sessions(id),
    accomplishments TEXT NOT NULL DEFAULT '',
    blockers TEXT NOT NULL DEFAULT '',
    pending_work TEXT NOT NULL DEFAULT '',
    next_prompt TEXT NOT NULL DEFAULT '',
    decisions TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_session ON ai_session_snapshots(session_id);

CREATE TABLE IF NOT EXISTS schema_migrations (
    id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def _migrate_ai_workspace_to_sessions(conn: sqlite3.Connection) -> None:
    """v1.4 (Context Engine): copies every non-empty URL from the v1.3
    `ai_workspace` single-record-per-project table into the new
    `ai_sessions` collection, one session per assistant that had a saved
    URL. Copies, never moves or deletes -- `ai_workspace` and its API
    (`app.routers.pi.ai_workspace`) are left fully intact and functional,
    per this migration's explicit "preserve AI Workspace URLs, keep
    existing API contracts" requirement. Runs at most once per database
    (tracked in `schema_migrations`), so it is safe even though
    `ensure_schema` runs on every connection.
    """
    ts = now_iso()
    rows = conn.execute("SELECT * FROM ai_workspace").fetchall()
    for row in rows:
        for assistant, url_col in (
            ("claude", "claude_url"),
            ("chatgpt", "chatgpt_url"),
            ("gemini", "gemini_url"),
        ):
            url = (row[url_col] or "").strip()
            if not url:
                continue
            conn.execute(
                """
                INSERT INTO ai_sessions (
                    id, project_id, title, assistant, conversation_url, role,
                    preferred_model, started_at, last_used_at, status, favorite,
                    current, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, 1, ?, ?, ?)
                """,
                (
                    new_id(),
                    row["project_id"],
                    f"Migrated {assistant} conversation",
                    assistant,
                    url,
                    row["role"] or "",
                    row["preferred_model"] or "",
                    row["created_at"] or ts,
                    row["last_opened_at"],
                    "Migrated from AI Workspace (v1.3) on upgrade to Context Engine (v1.4).",
                    row["created_at"] or ts,
                    ts,
                ),
            )


# Ordered, named migrations. Each runs at most once per database file,
# tracked by id in `schema_migrations` -- add new entries here, never
# rewrite or reorder an existing one (same "append, never rewrite"
# discipline as `role-ecosystem/DECISION_LOG.md`).
MIGRATIONS: tuple[tuple[str, Any], ...] = (
    ("0001_ai_sessions_from_ai_workspace", _migrate_ai_workspace_to_sessions),
)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    applied = {row["id"] for row in conn.execute("SELECT id FROM schema_migrations")}
    for migration_id, migrate_fn in MIGRATIONS:
        if migration_id in applied:
            continue
        migrate_fn(conn)
        conn.execute(
            "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
            (migration_id, now_iso()),
        )
        conn.commit()


# Sprint 5 (Project Unification): the canonical-identity bridge column --
# nullable, set only for a Project that is (or was auto-created for) an
# adopted Workspace item. `ALTER TABLE ... ADD COLUMN` has no "IF NOT
# EXISTS" in SQLite, so this is wrapped and the "duplicate column" error
# swallowed, same idempotent pattern as `app.workspace.db`'s Sprint 3
# overlay columns -- safe on both a fresh database and an existing one.
_SPRINT5_COLUMNS = (
    ("discovery_item_id", "ALTER TABLE projects ADD COLUMN discovery_item_id TEXT"),
)

# Sprint C2.1 (Project Identity Reconciliation): nullable, set only on a
# Project row that has been merged into another (the surviving) Project --
# never deleted, so its notes/decisions/todos/deliverables/prompts/AI
# Sessions/Snapshots/capabilities/dependencies remain inspectable even
# after `merge_project()` migrates the *active* references to the
# survivor. Same idempotent "ALTER TABLE, swallow duplicate-column error"
# pattern as `_SPRINT5_COLUMNS` above.
_SPRINT_C2_1_COLUMNS = (
    (
        "merged_into_project_id",
        "ALTER TABLE projects ADD COLUMN merged_into_project_id TEXT",
    ),
)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for _column, ddl in _SPRINT5_COLUMNS:
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists
    for _column, ddl in _SPRINT_C2_1_COLUMNS:
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_discovery_item ON projects(discovery_item_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_merged_into ON projects(merged_into_project_id)"
    )
    row = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()
    if row[0] == 0:
        ts = now_iso()
        conn.executemany(
            "INSERT INTO workspaces (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            [(new_id(), name, "", ts, ts) for name in DEFAULT_WORKSPACES],
        )
    conn.commit()
    _apply_migrations(conn)


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path: Path = settings.projects_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------


def _workspace_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_workspaces(settings: Settings | None = None) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute("SELECT * FROM workspaces ORDER BY name").fetchall()
        result = []
        for row in rows:
            data = _workspace_row_to_dict(row)
            count = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE workspace_id = ?", (row["id"],)
            ).fetchone()[0]
            data["project_count"] = count
            result.append(data)
        return result


def get_workspace(workspace_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    return _workspace_row_to_dict(row) if row else None


def get_workspace_by_name(name: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM workspaces WHERE name = ?", (name,)).fetchone()
    return _workspace_row_to_dict(row) if row else None


def create_workspace(
    name: str, description: str = "", settings: Settings | None = None
) -> dict[str, Any]:
    ts = now_iso()
    workspace_id = new_id()
    with get_connection(settings) as conn:
        conn.execute(
            "INSERT INTO workspaces (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (workspace_id, name, description, ts, ts),
        )
        conn.commit()
    return get_workspace(workspace_id, settings)


def get_or_create_workspace(name: str, settings: Settings | None = None) -> dict[str, Any]:
    existing = get_workspace_by_name(name, settings)
    if existing:
        return existing
    return create_workspace(name, settings=settings)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

_PROJECT_JSON_FIELDS = (
    "tags",
    "notes",
    "decisions",
    "todos",
    "deliverables",
    "assets",
    "prompts",
    "conversations",
    "related_projects",
)


def _project_row_to_dict(row: sqlite3.Row, workspace_name: str | None = None) -> dict[str, Any]:
    data = dict(row)
    for field in _PROJECT_JSON_FIELDS:
        data[field] = json.loads(data[field]) if data.get(field) else []
    if workspace_name is not None:
        data["workspace"] = workspace_name
    return data


def _fetch_project_row(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def create_project(
    *,
    name: str,
    workspace: str,
    description: str = "",
    status: str = "active",
    priority: str = "medium",
    tags: list[str] | None = None,
    owner: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    ws = get_or_create_workspace(workspace, settings)
    ts = now_iso()
    project_id = new_id()
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO projects (
                id, workspace_id, name, description, status, health_score, priority,
                tags, owner, notes, decisions, todos, deliverables, assets, prompts,
                conversations, related_projects, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, '[]', '[]', '[]', '[]', '[]', '[]', '[]', '[]', ?, ?)
            """,
            (
                project_id,
                ws["id"],
                name,
                description,
                status,
                priority,
                json.dumps(tags or []),
                owner,
                ts,
                ts,
            ),
        )
        conn.commit()
    return get_project(project_id, settings)


def get_project(
    project_id: str, settings: Settings | None = None, *, follow_merge: bool = True
) -> dict[str, Any] | None:
    """`follow_merge` (Sprint C2.1): if `project_id` names a Project that
    has since been merged into another (surviving) Project, transparently
    returns the *survivor's* data instead -- the same "merged identities
    always resolve to the surviving canonical project" contract
    `ProjectContext`/`app.workspace.identity` rely on. Pass `follow_merge=
    False` only when you specifically need the raw, as-stored row for a
    project id that might itself be a merged-away duplicate (e.g.
    `merge_project`'s own bookkeeping)."""
    with get_connection(settings) as conn:
        row = _fetch_project_row(conn, project_id)
        if not row:
            return None
        if follow_merge and row["merged_into_project_id"]:
            survivor_row = _fetch_project_row(conn, row["merged_into_project_id"])
            if survivor_row is not None:
                row = survivor_row
        ws_row = conn.execute(
            "SELECT name FROM workspaces WHERE id = ?", (row["workspace_id"],)
        ).fetchone()
    return _project_row_to_dict(row, ws_row["name"] if ws_row else None)


# ---------------------------------------------------------------------------
# Sprint 5 (Project Unification): the canonical-identity bridge. A Project
# row can optionally be linked to a Workspace-discovered item id
# (`discovery_item_id`) -- see `app.workspace.identity`, which is the only
# caller that creates or resolves this link. This module only exposes the
# plain lookups/writes; it has no knowledge of Workspace/Discovery itself.
# ---------------------------------------------------------------------------


def get_project_by_discovery_item_id(
    item_id: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE discovery_item_id = ?", (item_id,)
        ).fetchone()
    return get_project(row["id"], settings) if row else None


def find_unlinked_project_by_name(
    name: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    """Sprint 5 §7 backward-compatibility: a conservative migration match
    for an existing manually-created Project that likely *is* a discovered
    folder, found by exact (case-insensitive) name -- only ever offered to
    a Project that isn't already linked to a different discovered item, so
    this can never steal or overwrite an existing link."""
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE discovery_item_id IS NULL AND lower(name) = lower(?) LIMIT 1",
            (name,),
        ).fetchone()
    return get_project(row["id"], settings) if row else None


def link_project_to_discovery_item(
    project_id: str, item_id: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        if not _fetch_project_row(conn, project_id):
            return None
        conn.execute(
            "UPDATE projects SET discovery_item_id = ?, updated_at = ? WHERE id = ?",
            (item_id, now_iso(), project_id),
        )
        conn.commit()
    return get_project(project_id, settings)


def list_projects(
    *,
    workspace: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    priority: str | None = None,
    include_merged: bool = False,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """`include_merged` (Sprint C2.1): a Project merged into another one
    (`merged_into_project_id` set) is excluded by default -- it is kept,
    never deleted, but is no longer an *active* identity, so Dashboard/
    Projects/Advisor/Cockpit each show a merged pair once, not twice. Pass
    `include_merged=True` for reconciliation tooling that needs to see
    every row, merged or not."""
    query = "SELECT projects.*, workspaces.name AS workspace_name FROM projects JOIN workspaces ON projects.workspace_id = workspaces.id WHERE 1=1"
    params: list[Any] = []
    if not include_merged:
        query += " AND projects.merged_into_project_id IS NULL"
    if workspace:
        query += " AND workspaces.name = ?"
        params.append(workspace)
    if status:
        query += " AND projects.status = ?"
        params.append(status)
    if priority:
        query += " AND projects.priority = ?"
        params.append(priority)
    query += " ORDER BY projects.updated_at DESC"

    with get_connection(settings) as conn:
        rows = conn.execute(query, params).fetchall()

    projects = []
    for row in rows:
        data = _project_row_to_dict(row, row["workspace_name"])
        if tag and tag not in data["tags"]:
            continue
        projects.append(data)
    return projects


class MergeError(ValueError):
    """Raised by `merge_project` for any precondition failure -- never
    partially applied; the caller's transaction is rolled back before this
    is raised."""


_COLLECTION_MERGE_FIELDS = (
    "notes",
    "decisions",
    "todos",
    "deliverables",
    "assets",
    "prompts",
)


def _merge_json_collections(
    survivor_row: sqlite3.Row, duplicate_row: sqlite3.Row
) -> dict[str, str]:
    """Union-merges each JSON-list collection field (deduped by item `id`)
    plus `tags`/`conversations`/`related_projects` (deduped by value).
    Returns `{field: json_string}` for every field that changed, ready to
    splice into an `UPDATE projects SET ...` -- the duplicate row's own
    copies are left completely untouched (it is never deleted), so this is
    additive only: nothing the survivor already had is removed.
    """
    updates: dict[str, str] = {}

    for field in _COLLECTION_MERGE_FIELDS:
        survivor_items = json.loads(survivor_row[field] or "[]")
        duplicate_items = json.loads(duplicate_row[field] or "[]")
        if not duplicate_items:
            continue
        seen_ids = {item.get("id") for item in survivor_items if isinstance(item, dict)}
        merged = list(survivor_items) + [
            item
            for item in duplicate_items
            if not (isinstance(item, dict) and item.get("id") in seen_ids)
        ]
        if len(merged) != len(survivor_items):
            updates[field] = json.dumps(merged)

    for field in ("tags", "conversations", "related_projects"):
        survivor_values = json.loads(survivor_row[field] or "[]")
        duplicate_values = json.loads(duplicate_row[field] or "[]")
        merged_values = list(survivor_values)
        for value in duplicate_values:
            if value not in merged_values and value not in (
                survivor_row["id"],
                duplicate_row["id"],
            ):
                merged_values.append(value)
        if merged_values != survivor_values:
            updates[field] = json.dumps(merged_values)

    for field in ("description", "owner"):
        if not (survivor_row[field] or "").strip() and (duplicate_row[field] or "").strip():
            updates[field] = duplicate_row[field]

    return updates


def merge_project(
    surviving_id: str, duplicate_id: str, settings: Settings | None = None
) -> dict[str, Any]:
    """Sprint C2.1 (Project Identity Reconciliation): merges `duplicate_id`
    into `surviving_id`. Never destructive -- the duplicate Project row is
    never deleted, only marked `merged_into_project_id`; every FK-
    referencing table (`ai_sessions` and therefore all of its Snapshots,
    `capabilities`, `capability_consumers`, `dependencies`) is migrated to
    point at the survivor so AI Sessions/Snapshots/capabilities/
    dependencies are never lost or orphaned; the embedded JSON collections
    (notes/decisions/todos/deliverables/assets/prompts/tags/conversations/
    related_projects) are union-merged onto the survivor (additive,
    deduped by item id or value); `discovery_item_id` migrates to the
    survivor only if the survivor doesn't already have one (so merging a
    discovery-linked duplicate into a manual survivor still preserves the
    Workspace bridge -- the caller, `app.workspace.reconciliation`, is
    responsible for re-syncing the Workspace overlay's cached
    `canonical_project_id` afterward if this happens).

    Entirely one transaction: any failure raises and leaves the database
    exactly as it was (`conn.rollback()`), never a half-migrated state.

    Raises `MergeError` if either id doesn't exist, they're the same id,
    the duplicate is already merged (into anything), or the survivor is
    itself a merged-away duplicate -- merge chains are deliberately
    disallowed (always merge into a live, "active" identity) to keep
    resolution a single hop.
    """
    if surviving_id == duplicate_id:
        raise MergeError("cannot merge a project into itself")

    with get_connection(settings) as conn:
        try:
            survivor_row = _fetch_project_row(conn, surviving_id)
            duplicate_row = _fetch_project_row(conn, duplicate_id)
            if survivor_row is None:
                raise MergeError(f"surviving project '{surviving_id}' not found")
            if duplicate_row is None:
                raise MergeError(f"duplicate project '{duplicate_id}' not found")
            if duplicate_row["merged_into_project_id"]:
                raise MergeError(
                    f"'{duplicate_id}' is already merged into "
                    f"'{duplicate_row['merged_into_project_id']}' -- cannot merge it again"
                )
            if survivor_row["merged_into_project_id"]:
                raise MergeError(
                    f"'{surviving_id}' is itself merged into "
                    f"'{survivor_row['merged_into_project_id']}' -- merge into that project instead"
                )

            ts = now_iso()
            migrated: dict[str, int] = {}

            cur = conn.execute(
                "UPDATE ai_sessions SET project_id = ? WHERE project_id = ?",
                (surviving_id, duplicate_id),
            )
            migrated["ai_sessions"] = cur.rowcount

            cur = conn.execute(
                "UPDATE capabilities SET project_id = ? WHERE project_id = ?",
                (surviving_id, duplicate_id),
            )
            migrated["capabilities"] = cur.rowcount

            # capability_consumers/dependencies both carry a UNIQUE
            # constraint that a blanket UPDATE could violate if the
            # survivor already has an equivalent row -- migrate row by
            # row, dropping only the exact duplicate-of-duplicate link
            # (never a capability/dependency itself) when that happens.
            consumer_rows = conn.execute(
                "SELECT * FROM capability_consumers WHERE consumer_project_id = ?", (duplicate_id,)
            ).fetchall()
            migrated["capability_consumers"] = 0
            for row in consumer_rows:
                try:
                    conn.execute(
                        "UPDATE capability_consumers SET consumer_project_id = ? WHERE id = ?",
                        (surviving_id, row["id"]),
                    )
                    migrated["capability_consumers"] += 1
                except sqlite3.IntegrityError:
                    conn.execute("DELETE FROM capability_consumers WHERE id = ?", (row["id"],))

            dep_rows = conn.execute(
                "SELECT * FROM dependencies WHERE project_id = ? OR depends_on_project_id = ?",
                (duplicate_id, duplicate_id),
            ).fetchall()
            migrated["dependencies"] = 0
            for row in dep_rows:
                new_project_id = (
                    surviving_id if row["project_id"] == duplicate_id else row["project_id"]
                )
                new_depends_on = (
                    surviving_id
                    if row["depends_on_project_id"] == duplicate_id
                    else row["depends_on_project_id"]
                )
                if new_project_id == new_depends_on:
                    # Would become a self-dependency once both sides
                    # resolve to the survivor -- drop it rather than
                    # create a nonsensical edge.
                    conn.execute("DELETE FROM dependencies WHERE id = ?", (row["id"],))
                    continue
                try:
                    conn.execute(
                        "UPDATE dependencies SET project_id = ?, depends_on_project_id = ? WHERE id = ?",
                        (new_project_id, new_depends_on, row["id"]),
                    )
                    migrated["dependencies"] += 1
                except sqlite3.IntegrityError:
                    conn.execute("DELETE FROM dependencies WHERE id = ?", (row["id"],))

            # ai_workspace: PK is project_id, at most one row per project.
            # If only the duplicate has one, move it outright; if both
            # have one, fill in any blank field on the survivor's row from
            # the duplicate's (never overwrite a non-empty value), then
            # leave the duplicate's own row in place (harmless -- it is
            # keyed to a project id that still exists, just no longer
            # "active"; nothing here is deleted).
            survivor_workspace = conn.execute(
                "SELECT * FROM ai_workspace WHERE project_id = ?", (surviving_id,)
            ).fetchone()
            duplicate_workspace = conn.execute(
                "SELECT * FROM ai_workspace WHERE project_id = ?", (duplicate_id,)
            ).fetchone()
            migrated["ai_workspace"] = 0
            if duplicate_workspace is not None and survivor_workspace is None:
                conn.execute(
                    "UPDATE ai_workspace SET project_id = ? WHERE project_id = ?",
                    (surviving_id, duplicate_id),
                )
                migrated["ai_workspace"] = 1
            elif duplicate_workspace is not None and survivor_workspace is not None:
                fill_clauses, fill_params = [], []
                for field in ("claude_url", "chatgpt_url", "gemini_url", "role", "preferred_model"):
                    if (
                        not (survivor_workspace[field] or "").strip()
                        and (duplicate_workspace[field] or "").strip()
                    ):
                        fill_clauses.append(f"{field} = ?")
                        fill_params.append(duplicate_workspace[field])
                if fill_clauses:
                    fill_clauses.append("updated_at = ?")
                    fill_params.extend([ts, surviving_id])
                    conn.execute(
                        f"UPDATE ai_workspace SET {', '.join(fill_clauses)} WHERE project_id = ?",
                        fill_params,
                    )
                    migrated["ai_workspace"] = 1

            # discovery_item_id: only migrate onto the survivor if it
            # doesn't already have one -- never overwrite an existing
            # Workspace bridge.
            moved_discovery_item_id = None
            if duplicate_row["discovery_item_id"] and not survivor_row["discovery_item_id"]:
                moved_discovery_item_id = duplicate_row["discovery_item_id"]
                conn.execute(
                    "UPDATE projects SET discovery_item_id = ? WHERE id = ?",
                    (moved_discovery_item_id, surviving_id),
                )

            collection_updates = _merge_json_collections(survivor_row, duplicate_row)
            if collection_updates:
                set_clauses = [f"{field} = ?" for field in collection_updates]
                params = list(collection_updates.values())
                params.append(surviving_id)
                conn.execute(f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?", params)

            conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (ts, surviving_id))
            conn.execute(
                "UPDATE projects SET merged_into_project_id = ?, updated_at = ? WHERE id = ?",
                (surviving_id, ts, duplicate_id),
            )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

    result = get_project(surviving_id, settings)
    result["_merge_summary"] = {
        "duplicate_id": duplicate_id,
        "migrated": migrated,
        "moved_discovery_item_id": moved_discovery_item_id,
        "collection_fields_merged": list(collection_updates.keys()),
    }
    return result


def update_project(
    project_id: str, patch: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any] | None:
    allowed = {"name", "description", "status", "priority", "owner"}
    set_clauses = []
    params: list[Any] = []

    with get_connection(settings) as conn:
        if not _fetch_project_row(conn, project_id):
            return None

        for field in allowed:
            if field in patch:
                set_clauses.append(f"{field} = ?")
                params.append(patch[field])
        if "tags" in patch:
            set_clauses.append("tags = ?")
            params.append(json.dumps(patch["tags"]))
        if "workspace" in patch:
            ws = get_or_create_workspace(patch["workspace"], settings)
            set_clauses.append("workspace_id = ?")
            params.append(ws["id"])

        if set_clauses:
            set_clauses.append("updated_at = ?")
            params.append(now_iso())
            params.append(project_id)
            conn.execute(f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?", params)
            conn.commit()

    return get_project(project_id, settings)


def delete_project(project_id: str, settings: Settings | None = None) -> bool:
    with get_connection(settings) as conn:
        if not _fetch_project_row(conn, project_id):
            return False
        conn.execute(
            "DELETE FROM capability_consumers WHERE consumer_project_id = ?", (project_id,)
        )
        conn.execute(
            "DELETE FROM capability_consumers WHERE capability_id IN (SELECT id FROM capabilities WHERE project_id = ?)",
            (project_id,),
        )
        conn.execute("DELETE FROM capabilities WHERE project_id = ?", (project_id,))
        conn.execute(
            "DELETE FROM dependencies WHERE project_id = ? OR depends_on_project_id = ?",
            (project_id, project_id),
        )
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    return True


def set_health_score(project_id: str, score: int, settings: Settings | None = None) -> None:
    # Deliberately does NOT touch updated_at: recalculating the score is not
    # itself "activity" on the project, and the activity signal would
    # otherwise be gameable by just re-running the health check.
    with get_connection(settings) as conn:
        conn.execute("UPDATE projects SET health_score = ? WHERE id = ?", (score, project_id))
        conn.commit()


# ---------------------------------------------------------------------------
# Generic JSON-list collections (notes, decisions, todos, deliverables,
# assets, prompts)
# ---------------------------------------------------------------------------


def add_collection_item(
    project_id: str, field: str, item: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any] | None:
    assert field in COLLECTION_FIELDS, f"unknown collection field: {field}"
    with get_connection(settings) as conn:
        row = _fetch_project_row(conn, project_id)
        if not row:
            return None
        items = json.loads(row[field]) if row[field] else []
        record = {"id": new_id(), "created_at": now_iso(), **item}
        items.append(record)
        conn.execute(
            f"UPDATE projects SET {field} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(items), now_iso(), project_id),
        )
        conn.commit()
    return record


def list_collection_items(
    project_id: str, field: str, settings: Settings | None = None
) -> list[dict[str, Any]] | None:
    assert field in COLLECTION_FIELDS, f"unknown collection field: {field}"
    with get_connection(settings) as conn:
        row = _fetch_project_row(conn, project_id)
        if not row:
            return None
        return json.loads(row[field]) if row[field] else []


def update_collection_item(
    project_id: str,
    field: str,
    item_id: str,
    patch: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    assert field in COLLECTION_FIELDS, f"unknown collection field: {field}"
    with get_connection(settings) as conn:
        row = _fetch_project_row(conn, project_id)
        if not row:
            return None
        items = json.loads(row[field]) if row[field] else []
        updated = None
        for item in items:
            if item.get("id") == item_id:
                item.update(patch)
                updated = item
                break
        if updated is None:
            return None
        conn.execute(
            f"UPDATE projects SET {field} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(items), now_iso(), project_id),
        )
        conn.commit()
    return updated


def delete_collection_item(
    project_id: str, field: str, item_id: str, settings: Settings | None = None
) -> bool:
    assert field in COLLECTION_FIELDS, f"unknown collection field: {field}"
    with get_connection(settings) as conn:
        row = _fetch_project_row(conn, project_id)
        if not row:
            return False
        items = json.loads(row[field]) if row[field] else []
        remaining = [i for i in items if i.get("id") != item_id]
        if len(remaining) == len(items):
            return False
        conn.execute(
            f"UPDATE projects SET {field} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(remaining), now_iso(), project_id),
        )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Conversations and related-projects links (simple id lists)
# ---------------------------------------------------------------------------


def _link_id(
    project_id: str, field: str, value: str, settings: Settings | None
) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = _fetch_project_row(conn, project_id)
        if not row:
            return None
        items = json.loads(row[field]) if row[field] else []
        if value not in items:
            items.append(value)
            conn.execute(
                f"UPDATE projects SET {field} = ?, updated_at = ? WHERE id = ?",
                (json.dumps(items), now_iso(), project_id),
            )
            conn.commit()
    return {"project_id": project_id, field: value}


def _unlink_id(project_id: str, field: str, value: str, settings: Settings | None) -> bool:
    with get_connection(settings) as conn:
        row = _fetch_project_row(conn, project_id)
        if not row:
            return False
        items = json.loads(row[field]) if row[field] else []
        if value not in items:
            return False
        items.remove(value)
        conn.execute(
            f"UPDATE projects SET {field} = ?, updated_at = ? WHERE id = ?",
            (json.dumps(items), now_iso(), project_id),
        )
        conn.commit()
    return True


def link_conversation(project_id: str, conversation_id: str, settings: Settings | None = None):
    return _link_id(project_id, "conversations", conversation_id, settings)


def unlink_conversation(
    project_id: str, conversation_id: str, settings: Settings | None = None
) -> bool:
    return _unlink_id(project_id, "conversations", conversation_id, settings)


def link_related_project(
    project_id: str, related_project_id: str, settings: Settings | None = None
):
    return _link_id(project_id, "related_projects", related_project_id, settings)


def unlink_related_project(
    project_id: str, related_project_id: str, settings: Settings | None = None
) -> bool:
    return _unlink_id(project_id, "related_projects", related_project_id, settings)


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


def _capability_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "created_at": row["created_at"],
    }


def create_capability(
    project_id: str,
    name: str,
    description: str = "",
    category: str = "",
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        if not _fetch_project_row(conn, project_id):
            return None
        capability_id = new_id()
        conn.execute(
            "INSERT INTO capabilities (id, project_id, name, description, category, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (capability_id, project_id, name, description, category, now_iso()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM capabilities WHERE id = ?", (capability_id,)).fetchone()
    return _capability_row_to_dict(row)


def get_capability(capability_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM capabilities WHERE id = ?", (capability_id,)).fetchone()
    return _capability_row_to_dict(row) if row else None


def list_capabilities(
    *, project_id: str | None = None, q: str | None = None, settings: Settings | None = None
) -> list[dict[str, Any]]:
    query = "SELECT * FROM capabilities WHERE 1=1"
    params: list[Any] = []
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    if q:
        query += " AND (name LIKE ? OR description LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])
    query += " ORDER BY name"
    with get_connection(settings) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_capability_row_to_dict(r) for r in rows]


def consume_capability(
    capability_id: str, consumer_project_id: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        cap_row = conn.execute(
            "SELECT * FROM capabilities WHERE id = ?", (capability_id,)
        ).fetchone()
        if not cap_row or not _fetch_project_row(conn, consumer_project_id):
            return None
        link_id = new_id()
        conn.execute(
            """
            INSERT OR IGNORE INTO capability_consumers (id, capability_id, consumer_project_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (link_id, capability_id, consumer_project_id, now_iso()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM capability_consumers WHERE capability_id = ? AND consumer_project_id = ?",
            (capability_id, consumer_project_id),
        ).fetchone()
    return dict(row)


def remove_capability_consumer(
    capability_id: str, consumer_project_id: str, settings: Settings | None = None
) -> bool:
    with get_connection(settings) as conn:
        cur = conn.execute(
            "DELETE FROM capability_consumers WHERE capability_id = ? AND consumer_project_id = ?",
            (capability_id, consumer_project_id),
        )
        conn.commit()
    return cur.rowcount > 0


def list_capability_consumers(
    capability_id: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    query = """
        SELECT capability_consumers.*, projects.name AS project_name
        FROM capability_consumers
        JOIN projects ON projects.id = capability_consumers.consumer_project_id
        WHERE capability_id = ?
        ORDER BY capability_consumers.created_at
    """
    with get_connection(settings) as conn:
        rows = conn.execute(query, (capability_id,)).fetchall()
    return [dict(r) for r in rows]


def list_consumed_capabilities(
    project_id: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    query = """
        SELECT capabilities.*, projects.name AS provider_project_name
        FROM capability_consumers
        JOIN capabilities ON capabilities.id = capability_consumers.capability_id
        JOIN projects ON projects.id = capabilities.project_id
        WHERE capability_consumers.consumer_project_id = ?
        ORDER BY capabilities.name
    """
    with get_connection(settings) as conn:
        rows = conn.execute(query, (project_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def create_dependency(
    project_id: str, depends_on_project_id: str, note: str = "", settings: Settings | None = None
) -> dict[str, Any] | None:
    if project_id == depends_on_project_id:
        return None
    with get_connection(settings) as conn:
        if not _fetch_project_row(conn, project_id) or not _fetch_project_row(
            conn, depends_on_project_id
        ):
            return None
        dep_id = new_id()
        conn.execute(
            """
            INSERT OR IGNORE INTO dependencies (id, project_id, depends_on_project_id, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (dep_id, project_id, depends_on_project_id, note, now_iso()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM dependencies WHERE project_id = ? AND depends_on_project_id = ?",
            (project_id, depends_on_project_id),
        ).fetchone()
    return dict(row)


def delete_dependency(dependency_id: str, settings: Settings | None = None) -> bool:
    with get_connection(settings) as conn:
        cur = conn.execute("DELETE FROM dependencies WHERE id = ?", (dependency_id,))
        conn.commit()
    return cur.rowcount > 0


def list_dependencies(project_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Projects that `project_id` depends on."""
    query = """
        SELECT dependencies.*, projects.name AS depends_on_project_name
        FROM dependencies
        JOIN projects ON projects.id = dependencies.depends_on_project_id
        WHERE dependencies.project_id = ?
        ORDER BY dependencies.created_at
    """
    with get_connection(settings) as conn:
        rows = conn.execute(query, (project_id,)).fetchall()
    return [dict(r) for r in rows]


def list_dependents(project_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Projects that depend on `project_id` (reverse lookup)."""
    query = """
        SELECT dependencies.*, projects.name AS dependent_project_name
        FROM dependencies
        JOIN projects ON projects.id = dependencies.project_id
        WHERE dependencies.depends_on_project_id = ?
        ORDER BY dependencies.created_at
    """
    with get_connection(settings) as conn:
        rows = conn.execute(query, (project_id,)).fetchall()
    return [dict(r) for r in rows]


def list_all_projects_light(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Minimal project listing (id, name) used internally by health scoring
    and other cross-project computations that don't need full collections."""
    with get_connection(settings) as conn:
        rows = conn.execute("SELECT id, name, updated_at FROM projects").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# AI Workspace (v1.3) -- one saved Claude/ChatGPT/Gemini conversation link,
# role, and preferred model per project, plus a last-opened timestamp. At
# most one row per project_id, unlike the JSON-list collections above.
# ---------------------------------------------------------------------------


def get_ai_workspace(project_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT * FROM ai_workspace WHERE project_id = ?", (project_id,)
        ).fetchone()
    return dict(row) if row else None


def save_ai_workspace(
    project_id: str,
    *,
    claude_url: str | None = None,
    chatgpt_url: str | None = None,
    gemini_url: str | None = None,
    role: str | None = None,
    preferred_model: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Upserts the AI Workspace for a project. Only fields explicitly
    passed (not None) are changed -- matches the PATCH-like semantics
    used elsewhere in this module (e.g. `update_registry_project` in
    `app.session.db`), so "Save Conversation" can update just one field
    (e.g. only the Claude URL) without clobbering the others.
    """
    ts = now_iso()
    fields = {
        "claude_url": claude_url,
        "chatgpt_url": chatgpt_url,
        "gemini_url": gemini_url,
        "role": role,
        "preferred_model": preferred_model,
    }
    provided = {k: v for k, v in fields.items() if v is not None}

    with get_connection(settings) as conn:
        existing = conn.execute(
            "SELECT project_id FROM ai_workspace WHERE project_id = ?", (project_id,)
        ).fetchone()
        if existing:
            if provided:
                set_clause = ", ".join(f"{col} = ?" for col in provided)
                conn.execute(
                    f"UPDATE ai_workspace SET {set_clause}, updated_at = ? WHERE project_id = ?",
                    (*provided.values(), ts, project_id),
                )
        else:
            conn.execute(
                """
                INSERT INTO ai_workspace (
                    project_id, claude_url, chatgpt_url, gemini_url, role,
                    preferred_model, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    claude_url or "",
                    chatgpt_url or "",
                    gemini_url or "",
                    role or "",
                    preferred_model or "",
                    ts,
                    ts,
                ),
            )
        conn.commit()

    return get_ai_workspace(project_id, settings)


def touch_ai_workspace_last_opened(
    project_id: str, settings: Settings | None = None
) -> dict[str, Any]:
    """Records that a conversation was just opened for this project.
    Creates an empty AI Workspace row first if one doesn't exist yet
    (e.g. the very first "Open" click before any URL has ever been
    saved) -- there's no seed data needed since every field defaults to
    an empty string, mirroring `save_ai_workspace`'s own defaults.
    """
    ts = now_iso()
    with get_connection(settings) as conn:
        existing = conn.execute(
            "SELECT project_id FROM ai_workspace WHERE project_id = ?", (project_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE ai_workspace SET last_opened_at = ?, updated_at = ? WHERE project_id = ?",
                (ts, ts, project_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO ai_workspace (
                    project_id, claude_url, chatgpt_url, gemini_url, role,
                    preferred_model, last_opened_at, created_at, updated_at
                ) VALUES (?, '', '', '', '', '', ?, ?, ?)
                """,
                (project_id, ts, ts, ts),
            )
        conn.commit()

    return get_ai_workspace(project_id, settings)


# ---------------------------------------------------------------------------
# AI Sessions (v1.4 Context Engine) -- a collection of assistant conversation
# sessions per project, replacing AI Workspace's single record as the
# primary UI. The v1.3 `ai_workspace` table and functions above are left
# fully intact for backward compatibility; existing data is copied into
# this collection once, at upgrade time, by the `0001_ai_sessions_from_
# ai_workspace` migration -- it is not kept in ongoing sync with them.
# ---------------------------------------------------------------------------

VALID_ASSISTANTS = ("claude", "chatgpt", "gemini", "other")
VALID_AI_SESSION_STATUSES = ("active", "paused", "completed")


def _ai_session_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["favorite"] = bool(data["favorite"])
    data["current"] = bool(data["current"])
    return data


def create_ai_session(
    project_id: str,
    *,
    assistant: str,
    title: str = "",
    conversation_url: str = "",
    role: str = "",
    preferred_model: str = "",
    notes: str = "",
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    ts = now_iso()
    session_id = new_id()
    with get_connection(settings) as conn:
        if not _fetch_project_row(conn, project_id):
            return None
        conn.execute(
            """
            INSERT INTO ai_sessions (
                id, project_id, title, assistant, conversation_url, role,
                preferred_model, started_at, status, favorite, current,
                notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, 0, ?, ?, ?)
            """,
            (
                session_id,
                project_id,
                title,
                assistant,
                conversation_url,
                role,
                preferred_model,
                ts,
                notes,
                ts,
                ts,
            ),
        )
        conn.commit()
    return get_ai_session(session_id, settings)


def get_ai_session(session_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM ai_sessions WHERE id = ?", (session_id,)).fetchone()
    return _ai_session_row_to_dict(row) if row else None


def list_ai_sessions(
    project_id: str,
    *,
    assistant: str | None = None,
    status: str | None = None,
    favorite: bool | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM ai_sessions WHERE project_id = ?"
    params: list[Any] = [project_id]
    if assistant:
        query += " AND assistant = ?"
        params.append(assistant)
    if status:
        query += " AND status = ?"
        params.append(status)
    if favorite is not None:
        query += " AND favorite = ?"
        params.append(1 if favorite else 0)
    query += " ORDER BY current DESC, last_used_at DESC, started_at DESC"

    with get_connection(settings) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_ai_session_row_to_dict(r) for r in rows]


def update_ai_session(
    session_id: str, patch: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any] | None:
    text_fields = {"title", "conversation_url", "role", "preferred_model", "status", "notes"}
    set_clauses = []
    params: list[Any] = []
    for field in text_fields:
        if field in patch and patch[field] is not None:
            set_clauses.append(f"{field} = ?")
            params.append(patch[field])
    if "favorite" in patch and patch["favorite"] is not None:
        set_clauses.append("favorite = ?")
        params.append(1 if patch["favorite"] else 0)

    with get_connection(settings) as conn:
        if not conn.execute("SELECT id FROM ai_sessions WHERE id = ?", (session_id,)).fetchone():
            return None
        if set_clauses:
            set_clauses.append("updated_at = ?")
            params.append(now_iso())
            params.append(session_id)
            conn.execute(f"UPDATE ai_sessions SET {', '.join(set_clauses)} WHERE id = ?", params)
            conn.commit()
    return get_ai_session(session_id, settings)


def delete_ai_session(session_id: str, settings: Settings | None = None) -> bool:
    with get_connection(settings) as conn:
        if not conn.execute("SELECT id FROM ai_sessions WHERE id = ?", (session_id,)).fetchone():
            return False
        conn.execute("DELETE FROM ai_session_snapshots WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM ai_sessions WHERE id = ?", (session_id,))
        conn.commit()
    return True


def set_ai_session_current(
    session_id: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    """Marks one session as `current` for its (project, assistant) pair,
    demoting any other session that was current for that same pair --
    "current" is scoped per assistant, not one global current session
    per project (you can have a current Claude session and a current
    ChatGPT session for the same project at once).
    """
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT project_id, assistant FROM ai_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not row:
            return None
        ts = now_iso()
        conn.execute(
            "UPDATE ai_sessions SET current = 0, updated_at = ? WHERE project_id = ? AND assistant = ? AND id != ?",
            (ts, row["project_id"], row["assistant"], session_id),
        )
        conn.execute(
            "UPDATE ai_sessions SET current = 1, updated_at = ? WHERE id = ?", (ts, session_id)
        )
        conn.commit()
    return get_ai_session(session_id, settings)


def touch_ai_session_last_used(
    session_id: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        if not conn.execute("SELECT id FROM ai_sessions WHERE id = ?", (session_id,)).fetchone():
            return None
        ts = now_iso()
        conn.execute(
            "UPDATE ai_sessions SET last_used_at = ?, updated_at = ? WHERE id = ?",
            (ts, ts, session_id),
        )
        conn.commit()
    return get_ai_session(session_id, settings)


# ---------------------------------------------------------------------------
# AI Session Snapshots (v1.4) -- an append-only log of point-in-time
# captures for one session; a session may have any number of snapshots.
# ---------------------------------------------------------------------------


def create_ai_session_snapshot(
    session_id: str,
    *,
    accomplishments: str = "",
    blockers: str = "",
    pending_work: str = "",
    next_prompt: str = "",
    decisions: str = "",
    summary: str = "",
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        if not conn.execute("SELECT id FROM ai_sessions WHERE id = ?", (session_id,)).fetchone():
            return None
        snapshot_id = new_id()
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO ai_session_snapshots (
                id, session_id, accomplishments, blockers, pending_work,
                next_prompt, decisions, summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                session_id,
                accomplishments,
                blockers,
                pending_work,
                next_prompt,
                decisions,
                summary,
                ts,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM ai_session_snapshots WHERE id = ?", (snapshot_id,)
        ).fetchone()
    return dict(row)


def list_ai_session_snapshots(
    session_id: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM ai_session_snapshots WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_latest_snapshot(session_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT * FROM ai_session_snapshots WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Project Timeline (v1.4) -- a chronological feed of session starts and
# snapshots for one project, computed on demand from the tables above; no
# separate store, matching this codebase's "never duplicate data into a
# new store" rule (docs/architecture/06_DEVELOPMENT_RULES.md).
# ---------------------------------------------------------------------------


def list_project_timeline(
    project_id: str, settings: Settings | None = None
) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        sessions = conn.execute(
            "SELECT * FROM ai_sessions WHERE project_id = ?", (project_id,)
        ).fetchall()
        session_by_id = {s["id"]: s for s in sessions}

        entries: list[dict[str, Any]] = []
        for s in sessions:
            entries.append(
                {
                    "type": "session_started",
                    "timestamp": s["started_at"],
                    "session_id": s["id"],
                    "session_title": s["title"],
                    "assistant": s["assistant"],
                    "excerpt": (
                        f'Started "{s["title"]}"'
                        if s["title"]
                        else f"Started a {s['assistant']} session"
                    ),
                }
            )

        if sessions:
            placeholders = ",".join("?" for _ in sessions)
            snap_rows = conn.execute(
                f"SELECT * FROM ai_session_snapshots WHERE session_id IN ({placeholders}) ORDER BY created_at",
                [s["id"] for s in sessions],
            ).fetchall()
            for snap in snap_rows:
                s = session_by_id[snap["session_id"]]
                entries.append(
                    {
                        "type": "snapshot",
                        "timestamp": snap["created_at"],
                        "session_id": snap["session_id"],
                        "session_title": s["title"],
                        "assistant": s["assistant"],
                        "excerpt": snap["summary"]
                        or snap["accomplishments"]
                        or "(snapshot recorded)",
                    }
                )

    entries.sort(key=lambda e: e["timestamp"])
    return entries
