"""SQLite persistence layer for the ChatGPT conversation importer.

Owns its own database file (`Settings.imports_db_path`), separate from the
Builder-generated knowledge database and every other domain's store. Schema
creation is idempotent and runs automatically on every connection, so no
manual migration step is required.
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

SCHEMA = """
CREATE TABLE IF NOT EXISTS imported_conversations (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'chatgpt',
    external_id TEXT,
    fingerprint TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT,
    updated_at TEXT,
    message_count INTEGER NOT NULL DEFAULT 0,
    roles TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL DEFAULT '[]',
    content_hash TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    source_file TEXT NOT NULL DEFAULT '',
    source_fingerprint TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_imported_conversations_external_id
    ON imported_conversations(external_id);

CREATE TABLE IF NOT EXISTS import_runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL,
    total_found INTEGER NOT NULL DEFAULT 0,
    imported INTEGER NOT NULL DEFAULT 0,
    updated INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    invalid INTEGER NOT NULL DEFAULT 0,
    errors TEXT NOT NULL DEFAULT '[]',
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_import_runs_started_at ON import_runs(started_at);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path: Path = settings.imports_db_path
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
        "SELECT * FROM imported_conversations WHERE fingerprint = ?",
        (fingerprint,),
    ).fetchone()


def insert_conversation(record: dict[str, Any], conn: sqlite3.Connection) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO imported_conversations (
            id, source, external_id, fingerprint, title, created_at, updated_at,
            message_count, roles, content, content_hash, imported_at, last_seen_at,
            source_file, source_fingerprint
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id(),
            record["source"],
            record["external_id"],
            record["fingerprint"],
            record["title"],
            record["created_at"],
            record["updated_at"],
            record["message_count"],
            json.dumps(record["roles"], ensure_ascii=False),
            json.dumps(record["content"], ensure_ascii=False),
            record["content_hash"],
            ts,
            ts,
            record["source_file"],
            record["source_fingerprint"],
        ),
    )
    conn.commit()


def update_conversation(existing_id: str, record: dict[str, Any], conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE imported_conversations
        SET title = ?, created_at = ?, updated_at = ?, message_count = ?,
            roles = ?, content = ?, content_hash = ?, last_seen_at = ?,
            source_file = ?, source_fingerprint = ?
        WHERE id = ?
        """,
        (
            record["title"],
            record["created_at"],
            record["updated_at"],
            record["message_count"],
            json.dumps(record["roles"], ensure_ascii=False),
            json.dumps(record["content"], ensure_ascii=False),
            record["content_hash"],
            now_iso(),
            record["source_file"],
            record["source_fingerprint"],
            existing_id,
        ),
    )
    conn.commit()


def touch_conversation(existing_id: str, conn: sqlite3.Connection) -> None:
    """Bump last_seen_at for a conversation that was seen again but unchanged."""
    conn.execute(
        "UPDATE imported_conversations SET last_seen_at = ? WHERE id = ?",
        (now_iso(), existing_id),
    )
    conn.commit()


def _row_to_conversation(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source"],
        "external_id": row["external_id"],
        "fingerprint": row["fingerprint"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "message_count": row["message_count"],
        "roles": json.loads(row["roles"]),
        "imported_at": row["imported_at"],
        "last_seen_at": row["last_seen_at"],
        "source_file": row["source_file"],
        "source_fingerprint": row["source_fingerprint"],
    }


def list_conversations(settings: Settings | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM imported_conversations ORDER BY imported_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_conversation(row) for row in rows]


def record_run(summary: dict[str, Any], settings: Settings | None = None) -> dict[str, Any]:
    run_id = new_id()
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO import_runs (
                id, status, source_filename, source_fingerprint, total_found,
                imported, updated, skipped, invalid, errors, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                summary["status"],
                summary["source_filename"],
                summary["source_fingerprint"],
                summary["total_found"],
                summary["imported"],
                summary["updated"],
                summary["skipped"],
                summary["invalid"],
                json.dumps(summary["errors"], ensure_ascii=False),
                summary["started_at"],
                summary["completed_at"],
            ),
        )
        conn.commit()
    return {"id": run_id, **summary}


def _row_to_run(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "status": row["status"],
        "source_filename": row["source_filename"],
        "source_fingerprint": row["source_fingerprint"],
        "total_found": row["total_found"],
        "imported": row["imported"],
        "updated": row["updated"],
        "skipped": row["skipped"],
        "invalid": row["invalid"],
        "errors": json.loads(row["errors"]),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }


def list_runs(settings: Settings | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM import_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_run(row) for row in rows]
