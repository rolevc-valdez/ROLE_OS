"""Tests for the Resume Work orchestration (Sprint 5 §3; redesigned around
Project Memory in Sprint C7.1): `app.workspace.resume`. Calls only
existing, unmodified `app.projects` functions -- these tests verify the
*sequencing*, not new AI-session logic.

Hotfix (Session Intent): a manually-created PI project with no
filesystem root has no evidence anywhere (no README/ROADMAP/TODO to
read, no Discovery-based Operational Intelligence rule can fire, no
Daily Session/Snapshot recorded) -- exactly the "nothing trustworthy"
case the no-action guard exists for. These tests are about session
*plumbing* (reuse, retitle, snapshot influence, URL resolution), not
requested-action derivation, so they pass a `user_objective` explicitly
(the same as a real user answering the Cockpit guard prompt) to bypass
the guard and reach the behavior actually under test.
"""

from __future__ import annotations

import pytest
from app.config import Settings
from app.projects import db as projects_db
from app.workspace import resume

_TEST_OBJECTIVE = {"requested_action": "Ship the release"}


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    return Settings()


def test_resume_work_unknown_project_returns_none(settings):
    assert resume.resume_work("does-not-exist", settings=settings) is None


def test_resume_work_requires_user_objective_when_no_evidence_exists(settings):
    """The hotfix's own contract: a manually-created project with no
    filesystem/session/snapshot evidence must trigger the no-action
    guard, not silently resume with "Continue this project"."""
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    result = resume.resume_work(project["id"], settings=settings)
    assert result["requires_user_objective"] is True
    assert "prompt" not in result


def test_resume_work_creates_first_session_with_zero_manual_creation(settings):
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    result = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    assert result is not None
    assert result["is_new_session"] is True
    assert result["project_id"] == project["id"]

    sessions = projects_db.list_ai_sessions(project["id"], settings=settings)
    assert len(sessions) == 1
    assert sessions[0]["id"] == result["session_id"]
    assert sessions[0]["current"] is True
    # Sprint C7.1: never "Resume Work"/"Untitled"/"Session 1" -- always
    # "<Project Name> -- <Objective>".
    assert sessions[0]["title"] == "My App — Continue this project"
    assert "session_selection_reason" in result


def test_resume_work_self_heals_a_session_named_resume_work(settings):
    """A session created under the old, session-centric flow (literally
    titled "Resume Work") gets retitled the moment it's next resumed --
    the bug this sprint fixes never persists forever."""
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    legacy_session = projects_db.create_ai_session(
        project["id"], assistant="claude", title="Resume Work", settings=settings
    )
    result = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    assert result["session_id"] == legacy_session["id"]
    refreshed = projects_db.get_ai_session(legacy_session["id"], settings=settings)
    assert refreshed["title"] != "Resume Work"
    assert refreshed["title"].startswith("My App —")


def test_resume_work_reuses_existing_session_not_creating_a_duplicate(settings):
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    first = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    second = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)

    assert second["is_new_session"] is False
    assert second["session_id"] == first["session_id"]
    assert len(projects_db.list_ai_sessions(project["id"], settings=settings)) == 1


def test_resume_work_prompt_reflects_latest_snapshot(settings):
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    first = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    projects_db.create_ai_session_snapshot(
        first["session_id"],
        summary="made progress",
        next_prompt="ship the release",
        settings=settings,
    )

    second = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    assert "made progress" in second["prompt"]
    assert "ship the release" in second["prompt"]


def test_resume_work_no_snapshot_yet_uses_fallback_prompt(settings):
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    result = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    assert "Where We Left Off:\nNo prior activity recorded." in result["prompt"]
    assert "Pending Work:\nNone recorded." in result["prompt"]


def test_resume_work_resolves_saved_conversation_url_when_present(settings):
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    result = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    projects_db.update_ai_session(
        result["session_id"],
        {"conversation_url": "https://claude.ai/chat/abc123"},
        settings=settings,
    )

    second = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    assert second["url"] == "https://claude.ai/chat/abc123"
    assert second["used_saved_conversation"] is True


def test_resume_work_falls_back_to_assistant_homepage(settings):
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    result = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    assert result["url"] == "https://claude.ai"
    assert result["used_saved_conversation"] is False


def test_resume_work_touches_last_used(settings):
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    result = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)
    session = projects_db.get_ai_session(result["session_id"], settings=settings)
    assert session["last_used_at"] is not None


def test_resume_work_marks_session_current(settings):
    project = projects_db.create_project(name="My App", workspace="Products", settings=settings)
    # Create an older, non-current session first.
    old_session = projects_db.create_ai_session(
        project["id"], assistant="chatgpt", title="old session", settings=settings
    )
    result = resume.resume_work(project["id"], settings=settings, user_objective=_TEST_OBJECTIVE)

    refreshed_old = projects_db.get_ai_session(old_session["id"], settings=settings)
    refreshed_new = projects_db.get_ai_session(result["session_id"], settings=settings)
    assert refreshed_new["current"] is True
    # Only meaningful if resume picked the pre-existing session (it should,
    # since list_ai_sessions returns the most relevant one first).
    if result["session_id"] == old_session["id"]:
        assert refreshed_old["current"] is True
    else:
        assert refreshed_old["current"] is False
