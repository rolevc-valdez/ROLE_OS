"""SQLite persistence for Workspace Adoption.

Two tables, both intentionally minimal -- see `app.workspace.__init__`'s
"do not duplicate discovery metadata" rule. Schema creation is idempotent
and runs on every connection, same convention as `app.projects.db`.
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

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace_scan_cache (
    id TEXT PRIMARY KEY,
    root TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    project_count INTEGER NOT NULL,
    result_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS adopted_projects (
    id TEXT PRIMARY KEY,
    root_path TEXT UNIQUE NOT NULL,
    adopted INTEGER NOT NULL DEFAULT 0,
    ignored INTEGER NOT NULL DEFAULT 0,
    priority TEXT NOT NULL DEFAULT 'medium',
    business_value TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'active',
    tags TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '[]',
    adopted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SCAN_CACHE_ID = "singleton"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


# Sprint 3 (Project Boundary): columns added to the existing
# `adopted_projects` table, additive-only. `override_action` is NULL
# (no override -- the Discovery Engine's own computed boundary applies) or
# one of "top_level"/"attach_to_parent"; `override_parent_id` is only set
# when `override_action == "attach_to_parent"`. `ALTER TABLE ... ADD COLUMN`
# is not idempotent in SQLite (no "IF NOT EXISTS"), so each is wrapped and
# the "duplicate column" error is swallowed -- safe to run on every
# connection, on both a fresh database and one from before this sprint.
_SPRINT3_COLUMNS = (
    ("override_action", "ALTER TABLE adopted_projects ADD COLUMN override_action TEXT"),
    ("override_parent_id", "ALTER TABLE adopted_projects ADD COLUMN override_parent_id TEXT"),
)

# Sprint 5 (Project Unification): the canonical ROLE OS Project id this
# adopted item is bridged to (see `app.workspace.identity`). NULL until
# the item is first adopted (or, for an item adopted before Sprint 5
# existed, until it's next read -- `identity.get_or_create_canonical_
# project_id` self-heals that case rather than requiring a one-off
# migration script).
_SPRINT5_COLUMNS = (
    ("canonical_project_id", "ALTER TABLE adopted_projects ADD COLUMN canonical_project_id TEXT"),
)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for _column, ddl in (*_SPRINT3_COLUMNS, *_SPRINT5_COLUMNS):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path: Path = settings.workspace_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Scan cache
# ---------------------------------------------------------------------------


def save_scan_cache(
    *,
    root: str,
    scanned_at: str,
    duration_seconds: float,
    projects: list[dict[str, Any]],
    settings: Settings | None = None,
) -> None:
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO workspace_scan_cache (id, root, scanned_at, duration_seconds, project_count, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                root = excluded.root,
                scanned_at = excluded.scanned_at,
                duration_seconds = excluded.duration_seconds,
                project_count = excluded.project_count,
                result_json = excluded.result_json
            """,
            (
                SCAN_CACHE_ID,
                root,
                scanned_at,
                duration_seconds,
                len(projects),
                json.dumps(projects),
            ),
        )
        conn.commit()


def load_scan_cache(settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT * FROM workspace_scan_cache WHERE id = ?", (SCAN_CACHE_ID,)
        ).fetchone()
    if not row:
        return None
    return {
        "root": row["root"],
        "scanned_at": row["scanned_at"],
        "duration_seconds": row["duration_seconds"],
        "project_count": row["project_count"],
        "projects": json.loads(row["result_json"]),
    }


# ---------------------------------------------------------------------------
# Adopted-project overlay
# ---------------------------------------------------------------------------

_OVERLAY_DEFAULTS = {
    "adopted": False,
    "ignored": False,
    "priority": "medium",
    "business_value": "medium",
    "status": "active",
    "tags": [],
    "notes": [],
    "adopted_at": None,
}


def _overlay_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["adopted"] = bool(data["adopted"])
    data["ignored"] = bool(data["ignored"])
    data["tags"] = json.loads(data["tags"]) if data["tags"] else []
    data["notes"] = json.loads(data["notes"]) if data["notes"] else []
    return data


