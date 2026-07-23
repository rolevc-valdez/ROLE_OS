"""Unit tests for the Project Intelligence persistence layer (app.projects.db).

Each test gets its own isolated SQLite file via a temporary
ROLE_OS_PROJECTS_DB_PATH, so tests never share or mutate state.
"""

from __future__ import annotations

import os

import pytest

from app.config import Settings
from app.projects import db


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    return Settings()


def test_default_workspaces_are_seeded(settings):
    names = {w["name"] for w in db.list_workspaces(settings)}
    assert names == {"Personal", "Kontoor", "Unger", "Products", "Ideas", "Library"}


def test_get_or_create_workspace_creates_once(settings):
    first = db.get_or_create_workspace("Personal", settings)
    second = db.get_or_create_workspace("Personal", settings)
    assert first["id"] == second["id"]


def test_create_project_resolves_workspace_by_name(settings):
    project = db.create_project(name="ROLE Master", workspace="Products", settings=settings)
    assert project["workspace"] == "Products"
    assert project["status"] == "active"
    assert project["health_score"] == 0
    assert project["tags"] == []


def test_create_project_with_new_workspace_name_creates_workspace(settings):
    project = db.create_project(name="X", workspace="Brand New Workspace", settings=settings)
    assert project["workspace"] == "Brand New Workspace"
    assert db.get_workspace_by_name("Brand New Workspace", settings) is not None


def test_get_project_returns_none_when_missing(settings):
    assert db.get_project("does-not-exist", settings) is None


def test_list_projects_filters_by_workspace_status_priority_tag(settings):
    db.create_project(name="A", workspace="Products", status="active", priority="high", tags=["x"], settings=settings)
    db.create_project(name="B", workspace="Ideas", status="paused", priority="low", tags=["y"], settings=settings)

    assert {p["name"] for p in db.list_projects(workspace="Products", settings=settings)} == {"A"}
    assert {p["name"] for p in db.list_projects(status="paused", settings=settings)} == {"B"}
    assert {p["name"] for p in db.list_projects(priority="high", settings=settings)} == {"A"}
    assert {p["name"] for p in db.list_projects(tag="y", settings=settings)} == {"B"}


def test_update_project_patches_fields_and_workspace(settings):
    project = db.create_project(name="A", workspace="Products", settings=settings)
    updated = db.update_project(
        project["id"], {"status": "at_risk", "tags": ["core"], "workspace": "Ideas"}, settings
    )
    assert updated["status"] == "at_risk"
    assert updated["tags"] == ["core"]
    assert updated["workspace"] == "Ideas"


def test_update_project_returns_none_when_missing(settings):
    assert db.update_project("nope", {"status": "paused"}, settings) is None


def test_delete_project_removes_it_and_related_rows(settings):
    a = db.create_project(name="A", workspace="Products", settings=settings)
    b = db.create_project(name="B", workspace="Products", settings=settings)
    cap = db.create_capability(a["id"], "Cap", settings=settings)
    db.consume_capability(cap["id"], b["id"], settings=settings)
    db.create_dependency(b["id"], a["id"], settings=settings)

    assert db.delete_project(a["id"], settings) is True
    assert db.get_project(a["id"], settings) is None
    assert db.list_capabilities(project_id=a["id"], settings=settings) == []
    assert db.list_dependencies(b["id"], settings) == []


def test_delete_project_returns_false_when_missing(settings):
    assert db.delete_project("nope", settings) is False


@pytest.mark.parametrize("field", list(db.COLLECTION_FIELDS))
def test_collection_item_crud(settings, field):
    project = db.create_project(name="A", workspace="Products", settings=settings)

    item = db.add_collection_item(project["id"], field, {"text": "hello"}, settings)
    assert item["text"] == "hello"
    assert item["id"]

    items = db.list_collection_items(project["id"], field, settings)
    assert len(items) == 1

    updated = db.update_collection_item(project["id"], field, item["id"], {"status": "done"}, settings)
    assert updated["status"] == "done"

    assert db.delete_collection_item(project["id"], field, item["id"], settings) is True
    assert db.list_collection_items(project["id"], field, settings) == []


