"""SQLite persistence layer for the Daily Session domain.

Owns its own database file (see `Settings.session_db_path`), separate from
every other domain's store. Schema creation is idempotent and runs
automatically on every connection, so no manual migration step is
required -- the database and the default project registry are created on
first use, mirroring `app/projects/db.py`'s established pattern for a
dashboard-owned store.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

# Seed values for the project registry (requirement: at least these seven).
# Each tuple is (id, name, status, reference, milestone, next_action,
# is_authoritative). `is_authoritative=True` means the value was pulled
# from an actual document in the ROLE Ecosystem at the time this seed was
# written, not guessed -- everything else is an honest placeholder the UI
# must label as a default. See the ROLE OS Dashboard MVP completion report
# for exactly which values came from where.
_SEED_REGISTRY_PROJECTS: tuple[tuple[str, str, str, str, str, str, bool], ...] = (
    (
        "role-os",
        "ROLE OS",
        "Build",
        "ROLE_OS/ (this repository); role-ecosystem/projects/ROLE_OS.md",
        "ROLE OS Dashboard MVP: Start/End My Day, Claude prompt generator, Obsidian-compatible daily record",
        "Ship the MVP: run tests, verify persistence across a restart, update ROLE OS docs",
        True,
    ),
    (
        "role-ecosystem",
        "ROLE ECOSYSTEM",
        "Active",
        "role-ecosystem/README.md",
        "Governance, standards, and templates repository -- continuously active, no release stage",
        "Keep standards/ and templates/ in sync as new products move through PRODUCT_LIFECYCLE.md",
        False,
    ),
    (
        "role-master",
        "ROLE MASTER",
        "Build",
        "role-ecosystem/projects/ROLE_MASTER.md",
        "Current lifecycle stage: Build (per PRODUCT_LIFECYCLE.md)",
        "See role-ecosystem/projects/ROLE_MASTER.md for the specific next milestone",
        False,
    ),
    (
        "role-commerce-factory",
        "ROLE Commerce Factory",
        "Build (Phase 4 - Products)",
        "role-ecosystem/projects/ROLE_COMMERCE_FACTORY.md",
        "Shopify write path: product + variant creation in RCOM-Shopify-Adapter, with a safety lock mirroring Printful's",
        "Implement productCreate + variant mutations, then a dry-run/--commit safety lock before any live write ships",
        True,
    ),
    (
        "brand-character-os",
        "Brand Character OS",
        "Definition",
        "role-ecosystem/projects/BRAND_CHARACTER_OS.md",
        "Current lifecycle stage: Definition (per PRODUCT_LIFECYCLE.md)",
        "Complete its PRD and enter Build, per PRODUCT_LIFECYCLE.md's Definition exit criteria",
        False,
    ),
    (
        "rolevaldez",
        "RoleValdez",
        "Definition",
        "role-ecosystem/projects/ROLEVALDEZ.md",
        "Current lifecycle stage: Definition (per PRODUCT_LIFECYCLE.md)",
        "Complete its PRD and enter Build, per PRODUCT_LIFECYCLE.md's Definition exit criteria",
        False,
    ),
    (
        "super-facil",
        "SUPER FACIL",
        "Discovery",
        "role-ecosystem/projects/SUPER_FACIL.md",
        "Current lifecycle stage: Discovery (per PRODUCT_LIFECYCLE.md)",
        "Validate the problem and gather evidence of demand, per PRODUCT_LIFECYCLE.md's Discovery exit criteria",
        False,
    ),
)

VALID_SESSION_STATUSES = ("not_started", "active", "completed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS registry_projects (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT '',
    reference TEXT NOT NULL DEFAULT '',
    milestone TEXT NOT NULL DEFAULT '',
    next_action TEXT NOT NULL DEFAULT '',
    is_authoritative INTEGER NOT NULL DEFAULT 0,
    user_edited INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    project_id TEXT REFERENCES registry_projects(id),
    project_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    objective TEXT NOT NULL,
    expected_result TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    completed_work TEXT NOT NULL DEFAULT '',
    decisions TEXT NOT NULL DEFAULT '',
    blockers TEXT NOT NULL DEFAULT '',
    next_step TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    row = conn.execute("SELECT COUNT(*) FROM registry_projects").fetchone()
    if row[0] == 0:
        ts = now_iso()
        conn.executemany(
            """
            INSERT INTO registry_projects (
                id, name, status, reference, milestone, next_action,
                is_authoritative, user_edited, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            [
                (pid, name, status, reference, milestone, next_action, int(authoritative), ts, ts)
                for pid, name, status, reference, milestone, next_action, authoritative in _SEED_REGISTRY_PROJECTS
            ],
        )
    conn.commit()


