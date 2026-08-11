"""Unit tests for the AI Sessions / Session Snapshots / Project Timeline
persistence layer (app.projects.db), ROLE OS v1.4 "Context Engine".

Each test gets its own isolated SQLite file via a temporary
ROLE_OS_PROJECTS_DB_PATH -- same pattern as test_projects_db.py.
"""

from __future__ import annotations

import pytest
from app.config import Settings
from app.projects import db


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    return Settings()


@pytest.fixture
def project(settings):
    return db.create_project(name="Context Engine Test", workspace="Products", settings=settings)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def test_create_ai_session_defaults(settings, project):
    session = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    assert session["project_id"] == project["id"]
    assert session["assistant"] == "claude"
    assert session["title"] == ""
    assert session["status"] == "active"
    assert session["favorite"] is False
    assert session["current"] is False
    assert session["last_used_at"] is None


def test_create_ai_session_missing_project_returns_none(settings):
    assert db.create_ai_session("does-not-exist", assistant="claude", settings=settings) is None


def test_multiple_sessions_per_assistant_supported(settings, project):
    s1 = db.create_ai_session(project["id"], assistant="claude", title="First", settings=settings)
    s2 = db.create_ai_session(project["id"], assistant="claude", title="Second", settings=settings)
    sessions = db.list_ai_sessions(project["id"], settings=settings)
    assert {s1["id"], s2["id"]} <= {s["id"] for s in sessions}
    assert len(sessions) == 2


def test_list_ai_sessions_filters_by_assistant(settings, project):
    db.create_ai_session(project["id"], assistant="claude", settings=settings)
    db.create_ai_session(project["id"], assistant="chatgpt", settings=settings)
    claude_only = db.list_ai_sessions(project["id"], assistant="claude", settings=settings)
    assert len(claude_only) == 1
    assert claude_only[0]["assistant"] == "claude"


