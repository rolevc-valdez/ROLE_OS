"""SQLite persistence layer for Knowledge Extraction (Sprint 4).

Owns its own database file (`Settings.extraction_db_path`), separate from
the imports database and every other domain's store. Schema creation is
idempotent and runs automatically on every connection, so no manual
migration step is required -- same pattern as `app/imports/db.py`.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS extracted_objects (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'chatgpt',
    confidence REAL NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    extraction_run_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_extracted_objects_conversation ON extracted_objects(conversation_id);
CREATE INDEX IF NOT EXISTS idx_extracted_objects_type ON extracted_objects(object_type);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    total_found INTEGER NOT NULL DEFAULT 0,
    created INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    counts_by_type TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_conversation ON extraction_runs(conversation_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def make_fingerprint(conversation_id: str, object_type: str, title: str) -> str:
    normalized = " ".join(title.lower().split())
    payload = f"{conversation_id}|{object_type}|{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path: Path = settings.extraction_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


def get_by_fingerprint(fingerprint: str, conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM extracted_objects WHERE fingerprint = ?", (fingerprint,)
    ).fetchone()


def insert_object(record: dict[str, Any], conn: sqlite3.Connection) -> str:
    obj_id = new_id()
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO extracted_objects (
            id, conversation_id, object_type, title, source, confidence,
            fingerprint, extraction_run_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            obj_id,
            record["conversation_id"],
            record["object_type"],
            record["title"],
            record["source"],
            record["confidence"],
            record["fingerprint"],
            record["extraction_run_id"],
            ts,
            ts,
        ),
    )
    conn.commit()
    return obj_id


def update_object(existing_id: str, record: dict[str, Any], conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE extracted_objects
        SET confidence = ?, extraction_run_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (record["confidence"], record["extraction_run_id"], now_iso(), existing_id),
    )
    conn.commit()


def touch_object(existing_id: str, conn: sqlite3.Connection) -> None:
    conn.execute("UPDATE extracted_objects SET updated_at = ? WHERE id = ?", (now_iso(), existing_id))
    conn.commit()


def _row_to_object(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "object_type": row["object_type"],
        "title": row["title"],
        "source": row["source"],
        "confidence": row["confidence"],
        "fingerprint": row["fingerprint"],
        "extraction_run_id": row["extraction_run_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_objects(
    conversation_id: str, object_type: str | None = None, settings: Settings | None = None
) -> list[dict[str, Any]]:
    query = "SELECT * FROM extracted_objects WHERE conversation_id = ?"
    params: list[Any] = [conversation_id]
    if object_type:
        query += " AND object_type = ?"
        params.append(object_type)
    query += " ORDER BY object_type ASC, created_at ASC"
    with get_connection(settings) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_object(row) for row in rows]


def list_all_objects(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Every extracted object across every conversation. Used by the
    Knowledge Graph engine (Sprint 5) to build the full graph in one pass;
    not exposed as its own API endpoint."""
    with get_connection(settings) as conn:
        rows = conn.execute("SELECT * FROM extracted_objects ORDER BY conversation_id ASC, created_at ASC").fetchall()
    return [_row_to_object(row) for row in rows]


def get_object(object_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM extracted_objects WHERE id = ?", (object_id,)).fetchone()
    return _row_to_object(row) if row else None


def delete_object(object_id: str, settings: Settings | None = None) -> bool:
    with get_connection(settings) as conn:
        cur = conn.execute("DELETE FROM extracted_objects WHERE id = ?", (object_id,))
        conn.commit()
        return cur.rowcount > 0


def counts_by_type(settings: Settings | None = None) -> dict[str, int]:
    with get_connection(settings) as conn:
        rows = conn.execute("SELECT object_type, COUNT(*) FROM extracted_objects GROUP BY object_type").fetchall()
    return {row[0]: row[1] for row in rows}


def record_run(summary: dict[str, Any], settings: Settings | None = None, run_id: str | None = None) -> dict[str, Any]:
    run_id = run_id or new_id()
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO extraction_runs (
                id, conversation_id, status, total_found, created, updated,
                unchanged, counts_by_type, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                summary["conversation_id"],
                summary["status"],
                summary["total_found"],
                summary["created"],
                summary["updated"],
                summary["unchanged"],
                json.dumps(summary["counts_by_type"], ensure_ascii=False),
                summary["started_at"],
                summary["completed_at"],
            ),
        )
        conn.commit()
    return {"id": run_id, **summary}