def test_collection_item_operations_return_none_for_missing_project(settings):
    assert db.add_collection_item("nope", "notes", {"text": "x"}, settings) is None
    assert db.list_collection_items("nope", "notes", settings) is None
    assert db.update_collection_item("nope", "notes", "item", {}, settings) is None
    assert db.delete_collection_item("nope", "notes", "item", settings) is False


def test_conversation_link_and_unlink(settings):
    project = db.create_project(name="A", workspace="Products", settings=settings)
    db.link_conversation(project["id"], "conv-1", settings)
    db.link_conversation(project["id"], "conv-1", settings)  # idempotent
    assert db.get_project(project["id"], settings)["conversations"] == ["conv-1"]
    assert db.unlink_conversation(project["id"], "conv-1", settings) is True
    assert db.get_project(project["id"], settings)["conversations"] == []
    assert db.unlink_conversation(project["id"], "conv-1", settings) is False


def test_related_project_link_and_unlink(settings):
    a = db.create_project(name="A", workspace="Products", settings=settings)
    b = db.create_project(name="B", workspace="Products", settings=settings)
    db.link_related_project(a["id"], b["id"], settings)
    assert db.get_project(a["id"], settings)["related_projects"] == [b["id"]]
    assert db.unlink_related_project(a["id"], b["id"], settings) is True


def test_capability_create_consume_and_list(settings):
    provider = db.create_project(name="ROLE Master", workspace="Products", settings=settings)
    consumer = db.create_project(name="SUPER FACIL", workspace="Products", settings=settings)

    cap = db.create_capability(provider["id"], "Brand Identity", "Logo + style", "branding", settings)
    assert cap["project_id"] == provider["id"]

    assert db.consume_capability(cap["id"], consumer["id"], settings) is not None
    # Consuming twice is idempotent (no duplicate rows / no error).
    assert db.consume_capability(cap["id"], consumer["id"], settings) is not None

    consumers = db.list_capability_consumers(cap["id"], settings)
    assert len(consumers) == 1
    assert consumers[0]["project_name"] == "SUPER FACIL"

    consumed = db.list_consumed_capabilities(consumer["id"], settings)
    assert len(consumed) == 1
    assert consumed[0]["provider_project_name"] == "ROLE Master"

    assert db.remove_capability_consumer(cap["id"], consumer["id"], settings) is True
    assert db.list_consumed_capabilities(consumer["id"], settings) == []


def test_capability_create_returns_none_for_missing_project(settings):
    assert db.create_capability("nope", "Cap", settings=settings) is None


def test_capability_search_by_query(settings):
    provider = db.create_project(name="A", workspace="Products", settings=settings)
    db.create_capability(provider["id"], "Brand Identity", settings=settings)
    db.create_capability(provider["id"], "Master Prompt", settings=settings)

    results = db.list_capabilities(q="Brand", settings=settings)
    assert [c["name"] for c in results] == ["Brand Identity"]


def test_dependency_create_list_and_dependents(settings):
    a = db.create_project(name="ROLE Master", workspace="Products", settings=settings)
    b = db.create_project(name="SUPER FACIL", workspace="Products", settings=settings)

    dep = db.create_dependency(b["id"], a["id"], "needs branding", settings)
    assert dep["depends_on_project_id"] == a["id"]

    deps = db.list_dependencies(b["id"], settings)
    assert deps[0]["depends_on_project_name"] == "ROLE Master"

    dependents = db.list_dependents(a["id"], settings)
    assert dependents[0]["dependent_project_name"] == "SUPER FACIL"

    assert db.delete_dependency(dep["id"], settings) is True
    assert db.list_dependencies(b["id"], settings) == []


def test_dependency_rejects_self_dependency(settings):
    a = db.create_project(name="A", workspace="Products", settings=settings)
    assert db.create_dependency(a["id"], a["id"], settings=settings) is None


def test_dependency_returns_none_for_missing_projects(settings):
    a = db.create_project(name="A", workspace="Products", settings=settings)
    assert db.create_dependency(a["id"], "nope", settings=settings) is None
    assert db.create_dependency("nope", a["id"], settings=settings) is None
