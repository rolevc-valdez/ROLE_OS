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

# Sprint B1.5 (Conversation Explorer) added two columns to a table that may
# already exist from Sprint B1 installs. CREATE TABLE IF NOT EXISTS won't
# retrofit those onto an existing table, so migrate them in explicitly.
# `status` only ever holds "imported" today -- there is no processing
# pipeline yet -- but exists as a real column (not a placeholder) so a
# future stage (e.g. "processed") can be introduced without a schema change.
_MIGRATIONS = (
    "ALTER TABLE imported_conversations ADD COLUMN status TEXT NOT NULL DEFAULT 'imported'",
    "ALTER TABLE imported_conversations ADD COLUMN import_run_id TEXT",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for migration in _MIGRATIONS:
        try:
            conn.execute(migration)
        except sqlite3.OperationalError:
            pass  # column already exists
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
            source_file, source_fingerprint, status, import_run_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            record.get("status", "imported"),
            record.get("import_run_id"),
        ),
    )
    conn.commit()


def update_conversation(existing_id: str, record: dict[str, Any], conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE imported_conversations
        SET title = ?, created_at = ?, updated_at = ?, message_count = ?,
            roles = ?, content = ?, content_hash = ?, last_seen_at = ?,
            source_file = ?, source_fingerprint = ?, import_run_id = ?
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
            record.get("import_run_id"),
            existing_id,
        ),
    )
    conn.commit()


def delete_conversation(conversation_id: str, settings: Settings | None = None) -> bool:
    with get_connection(settings) as conn:
        cur = conn.execute("DELETE FROM imported_conversations WHERE id = ?", (conversation_id,))
        conn.commit()
        return cur.rowcount > 0


def touch_conversation(existing_id: str, conn: sqlite3.Connection) -> None:
    """Bump last_seen_at for a conversation that was seen again but unchanged."""
    conn.execute(
        "UPDATE imported_conversations SET last_seen_at = ? WHERE id = ?",
        (now_iso(), existing_id),
    )
    conn.commit()


def _row_to_conversation(row: sqlite3.Row, include_content: bool = False) -> dict[str, Any]:
    record = {
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
        "status": row["status"],
        "import_run_id": row["import_run_id"],
    }
    if include_content:
        record["content"] = json.loads(row["content"])
    return record


def list_conversations(settings: Settings | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM imported_conversations ORDER BY imported_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_conversation(row) for row in rows]


SORTABLE_COLUMNS = {
    "imported_at": "imported_at",
    "created_at": "created_at",
    "title": "title",
    "message_count": "message_count",
}


def list_conversations_page(
    *,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "imported_at",
    sort_dir: str = "desc",
    q: str | None = None,
    source: str | None = None,
    status: str | None = None,
    imported_after: str | None = None,
    imported_before: str | None = None,
    settings: Settings | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Search/filter/sort/paginate imported conversations.

    Returns (items, total_matching) -- total_matching is the count under the
    same filters, before pagination, so the caller can render page counts.
    """
    column = SORTABLE_COLUMNS.get(sort_by, "imported_at")
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
    page = max(1, page)
    page_size = max(1, min(page_size, 200))

    clauses: list[str] = []
    params: list[Any] = []

    if q:
        like = f"%{q}%"
        clauses.append("(title LIKE ? OR content LIKE ? OR source LIKE ? OR external_id LIKE ? OR id LIKE ?)")
        params.extend([like, like, like, like, like])
    if source:
        clauses.append("source = ?")
        params.append(source)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if imported_after:
        clauses.append("imported_at >= ?")
        params.append(imported_after)
    if imported_before:
        clauses.append("imported_at <= ?")
        params.append(imported_before)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with get_connection(settings) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM imported_conversations {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM imported_conversations {where}
            ORDER BY {column} {direction}
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()

    return [_row_to_conversation(row) for row in rows], total


def get_conversation(conversation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT * FROM imported_conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
    return _row_to_conversation(row, include_content=True) if row else None


def list_facets(settings: Settings | None = None) -> dict[str, list[str]]:
    with get_connection(settings) as conn:
        sources = [r[0] for r in conn.execute("SELECT DISTINCT source FROM imported_conversations ORDER BY source")]
        statuses = [r[0] for r in conn.execute("SELECT DISTINCT status FROM imported_conversations ORDER BY status")]
    return {"sources": sources, "statuses": statuses}


def count_conversations(settings: Settings | None = None) -> int:
    with get_connection(settings) as conn:
        return conn.execute("SELECT COUNT(*) FROM imported_conversations").fetchone()[0]


def record_run(summary: dict[str, Any], settings: Settings | None = None, run_id: str | None = None) -> dict[str, Any]:
    run_id = run_id or new_id()
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
