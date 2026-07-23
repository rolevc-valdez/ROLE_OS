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
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

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
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT COUNT(*) FROM workspaces").fetchone()
    if row[0] == 0:
        ts = now_iso()
        conn.executemany(
            "INSERT INTO workspaces (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            [(new_id(), name, "", ts, ts) for name in DEFAULT_WORKSPACES],
        )
    conn.commit()


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


def create_workspace(name: str, description: str = "", settings: Settings | None = None) -> dict[str, Any]:
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


def get_project(project_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = _fetch_project_row(conn, project_id)
        if not row:
            return None
        ws_row = conn.execute("SELECT name FROM workspaces WHERE id = ?", (row["workspace_id"],)).fetchone()
    return _project_row_to_dict(row, ws_row["name"] if ws_row else None)


def list_projects(
    *,
    workspace: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    priority: str | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT projects.*, workspaces.name AS workspace_name FROM projects JOIN workspaces ON projects.workspace_id = workspaces.id WHERE 1=1"
    params: list[Any] = []
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
        conn.execute("DELETE FROM capability_consumers WHERE consumer_project_id = ?", (project_id,))
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
    project_id: str, field: str, item_id: str, patch: dict[str, Any], settings: Settings | None = None
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


def _link_id(project_id: str, field: str, value: str, settings: Settings | None) -> dict[str, Any] | None:
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


def unlink_conversation(project_id: str, conversation_id: str, settings: Settings | None = None) -> bool:
    return _unlink_id(project_id, "conversations", conversation_id, settings)


def link_related_project(project_id: str, related_project_id: str, settings: Settings | None = None):
    return _link_id(project_id, "related_projects", related_project_id, settings)


def unlink_related_project(project_id: str, related_project_id: str, settings: Settings | None = None) -> bool:
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
    project_id: str, name: str, description: str = "", category: str = "", settings: Settings | None = None
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
        cap_row = conn.execute("SELECT * FROM capabilities WHERE id = ?", (capability_id,)).fetchone()
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


def list_capability_consumers(capability_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
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


def list_consumed_capabilities(project_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
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
        if not _fetch_project_row(conn, project_id) or not _fetch_project_row(conn, depends_on_project_id):
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
