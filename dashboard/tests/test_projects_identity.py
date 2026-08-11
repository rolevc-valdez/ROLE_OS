"""Tests for the canonical-identity bridge columns/functions added to
`app.projects.db` in Sprint 5 (Project Unification): `discovery_item_id`,
`get_project_by_discovery_item_id`, `find_unlinked_project_by_name`,
`link_project_to_discovery_item`.
"""

from __future__ import annotations

import sqlite3

import pytest
from app.config import Settings
from app.projects import db


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    return Settings()


def test_new_project_has_no_discovery_item_id_by_default(settings):
    project = db.create_project(name="Manual Project", workspace="Products", settings=settings)
    assert project["discovery_item_id"] is None


def test_link_project_to_discovery_item(settings):
    project = db.create_project(name="My App", workspace="Products", settings=settings)
    linked = db.link_project_to_discovery_item(project["id"], "abc123", settings=settings)
    assert linked["discovery_item_id"] == "abc123"


def test_link_unknown_project_returns_none(settings):
    assert db.link_project_to_discovery_item("does-not-exist", "abc123", settings=settings) is None


def test_get_project_by_discovery_item_id(settings):
    project = db.create_project(name="My App", workspace="Products", settings=settings)
    db.link_project_to_discovery_item(project["id"], "abc123", settings=settings)
    found = db.get_project_by_discovery_item_id("abc123", settings=settings)
    assert found["id"] == project["id"]


def test_get_project_by_discovery_item_id_returns_none_when_unlinked(settings):
    assert db.get_project_by_discovery_item_id("nope", settings=settings) is None


def test_find_unlinked_project_by_name_case_insensitive(settings):
    db.create_project(name="ROLE_OS", workspace="Products", settings=settings)
    found = db.find_unlinked_project_by_name("role_os", settings=settings)
    assert found is not None
    assert found["name"] == "ROLE_OS"


def test_find_unlinked_project_by_name_excludes_already_linked(settings):
    project = db.create_project(name="ROLE_OS", workspace="Products", settings=settings)
    db.link_project_to_discovery_item(project["id"], "abc123", settings=settings)
    assert db.find_unlinked_project_by_name("ROLE_OS", settings=settings) is None


def test_find_unlinked_project_by_name_no_match(settings):
    assert db.find_unlinked_project_by_name("Nonexistent Name", settings=settings) is None


def test_discovery_item_id_is_unique(settings):
    p1 = db.create_project(name="A", workspace="Products", settings=settings)
    p2 = db.create_project(name="B", workspace="Products", settings=settings)
    db.link_project_to_discovery_item(p1["id"], "same-item-id", settings=settings)
    with pytest.raises(sqlite3.IntegrityError):
        db.link_project_to_discovery_item(p2["id"], "same-item-id", settings=settings)


def test_schema_migration_is_idempotent_across_repeated_connections(settings):
    # ensure_schema runs on every get_connection call; opening several
    # connections in a row must never raise "duplicate column".
    db.create_project(name="A", workspace="Products", settings=settings)
    db.list_projects(settings=settings)
    db.list_projects(settings=settings)
    project = db.create_project(name="B", workspace="Products", settings=settings)
    assert project["discovery_item_id"] is None


def test_existing_project_fields_untouched_by_linking(settings):
    """Never destroy user data (§7): linking only ever sets the new
    nullable column, nothing else about the row changes."""
    project = db.create_project(
        name="My App",
        workspace="Products",
        description="important notes",
        priority="high",
        settings=settings,
    )
    db.add_collection_item(project["id"], "notes", {"text": "a note"}, settings=settings)
    linked = db.link_project_to_discovery_item(project["id"], "abc123", settings=settings)
    assert linked["description"] == "important notes"
    assert linked["priority"] == "high"
    assert len(linked["notes"]) == 1
    assert linked["notes"][0]["text"] == "a note"
