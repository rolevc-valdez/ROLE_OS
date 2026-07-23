"""SQLite persistence layer for AI Advisor recommendations.

Owns its own database file (`Settings.advisor_db_path`), completely
separate from both the builder-generated knowledge DB and the Project
Intelligence DB — the Advisor only ever *reads* those, it never writes to
them. Schema creation is idempotent and runs on every connection, same
pattern as `app.projects.db`.

Duplicate prevention: recommendations are deduplicated by
`(project_id, recommendation_type)` — see `dedupe_key`. A new
recommendation is only inserted if no existing row for that key is still
"live" (`expires_at` in the future). This means:

- No duplicate *active* recommendations are ever created for the same
  project + type while one is still live.
- Dismissed and completed recommendations keep their state forever (their
  row is never overwritten) — but since they still count as "live" until
  `expires_at`, dismissing a recommendation also suppresses regenerating
  it for the rest of its natural lifetime, which is the whole point of
  dismissing something.
- Once a row's `expires_at` has passed, it's no longer "live", so the
  engine is free to generate a fresh recommendation for that project+type
  the next time the underlying condition is (still) detected.

The full history is kept (nothing is deleted), which doubles as an audit
log of every recommendation ever produced.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    workspace TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    recommendation_type TEXT NOT NULL,
    priority_score INTEGER NOT NULL,
    confidence_score INTEGER NOT NULL,
    reason TEXT NOT NULL,
    evidence TEXT NOT NULL DEFAULT '[]',
    suggested_action TEXT NOT NULL,
    estimated_effort TEXT NOT NULL,
    impact TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    dismissed INTEGER NOT NULL DEFAULT 0,
    completed INTEGER NOT NULL DEFAULT 0,
    dedupe_key TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recommendations_dedupe ON recommendations(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_recommendations_project ON recommendations(project_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_workspace ON recommendations(workspace);
CREATE INDEX IF NOT EXISTS idx_recommendations_type ON recommendations(recommendation_type);
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
    db_path: Path = settings.advisor_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["evidence"] = json.loads(data["evidence"]) if data.get("evidence") else []
    data["dismissed"] = bool(data["dismissed"])
    data["completed"] = bool(data["completed"])
    return data


def find_live_by_dedupe_key(dedupe_key: str, settings: Settings | None = None) -> dict[str, Any] | None:
    """Return the most recent still-live (unexpired) row for this dedupe key, if any."""
    with get_connection(settings) as conn:
        row = conn.execute(
            """
            SELECT * FROM recommendations
            WHERE dedupe_key = ? AND expires_at > ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (dedupe_key, now_iso()),
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert_recommendation(candidate, settings: Settings | None = None) -> dict[str, Any]:
    """Insert a new recommendation row from a `RecommendationCandidate`.

    Does NOT perform dedupe checking itself — callers (the engine) should
    call `find_live_by_dedupe_key` first and skip insertion if a live row
    already exists. This keeps the "should I insert?" policy decision in
    the engine, where it's easier to test and reason about.
    """
    ts = now_iso()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=candidate.ttl_days)).isoformat()
    rec_id = new_id()
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO recommendations (
                id, project_id, workspace, title, summary, recommendation_type,
                priority_score, confidence_score, reason, evidence, suggested_action,
                estimated_effort, impact, created_at, expires_at, dismissed, completed,
                dedupe_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
            """,
            (
                rec_id,
                candidate.project_id,
                candidate.workspace,
                candidate.title,
                candidate.summary,
                candidate.recommendation_type,
                candidate.priority_score,
                candidate.confidence_score,
                candidate.reason,
                json.dumps(candidate.evidence),
                candidate.suggested_action,
                candidate.estimated_effort,
                candidate.impact,
                ts,
                expires_at,
                candidate.dedupe_key(),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
    return _row_to_dict(row)


def get_recommendation(recommendation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_recommendations(
    *,
    workspace: str | None = None,
    project_id: str | None = None,
    recommendation_type: str | None = None,
    minimum_priority_score: int | None = None,
    include_dismissed: bool = False,
    include_completed: bool = False,
    only_live: bool = False,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM recommendations WHERE 1=1"
    params: list[Any] = []
    if workspace:
        query += " AND workspace = ?"
        params.append(workspace)
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    if recommendation_type:
        query += " AND recommendation_type = ?"
        params.append(recommendation_type)
    if minimum_priority_score is not None:
        query += " AND priority_score >= ?"
        params.append(minimum_priority_score)
    if not include_dismissed:
        query += " AND dismissed = 0"
    if not include_completed:
        query += " AND completed = 0"
    if only_live:
        query += " AND expires_at > ?"
        params.append(now_iso())
    query += " ORDER BY priority_score DESC, created_at DESC"

    with get_connection(settings) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def dismiss_recommendation(recommendation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        if not conn.execute("SELECT 1 FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone():
            return None
        conn.execute("UPDATE recommendations SET dismissed = 1 WHERE id = ?", (recommendation_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone()
    return _row_to_dict(row)


def complete_recommendation(recommendation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        if not conn.execute("SELECT 1 FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone():
            return None
        conn.execute("UPDATE recommendations SET completed = 1 WHERE id = ?", (recommendation_id,))
        conn.commit()
        row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone()
    return _row_to_dict(row)