@contextmanager
def get_connection(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    settings = settings or get_settings()
    db_path: Path = settings.session_db_path
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
# Project registry
# ---------------------------------------------------------------------------


def _registry_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["is_authoritative"] = bool(data["is_authoritative"])
    data["user_edited"] = bool(data["user_edited"])
    data["is_default"] = not data["is_authoritative"] and not data["user_edited"]
    return data


def list_registry_projects(settings: Settings | None = None) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute("SELECT * FROM registry_projects ORDER BY name").fetchall()
    return [_registry_row_to_dict(row) for row in rows]


def get_registry_project(
    project_id: str, settings: Settings | None = None
) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM registry_projects WHERE id = ?", (project_id,)).fetchone()
    return _registry_row_to_dict(row) if row else None


def update_registry_project(
    project_id: str, patch: dict[str, Any], settings: Settings | None = None
) -> dict[str, Any] | None:
    allowed = {"status", "reference", "milestone", "next_action"}
    set_clauses = []
    params: list[Any] = []
    for field in allowed:
        if field in patch and patch[field] is not None:
            set_clauses.append(f"{field} = ?")
            params.append(patch[field])

    with get_connection(settings) as conn:
        existing = conn.execute(
            "SELECT id FROM registry_projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not existing:
            return None
        if set_clauses:
            set_clauses.append("user_edited = 1")
            set_clauses.append("updated_at = ?")
            params.append(now_iso())
            params.append(project_id)
            conn.execute(
                f"UPDATE registry_projects SET {', '.join(set_clauses)} WHERE id = ?", params
            )
            conn.commit()
    return get_registry_project(project_id, settings)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def _session_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def get_active_session(settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return _session_row_to_dict(row) if row else None


def get_session(session_id: str, settings: Settings | None = None) -> dict[str, Any] | None:
    with get_connection(settings) as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _session_row_to_dict(row) if row else None


def list_sessions(limit: int = 30, settings: Settings | None = None) -> list[dict[str, Any]]:
    with get_connection(settings) as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_session_row_to_dict(row) for row in rows]


def start_session(
    *,
    date: str,
    project_id: str | None,
    project_name: str,
    mode: str,
    objective: str,
    expected_result: str,
    notes: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Creates and activates a new session.

    Raises `ValueError` if a session is already active -- only one session
    may be active at a time, matching the Not Started / Active / Completed
    status model the dashboard home screen displays.
    """
    if get_active_session(settings):
        raise ValueError("A session is already active. Close it before starting a new one.")

    ts = now_iso()
    session_id = new_id()
    with get_connection(settings) as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                id, date, project_id, project_name, mode, objective,
                expected_result, notes, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                session_id,
                date,
                project_id,
                project_name,
                mode,
                objective,
                expected_result,
                notes,
                ts,
                ts,
            ),
        )
        conn.commit()
    return get_session(session_id, settings)


def complete_session(
    session_id: str,
    *,
    completed_work: str,
    decisions: str,
    blockers: str,
    next_step: str,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    ts = now_iso()
    with get_connection(settings) as conn:
        existing = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not existing:
            return None
        conn.execute(
            """
            UPDATE sessions
            SET completed_work = ?, decisions = ?, blockers = ?, next_step = ?,
                status = 'completed', updated_at = ?, completed_at = ?
            WHERE id = ?
            """,
            (completed_work, decisions, blockers, next_step, ts, ts, session_id),
        )
        conn.commit()
    return get_session(session_id, settings)