def test_list_ai_sessions_filters_by_status(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    db.update_ai_session(s["id"], {"status": "completed"}, settings=settings)
    db.create_ai_session(project["id"], assistant="chatgpt", settings=settings)
    active = db.list_ai_sessions(project["id"], status="active", settings=settings)
    assert len(active) == 1
    assert active[0]["assistant"] == "chatgpt"


def test_list_ai_sessions_filters_by_favorite(settings, project):
    s1 = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    db.create_ai_session(project["id"], assistant="chatgpt", settings=settings)
    db.update_ai_session(s1["id"], {"favorite": True}, settings=settings)
    favorites = db.list_ai_sessions(project["id"], favorite=True, settings=settings)
    assert len(favorites) == 1
    assert favorites[0]["id"] == s1["id"]


def test_update_ai_session_partial(settings, project):
    s = db.create_ai_session(
        project["id"], assistant="claude", title="Original", role="Engineer", settings=settings
    )
    updated = db.update_ai_session(s["id"], {"role": "Architect"}, settings=settings)
    assert updated["role"] == "Architect"
    assert updated["title"] == "Original"  # untouched


def test_update_ai_session_favorite_toggle(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    assert db.update_ai_session(s["id"], {"favorite": True}, settings=settings)["favorite"] is True
    assert (
        db.update_ai_session(s["id"], {"favorite": False}, settings=settings)["favorite"] is False
    )


def test_update_ai_session_missing_returns_none(settings):
    assert db.update_ai_session("does-not-exist", {"title": "x"}, settings=settings) is None


def test_delete_ai_session(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    assert db.delete_ai_session(s["id"], settings=settings) is True
    assert db.get_ai_session(s["id"], settings=settings) is None


def test_delete_ai_session_missing_returns_false(settings):
    assert db.delete_ai_session("does-not-exist", settings=settings) is False


def test_delete_ai_session_cascades_snapshots(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    db.create_ai_session_snapshot(s["id"], summary="test", settings=settings)
    db.delete_ai_session(s["id"], settings=settings)
    assert db.list_ai_session_snapshots(s["id"], settings=settings) == []


def test_set_current_scoped_per_assistant(settings, project):
    claude1 = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    claude2 = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    chatgpt1 = db.create_ai_session(project["id"], assistant="chatgpt", settings=settings)

    db.set_ai_session_current(claude1["id"], settings=settings)
    db.set_ai_session_current(chatgpt1["id"], settings=settings)

    assert db.get_ai_session(claude1["id"], settings=settings)["current"] is True
    assert db.get_ai_session(chatgpt1["id"], settings=settings)["current"] is True

    db.set_ai_session_current(claude2["id"], settings=settings)
    assert db.get_ai_session(claude1["id"], settings=settings)["current"] is False
    assert db.get_ai_session(claude2["id"], settings=settings)["current"] is True
    # chatgpt's current session is untouched by a claude-scoped change
    assert db.get_ai_session(chatgpt1["id"], settings=settings)["current"] is True


def test_touch_last_used(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    assert s["last_used_at"] is None
    touched = db.touch_ai_session_last_used(s["id"], settings=settings)
    assert touched["last_used_at"] is not None


def test_touch_last_used_missing_returns_none(settings):
    assert db.touch_ai_session_last_used("does-not-exist", settings=settings) is None


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def test_create_snapshot(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    snap = db.create_ai_session_snapshot(
        s["id"], accomplishments="Did X", next_prompt="Do Y", settings=settings
    )
    assert snap["session_id"] == s["id"]
    assert snap["accomplishments"] == "Did X"
    assert snap["next_prompt"] == "Do Y"
    assert snap["blockers"] == ""


def test_create_snapshot_missing_session_returns_none(settings):
    assert db.create_ai_session_snapshot("does-not-exist", settings=settings) is None


def test_a_session_can_have_multiple_snapshots(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    db.create_ai_session_snapshot(s["id"], summary="first", settings=settings)
    db.create_ai_session_snapshot(s["id"], summary="second", settings=settings)
    snapshots = db.list_ai_session_snapshots(s["id"], settings=settings)
    assert len(snapshots) == 2


def test_list_snapshots_most_recent_first(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    db.create_ai_session_snapshot(s["id"], summary="first", settings=settings)
    db.create_ai_session_snapshot(s["id"], summary="second", settings=settings)
    snapshots = db.list_ai_session_snapshots(s["id"], settings=settings)
    assert snapshots[0]["summary"] == "second"


def test_get_latest_snapshot(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", settings=settings)
    assert db.get_latest_snapshot(s["id"], settings=settings) is None
    db.create_ai_session_snapshot(s["id"], summary="first", settings=settings)
    db.create_ai_session_snapshot(s["id"], summary="second", settings=settings)
    assert db.get_latest_snapshot(s["id"], settings=settings)["summary"] == "second"


# ---------------------------------------------------------------------------
# Project Timeline
# ---------------------------------------------------------------------------


def test_timeline_includes_session_start_and_snapshot_events(settings, project):
    s = db.create_ai_session(project["id"], assistant="claude", title="Refactor", settings=settings)
    db.create_ai_session_snapshot(s["id"], summary="progress", settings=settings)
    timeline = db.list_project_timeline(project["id"], settings=settings)
    types = [e["type"] for e in timeline]
    assert types == ["session_started", "snapshot"]


def test_timeline_is_sorted_chronologically(settings, project):
    s1 = db.create_ai_session(project["id"], assistant="claude", title="A", settings=settings)
    s2 = db.create_ai_session(project["id"], assistant="chatgpt", title="B", settings=settings)
    timeline = db.list_project_timeline(project["id"], settings=settings)
    timestamps = [e["timestamp"] for e in timeline]
    assert timestamps == sorted(timestamps)
    assert {e["session_id"] for e in timeline} == {s1["id"], s2["id"]}


def test_timeline_empty_for_project_with_no_sessions(settings, project):
    assert db.list_project_timeline(project["id"], settings=settings) == []
