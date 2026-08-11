"""Tests for the v1.4 Context Engine migration
(`0001_ai_sessions_from_ai_workspace` in app.projects.db): copying
existing v1.3 AI Workspace data into the new AI Sessions collection.

Builds a raw SQLite file that looks exactly like a database a v1.3
server would have produced (no `ai_sessions`/`schema_migrations` tables,
real `ai_workspace` rows) -- the realistic "upgrading an existing
database" scenario -- rather than creating a project through v1.4 code
first, which would apply (and mark complete) the migration against an
empty ai_workspace table before any data exists to migrate.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

import pytest
from app.config import Settings
from app.projects import db


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def legacy_db_path(tmp_path):
    """Creates a raw SQLite file with the v1.3 schema and one project
    with a full AI Workspace record (all three URLs), simulating a
    database that existed before v1.4's migration code did.
    """
    path = tmp_path / "projects.db"
    ts = _iso_now()
    workspace_id = uuid.uuid4().hex
    project_id = uuid.uuid4().hex

    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE workspaces (id TEXT PRIMARY KEY, name TEXT, description TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE projects (id TEXT PRIMARY KEY, workspace_id TEXT, name TEXT, description TEXT, status TEXT, health_score INTEGER, priority TEXT, tags TEXT, owner TEXT, notes TEXT, decisions TEXT, todos TEXT, deliverables TEXT, assets TEXT, prompts TEXT, conversations TEXT, related_projects TEXT, created_at TEXT, updated_at TEXT);
        CREATE TABLE ai_workspace (project_id TEXT PRIMARY KEY, claude_url TEXT, chatgpt_url TEXT, gemini_url TEXT, role TEXT, preferred_model TEXT, last_opened_at TEXT, created_at TEXT, updated_at TEXT);
        """)
    conn.execute(
        "INSERT INTO workspaces VALUES (?, ?, ?, ?, ?)", (workspace_id, "Products", "", ts, ts)
    )
    conn.execute(
        "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project_id,
            workspace_id,
            "Legacy Project",
            "",
            "active",
            0,
            "medium",
            "[]",
            "",
            "[]",
            "[]",
            "[]",
            "[]",
            "[]",
            "[]",
            "[]",
            "[]",
            ts,
            ts,
        ),
    )
    conn.execute(
        "INSERT INTO ai_workspace VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project_id,
            "https://claude.ai/chat/old1",
            "https://chatgpt.com/c/old2",
            "",
            "Engineer",
            "Opus",
            None,
            ts,
            ts,
        ),
    )
    conn.commit()
    conn.close()
    return path, project_id


@pytest.fixture
def settings_for(monkeypatch):
    def _make(path):
        monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(path))
        return Settings()

    return _make


def test_migration_copies_every_saved_url_into_a_session(legacy_db_path, settings_for):
    path, project_id = legacy_db_path
    settings = settings_for(path)

    sessions = db.list_ai_sessions(project_id, settings=settings)
    assistants = {s["assistant"] for s in sessions}
    assert assistants == {"claude", "chatgpt"}  # gemini_url was empty, so no gemini session


def test_migration_preserves_url_role_and_model(legacy_db_path, settings_for):
    path, project_id = legacy_db_path
    settings = settings_for(path)

    sessions = {s["assistant"]: s for s in db.list_ai_sessions(project_id, settings=settings)}
    assert sessions["claude"]["conversation_url"] == "https://claude.ai/chat/old1"
    assert sessions["chatgpt"]["conversation_url"] == "https://chatgpt.com/c/old2"
    assert sessions["claude"]["role"] == "Engineer"
    assert sessions["claude"]["preferred_model"] == "Opus"


def test_migration_marks_migrated_sessions_current(legacy_db_path, settings_for):
    path, project_id = legacy_db_path
    settings = settings_for(path)
    for s in db.list_ai_sessions(project_id, settings=settings):
        assert s["current"] is True


def test_migration_does_not_modify_ai_workspace_table(legacy_db_path, settings_for):
    path, project_id = legacy_db_path
    settings = settings_for(path)

    # Trigger the migration (any db.py call opens a connection -> ensure_schema).
    db.list_ai_sessions(project_id, settings=settings)

    workspace = db.get_ai_workspace(project_id, settings=settings)
    assert workspace["claude_url"] == "https://claude.ai/chat/old1"
    assert workspace["chatgpt_url"] == "https://chatgpt.com/c/old2"


def test_migration_runs_at_most_once(legacy_db_path, settings_for):
    path, project_id = legacy_db_path
    settings = settings_for(path)

    first = db.list_ai_sessions(project_id, settings=settings)
    # Open several more connections (each would normally re-run ensure_schema).
    db.list_ai_sessions(project_id, settings=settings)
    db.list_ai_sessions(project_id, settings=settings)
    second = db.list_ai_sessions(project_id, settings=settings)

    assert len(first) == len(second) == 2  # not duplicated


def test_migration_is_a_no_op_for_a_brand_new_database(tmp_path, settings_for):
    """A database with no ai_workspace rows at all (a fresh v1.4
    install) must not create any phantom sessions."""
    settings = settings_for(tmp_path / "fresh.db")
    project = db.create_project(name="Fresh", workspace="Products", settings=settings)
    assert db.list_ai_sessions(project["id"], settings=settings) == []


def test_migration_recorded_in_schema_migrations(legacy_db_path, settings_for):
    path, project_id = legacy_db_path
    settings = settings_for(path)
    db.list_ai_sessions(project_id, settings=settings)  # trigger

    with db.get_connection(settings) as conn:
        rows = conn.execute("SELECT id FROM schema_migrations").fetchall()
    assert {r["id"] for r in rows} == {"0001_ai_sessions_from_ai_workspace"}
