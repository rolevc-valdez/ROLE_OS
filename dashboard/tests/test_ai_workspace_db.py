"""Unit tests for the AI Workspace persistence layer (app.projects.db's
get_ai_workspace / save_ai_workspace / touch_ai_workspace_last_opened),
ROLE OS v1.3.

Each test gets its own isolated SQLite file via a temporary
ROLE_OS_PROJECTS_DB_PATH, so tests never share or mutate state -- same
pattern as test_projects_db.py.
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
    return db.create_project(name="AI Workspace Test", workspace="Products", settings=settings)


def test_get_ai_workspace_none_when_never_saved(settings, project):
    assert db.get_ai_workspace(project["id"], settings) is None


def test_save_ai_workspace_creates_row(settings, project):
    saved = db.save_ai_workspace(
        project["id"], claude_url="https://claude.ai/chat/abc", role="Engineer", settings=settings
    )
    assert saved["project_id"] == project["id"]
    assert saved["claude_url"] == "https://claude.ai/chat/abc"
    assert saved["role"] == "Engineer"
    assert saved["chatgpt_url"] == ""
    assert saved["gemini_url"] == ""
    assert saved["preferred_model"] == ""
    assert saved["last_opened_at"] is None
    assert saved["created_at"] == saved["updated_at"]


def test_save_ai_workspace_partial_update_does_not_clobber_other_fields(settings, project):
    db.save_ai_workspace(
        project["id"], claude_url="https://claude.ai/chat/abc", role="Engineer", settings=settings
    )
    updated = db.save_ai_workspace(
        project["id"], chatgpt_url="https://chatgpt.com/c/xyz", settings=settings
    )
    assert updated["claude_url"] == "https://claude.ai/chat/abc"
    assert updated["role"] == "Engineer"
    assert updated["chatgpt_url"] == "https://chatgpt.com/c/xyz"


def test_save_ai_workspace_can_overwrite_a_field(settings, project):
    db.save_ai_workspace(project["id"], claude_url="https://claude.ai/chat/old", settings=settings)
    updated = db.save_ai_workspace(
        project["id"], claude_url="https://claude.ai/chat/new", settings=settings
    )
    assert updated["claude_url"] == "https://claude.ai/chat/new"


def test_save_ai_workspace_updated_at_advances(settings, project):
    first = db.save_ai_workspace(project["id"], role="Engineer", settings=settings)
    second = db.save_ai_workspace(project["id"], role="Architect", settings=settings)
    assert second["updated_at"] >= first["updated_at"]
    assert second["created_at"] == first["created_at"]


def test_touch_last_opened_creates_row_if_none_exists(settings, project):
    assert db.get_ai_workspace(project["id"], settings) is None
    touched = db.touch_ai_workspace_last_opened(project["id"], settings=settings)
    assert touched["last_opened_at"] is not None
    assert touched["claude_url"] == ""


def test_touch_last_opened_preserves_existing_urls(settings, project):
    db.save_ai_workspace(project["id"], claude_url="https://claude.ai/chat/abc", settings=settings)
    touched = db.touch_ai_workspace_last_opened(project["id"], settings=settings)
    assert touched["claude_url"] == "https://claude.ai/chat/abc"
    assert touched["last_opened_at"] is not None


def test_ai_workspace_is_isolated_per_project(settings):
    p1 = db.create_project(name="P1", workspace="Products", settings=settings)
    p2 = db.create_project(name="P2", workspace="Products", settings=settings)
    db.save_ai_workspace(p1["id"], claude_url="https://claude.ai/chat/p1", settings=settings)
    assert db.get_ai_workspace(p2["id"], settings) is None
    assert db.get_ai_workspace(p1["id"], settings)["claude_url"] == "https://claude.ai/chat/p1"
