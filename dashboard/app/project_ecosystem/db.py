"""SQLite persistence for the Project Ecosystem Engine (Sprint C8).

One table, minimal, same discipline as `app.assets.db`/`app.workspace.db`:
this never stores relationships themselves (those are always recomputed
fresh from ProjectContext/Assets/Knowledge/PI dependencies on every
request) -- only a user's manual override of one, keyed by the
relationship's own deterministic `relationship_id`
(`models.relationship_id`, stable across recomputation since it's derived
from the two projects + type + detector, not a random id). Dismissing a
false-positive detected relationship, or confirming one, both live here;
nothing here is a second source of truth for the relationship graph.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS relationship_overrides (
    relationship_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

VALID_STATUSES = ("dismissed", "confirmed")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path: Path = settings.ecosystem_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


def list_overrides(settings: Settings | None = None) -> dict[str, str]:
    """`{relationship_id: status}` for every manually-overridden
    relationship."""
    with get_connection(settings) as conn:
        rows = conn.execute("SELECT relationship_id, status FROM relationship_overrides").fetchall()
    return {row["relationship_id"]: row["status"] for row in rows}


def set_override(relationship_id: str, status: str, settings: Settings | None = None) -> None:
    assert status in VALID_STATUSES, f"invalid override status: {status}"
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO relationship_overrides (relationship_id, status, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(relationship_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
            """,
            (relationship_id, status, now_iso()),
        )
        conn.commit()


def clear_override(relationship_id: str, settings: Settings | None = None) -> bool:
    with get_connection(settings) as conn:
        cursor = conn.execute(
            "DELETE FROM relationship_overrides WHERE relationship_id = ?", (relationship_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