def get_overlay(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM adopted_projects WHERE id = ?", (item_id,)).fetchone()
    return _overlay_row_to_dict(row) if row else None


def list_overlays(settings: Settings | None = None) -> dict[str, dict[str, Any]]:
    """All overlay rows, keyed by id, for a single bulk merge pass."""
    with get_connection(settings) as conn:
        rows = conn.execute("SELECT * FROM adopted_projects").fetchall()
    return {row["id"]: _overlay_row_to_dict(row) for row in rows}


def _ensure_overlay_row(conn: sqlite3.Connection, item_id: str, root_path: str) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO adopted_projects (
            id, root_path, adopted, ignored, priority, business_value,
            status, tags, notes, adopted_at, created_at, updated_at
        ) VALUES (?, ?, 0, 0, 'medium', 'medium', 'active', '[]', '[]', NULL, ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (item_id, root_path, ts, ts),
    )


def adopt(
    item_id: str,
    root_path: str,
    *,
    priority: str = "medium",
    business_value: str = "medium",
    status: str = "active",
    tags: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    ts = now_iso()
    with get_connection(settings) as conn:
        _ensure_overlay_row(conn, item_id, root_path)
        conn.execute(
            """
            UPDATE adopted_projects
            SET adopted = 1, ignored = 0, priority = ?, business_value = ?,
                status = ?, tags = ?, adopted_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (priority, business_value, status, json.dumps(tags or []), ts, ts, item_id),
        )
        conn.commit()
    return get_overlay(item_id, settings)


def ignore(item_id: str, root_path: str, settings: Settings | None = None) -> dict[str, Any]:
    ts = now_iso()
    with get_connection(settings) as conn:
        _ensure_overlay_row(conn, item_id, root_path)
        conn.execute(
            "UPDATE adopted_projects SET ignored = 1, updated_at = ? WHERE id = ?",
            (ts, item_id),
        )
        conn.commit()
    return get_overlay(item_id, settings)


def unignore(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        if not conn.execute("SELECT id FROM adopted_projects WHERE id = ?", (item_id,)).fetchone():
            return None
        conn.execute(
            "UPDATE adopted_projects SET ignored = 0, updated_at = ? WHERE id = ?",
            (now_iso(), item_id),
        )
        conn.commit()
    return get_overlay(item_id, settings)


def update_overlay(
    item_id: str, root_path: str, patch: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any]:
    allowed = {"priority", "business_value", "status"}
    set_clauses = []
    params: list[Any] = []
    with get_connection(settings) as conn:
        _ensure_overlay_row(conn, item_id, root_path)
        for field in allowed:
            if field in patch and patch[field] is not None:
                set_clauses.append(f"{field} = ?")
                params.append(patch[field])
        if "tags" in patch and patch["tags"] is not None:
            set_clauses.append("tags = ?")
            params.append(json.dumps(patch["tags"]))
        if set_clauses:
            set_clauses.append("updated_at = ?")
            params.append(now_iso())
            params.append(item_id)
            conn.execute(
                f"UPDATE adopted_projects SET {', '.join(set_clauses)} WHERE id = ?", params
            )
            conn.commit()
    return get_overlay(item_id, settings)


VALID_OVERRIDE_ACTIONS = ("top_level", "attach_to_parent")


def set_override(
    item_id: str,
    root_path: str,
    action: str,
    parent_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """§8: user boundary override ("treat as top-level project" /
    "attach to parent project"). Stored only in this overlay table --
    never written back to the scanned folder, and never changes the
    Discovery Engine's own computed `item_kind`/`parent_item_id` fields,
    which remain visible in `discovery_detail` for comparison."""
    assert action in VALID_OVERRIDE_ACTIONS, f"unknown override action: {action}"
    ts = now_iso()
    with get_connection(settings) as conn:
        _ensure_overlay_row(conn, item_id, root_path)
        conn.execute(
            "UPDATE adopted_projects SET override_action = ?, override_parent_id = ?, updated_at = ? WHERE id = ?",
            (action, parent_id if action == "attach_to_parent" else None, ts, item_id),
        )
        conn.commit()
    return get_overlay(item_id, settings)


def clear_override(item_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        if not conn.execute("SELECT id FROM adopted_projects WHERE id = ?", (item_id,)).fetchone():
            return None
        conn.execute(
            "UPDATE adopted_projects SET override_action = NULL, override_parent_id = NULL, updated_at = ? WHERE id = ?",
            (now_iso(), item_id),
        )
        conn.commit()
    return get_overlay(item_id, settings)


def set_canonical_project_id(
    item_id: str, root_path: str, project_id: str, settings: Settings | None = None
) -> dict[str, Any]:
    """Sprint 5: records the bridge from this item to its canonical ROLE OS
    Project id. Creates the overlay row first if it doesn't exist yet --
    an item can have a canonical identity resolved lazily on read, before
    any explicit adopt/ignore/override action has ever touched it."""
    with get_connection(settings) as conn:
        _ensure_overlay_row(conn, item_id, root_path)
        conn.execute(
            "UPDATE adopted_projects SET canonical_project_id = ?, updated_at = ? WHERE id = ?",
            (project_id, now_iso(), item_id),
        )
        conn.commit()
    return get_overlay(item_id, settings)


def add_note(
    item_id: str, root_path: str, text: str, settings: Settings | None = None
) -> dict[str, Any]:
    with get_connection(settings) as conn:
        _ensure_overlay_row(conn, item_id, root_path)
        row = conn.execute("SELECT notes FROM adopted_projects WHERE id = ?", (item_id,)).fetchone()
        notes = json.loads(row["notes"]) if row["notes"] else []
        notes.append({"id": new_id(), "text": text, "created_at": now_iso()})
        conn.execute(
            "UPDATE adopted_projects SET notes = ?, updated_at = ? WHERE id = ?",
            (json.dumps(notes), now_iso(), item_id),
        )
        conn.commit()
    return get_overlay(item_id, settings)
