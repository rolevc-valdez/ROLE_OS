"""SQLite persistence for Assets OS (Sprint C4).

Two tables, both intentionally minimal, same "do not duplicate what the
filesystem or another domain already owns" discipline as `app.workspace.
db`. Schema creation is idempotent and runs on every connection.

- `asset_cache`: keyed by `asset_id` (a deterministic hash of the file's
  absolute path). Stores the *expensive-to-recompute* signals (image
  width/height, the partial-content duplicate hash) alongside the file's
  `size_bytes`/`mtime` at the time they were computed -- a cache hit only
  counts if the file's current size+mtime still match, so a modified file
  is always recomputed, never served stale dimensions/hash silently.
- `asset_overrides`: keyed by `asset_id`. The *only* place a user's
  reusable/category/favorite choice is stored -- never written back into
  the scanned file or folder.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS asset_cache (
    asset_id TEXT PRIMARY KEY,
    absolute_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime REAL NOT NULL,
    width INTEGER,
    height INTEGER,
    duplicate_hash TEXT,
    computed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_overrides (
    asset_id TEXT PRIMARY KEY,
    reusable INTEGER,
    category TEXT,
    favorite INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path: Path = settings.assets_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def get_cached(
    asset_id: str, *, size_bytes: int, mtime: float, settings: Settings | None = None
) -> dict[str, Any] | None:
    """Returns the cached `{width, height, duplicate_hash}` only if the
    file's current `size_bytes`/`mtime` still match what was cached --
    otherwise `None` (the caller must recompute), so a changed file is
    never served stale derived data."""
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM asset_cache WHERE asset_id = ?", (asset_id,)).fetchone()
    if row is None:
        return None
    if row["size_bytes"] != size_bytes or abs(row["mtime"] - mtime) > 0.001:
        return None
    return {
        "width": row["width"],
        "height": row["height"],
        "duplicate_hash": row["duplicate_hash"],
    }


def set_cached(
    asset_id: str,
    *,
    absolute_path: str,
    size_bytes: int,
    mtime: float,
    width: int | None,
    height: int | None,
    duplicate_hash: str | None,
    settings: Settings | None = None,
) -> None:
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO asset_cache (
                asset_id, absolute_path, size_bytes, mtime, width, height,
                duplicate_hash, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                absolute_path = excluded.absolute_path,
                size_bytes = excluded.size_bytes,
                mtime = excluded.mtime,
                width = excluded.width,
                height = excluded.height,
                duplicate_hash = excluded.duplicate_hash,
                computed_at = excluded.computed_at
            """,
            (asset_id, absolute_path, size_bytes, mtime, width, height, duplicate_hash, now_iso()),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


def get_override(asset_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT * FROM asset_overrides WHERE asset_id = ?", (asset_id,)
        ).fetchone()
    if row is None:
        return None
    return {
        "reusable": None if row["reusable"] is None else bool(row["reusable"]),
        "category": row["category"],
        "favorite": bool(row["favorite"]),
    }


def list_overrides(settings: Settings | None = None) -> dict[str, dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute("SELECT * FROM asset_overrides").fetchall()
    return {
        row["asset_id"]: {
            "reusable": None if row["reusable"] is None else bool(row["reusable"]),
            "category": row["category"],
            "favorite": bool(row["favorite"]),
        }
        for row in rows
    }


def set_override(
    asset_id: str,
    *,
    reusable: bool | None = None,
    category: str | None = None,
    favorite: bool | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """PATCH-like semantics -- only fields explicitly passed (not the
    Python `None` *sentinel meaning "don't touch"*, distinguished from the
    stored "no override" `NULL` by reading the existing row first) are
    changed. Never modifies the source file -- this table is the only
    place a reusable/category/favorite choice lives."""
    existing = get_override(asset_id, settings) or {
        "reusable": None,
        "category": None,
        "favorite": False,
    }
    new_reusable = existing["reusable"] if reusable is None else reusable
    new_category = existing["category"] if category is None else category
    new_favorite = existing["favorite"] if favorite is None else favorite
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO asset_overrides (asset_id, reusable, category, favorite, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                reusable = excluded.reusable,
                category = excluded.category,
                favorite = excluded.favorite,
                updated_at = excluded.updated_at
            """,
            (
                asset_id,
                None if new_reusable is None else int(new_reusable),
                new_category,
                int(new_favorite),
                now_iso(),
            ),
        )
        conn.commit()
    return {"reusable": new_reusable, "category": new_category, "favorite": new_favorite}


def clear_override(asset_id: str, settings: Settings | None = None) -> None:
    with get_connection(settings) as conn:
        conn.execute("DELETE FROM asset_overrides WHERE asset_id = ?", (asset_id,))
        conn.commit()
