"""Unit tests for the Daily Session persistence layer (app.session.db).

Each test gets its own isolated SQLite file via a temporary
ROLE_OS_SESSION_DB_PATH, so tests never share or mutate state -- same
pattern as test_projects_db.py.
"""

from __future__ import annotations

import pytest
from app.config import Settings
from app.session import db


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_SESSION_DB_PATH", str(tmp_path / "session.db"))
    return Settings()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_seeds_at_least_the_seven_required_projects(settings):
    names = {p["name"] for p in db.list_registry_projects(settings)}
    required = {
        "ROLE OS",
        "ROLE ECOSYSTEM",
        "ROLE MASTER",
        "ROLE Commerce Factory",
        "Brand Character OS",
        "RoleValdez",
        "SUPER FACIL",
    }
    assert required.issubset(names)


def test_registry_seed_marks_defaults_vs_authoritative(settings):
    projects = {p["id"]: p for p in db.list_registry_projects(settings)}
    # ROLE Commerce Factory's seed values came from real, recently-written
    # ecosystem documents -- not a placeholder.
    assert projects["role-commerce-factory"]["is_authoritative"] is True
    assert projects["role-commerce-factory"]["is_default"] is False
    # ROLE MASTER's seed milestone/next_action are honest placeholders.
    assert projects["role-master"]["is_authoritative"] is False
    assert projects["role-master"]["is_default"] is True


def test_registry_seeds_only_once(settings):
    first = db.list_registry_projects(settings)
    second = db.list_registry_projects(settings)
    assert len(first) == len(second)


def test_update_registry_project_marks_user_edited(settings):
    project = db.list_registry_projects(settings)[0]
    updated = db.update_registry_project(
        project["id"], {"milestone": "New milestone", "next_action": "New action"}, settings
    )
    assert updated["milestone"] == "New milestone"
    assert updated["next_action"] == "New action"
    assert updated["user_edited"] is True
    assert updated["is_default"] is False


def test_update_registry_project_missing_returns_none(settings):
    assert db.update_registry_project("does-not-exist", {"status": "x"}, settings) is None


def test_update_registry_project_ignores_unknown_fields(settings):
    project = db.list_registry_projects(settings)[0]
    updated = db.update_registry_project(project["id"], {"name": "Should not change"}, settings)
    assert updated["name"] == project["name"]


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def _start(settings, **overrides):
    payload = {
        "date": "2026-07-30",
        "project_id": "role-os",
        "project_name": "ROLE OS",
        "mode": "BUILD",
        "objective": "Ship the dashboard MVP",
        "expected_result": "A working local dashboard",
    }
    payload.update(overrides)
    return db.start_session(settings=settings, **payload)


def test_get_active_session_none_when_nothing_started(settings):
    assert db.get_active_session(settings) is None


def test_start_session_creates_active_session(settings):
    session = _start(settings)
    assert session["status"] == "active"
    assert session["project_name"] == "ROLE OS"
    assert session["mode"] == "BUILD"
    assert db.get_active_session(settings)["id"] == session["id"]


def test_start_session_rejects_second_active_session(settings):
    _start(settings)
    with pytest.raises(ValueError):
        _start(settings, project_name="Something else")


def test_complete_session_closes_it_and_records_fields(settings):
    session = _start(settings)
    completed = db.complete_session(
        session["id"],
        completed_work="Built the session domain",
        decisions="Own SQLite store per domain",
        blockers="None",
        next_step="Write tests",
        settings=settings,
    )
    assert completed["status"] == "completed"
    assert completed["completed_work"] == "Built the session domain"
    assert completed["completed_at"] is not None
    assert db.get_active_session(settings) is None


def test_start_session_allowed_again_after_completion(settings):
    first = _start(settings)
    db.complete_session(
        first["id"],
        completed_work="done",
        decisions="",
        blockers="",
        next_step="",
        settings=settings,
    )
    second = _start(settings, project_name="ROLE Commerce Factory")
    assert second["id"] != first["id"]
    assert db.get_active_session(settings)["id"] == second["id"]


def test_complete_session_missing_returns_none(settings):
    assert (
        db.complete_session(
            "does-not-exist",
            completed_work="x",
            decisions="",
            blockers="",
            next_step="",
            settings=settings,
        )
        is None
    )


def test_list_sessions_orders_most_recent_first(settings):
    first = _start(settings)
    db.complete_session(
        first["id"], completed_work="a", decisions="", blockers="", next_step="", settings=settings
    )
    second = _start(settings, project_name="ROLE ECOSYSTEM")
    sessions = db.list_sessions(settings=settings)
    assert sessions[0]["id"] == second["id"]
    assert sessions[1]["id"] == first["id"]


def test_data_persists_across_new_connections(settings):
    """Simulates an app restart: a brand-new connection to the same file
    must see everything a previous connection wrote."""
    session = _start(settings)
    db.update_registry_project("role-os", {"status": "Restarted-check"}, settings)

    # New Settings instance pointing at the same path, new connections.
    reloaded_settings = Settings()
    assert reloaded_settings.session_db_path == settings.session_db_path
    assert db.get_session(session["id"], reloaded_settings)["id"] == session["id"]
    assert db.get_registry_project("role-os", reloaded_settings)["status"] == "Restarted-check"
