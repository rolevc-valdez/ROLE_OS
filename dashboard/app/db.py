"""SQLite access layer for the ROLE OS Dashboard.

Keeps all raw SQL in one place so routers stay thin and the storage engine
can be swapped later without touching request-handling code.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.config import Settings, get_settings


class DatabaseUnavailableError(RuntimeError):
    """Raised when the configured SQLite database file cannot be found."""


def _row_to_card(row: sqlite3.Row) -> dict[str, Any]:
    card = json.loads(row["card_json"]) if row["card_json"] else {}
    card.setdefault("conversation_id", row["conversation_id"])
    card.setdefault("title", row["title"])
    card.setdefault("project", row["project"])
    card.setdefault("category", row["category"])
    card.setdefault("status", row["status"])
    card.setdefault("date", row["date"])
    card.setdefault("updated", row["updated"])
    card.setdefault("summary", row["summary"])
    return card


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path: Path = settings.db_path
    if not db_path.exists():
        raise DatabaseUnavailableError(f"SQLite database not found at: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def database_exists(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.db_path.exists()


def list_projects(settings: Settings | None = None) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT project, COUNT(*) AS count
            FROM knowledge_cards
            GROUP BY project
            ORDER BY count DESC, project ASC
            """
        ).fetchall()
    return [{"project": row["project"], "count": row["count"]} for row in rows]


def search_cards(query: str, settings: Settings | None = None, limit: int = 50) -> list[dict[str, Any]]:
    like = f"%{query}%"
    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT conversation_id, title, project, category, status, date, updated, summary, card_json
            FROM knowledge_cards
            WHERE title LIKE ? OR summary LIKE ? OR card_json LIKE ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (like, like, like, limit),
        ).fetchall()
    return [_row_to_card(row) for row in rows]


def recent_cards(settings: Settings | None = None, limit: int = 10) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT conversation_id, title, project, category, status, date, updated, summary, card_json
            FROM knowledge_cards
            ORDER BY date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_card(row) for row in rows]


def timeline(settings: Settings | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT conversation_id, title, project, date, updated
            FROM knowledge_cards
            ORDER BY date ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "conversation_id": row["conversation_id"],
            "title": row["title"],
            "project": row["project"],
            "date": row["date"],
            "updated": row["updated"],
        }
        for row in rows
    ]


def list_all_cards(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Return every knowledge card, fully parsed.

    Internal helper for cross-cutting consumers (currently the Knowledge
    Graph engine, Epic 3) that need to build a full picture of the
    knowledge base rather than a single search/lookup. Not exposed as its
    own public API endpoint -- existing /knowledge/{id}, /search, and
    /projects routes are unchanged.
    """
    with get_connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT conversation_id, title, project, category, status, date, updated, summary, card_json
            FROM knowledge_cards
            ORDER BY date ASC
            """
        ).fetchall()
    return [_row_to_card(row) for row in rows]


def get_card(conversation_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute(
            """
            SELECT conversation_id, title, project, category, status, date, updated, summary, card_json
            FROM knowledge_cards
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        ).fetchone()
    return _row_to_card(row) if row else None
