"""Tests for the canonical Project Identity bridge (Sprint 5 §1):
`app.workspace.identity`. Real Discovery Engine runs against synthetic
folder trees throughout -- nothing mocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.projects import db as projects_db
from app.workspace import identity, service


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "proj" / "projects.db"))
    return Settings()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _adopt_real_project(tmp_path, settings, name="my-app"):
    root = tmp_path / "scan-root"
    _write(root / name / "README.md", "x")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    service.rescan(settings=settings, root=str(root))
    items = service.list_hierarchy(view="top_level", settings=settings)
    item = next(i for i in items if i["name"] == name)
    service.adopt_item(item["id"], settings=settings)
    return item


def test_creates_new_canonical_project_when_no_match_exists(tmp_path, settings):
    item = _adopt_real_project(tmp_path, settings)
    project_id = identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    project = projects_db.get_project(project_id, settings=settings)
    assert project is not None
    assert project["name"] == "my-app"
    assert project["discovery_item_id"] == item["id"]


def test_idempotent_second_call_returns_same_project(tmp_path, settings):
    item = _adopt_real_project(tmp_path, settings)
    first = identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    second = identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    assert first == second
    assert len(projects_db.list_projects(settings=settings)) == 1


def test_links_to_existing_unlinked_manual_project_by_name(tmp_path, settings):
    manual = projects_db.create_project(
        name="my-app", workspace="Products", description="hand-typed notes", settings=settings
    )
    item = _adopt_real_project(tmp_path, settings)
    resolved_id = identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    assert resolved_id == manual["id"]
    assert len(projects_db.list_projects(settings=settings)) == 1
    # Never destroy user data.
    project = projects_db.get_project(manual["id"], settings=settings)
    assert project["description"] == "hand-typed notes"


def test_two_different_items_never_collide_on_the_same_project(tmp_path, settings):
    item_a = _adopt_real_project(tmp_path, settings, name="app-a")
    item_b = _adopt_real_project(tmp_path, settings, name="app-b")
    id_a = identity.get_or_create_canonical_project_id(
        item_a["id"], item_a["root_path"], item_a["name"], settings=settings
    )
    id_b = identity.get_or_create_canonical_project_id(
        item_b["id"], item_b["root_path"], item_b["name"], settings=settings
    )
    assert id_a != id_b


def test_get_canonical_project_id_read_only_never_creates_for_unadopted_item(tmp_path, settings):
    root = tmp_path / "scan-root"
    _write(root / "my-app" / "README.md", "x")
    _write(root / "my-app" / "pyproject.toml", "[project]\nname='a'")
    service.rescan(settings=settings, root=str(root))
    items = service.list_hierarchy(view="top_level", settings=settings)
    item = items[0]  # never adopted

    assert identity.get_canonical_project_id(item["id"], settings=settings) is None
    assert projects_db.list_projects(settings=settings) == []


def test_adopt_item_itself_resolves_a_canonical_project_automatically(tmp_path, settings):
    """§2/§7: adoption is what makes AI Sessions work with zero manual
    creation -- `service.adopt_item` (not just `identity` directly) must
    already have resolved a canonical identity by the time it returns."""
    item = _adopt_real_project(tmp_path, settings)
    assert identity.get_canonical_project_id(item["id"], settings=settings) is not None


def test_get_canonical_project_id_returns_resolved_id(tmp_path, settings):
    item = _adopt_real_project(tmp_path, settings)
    created_id = identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    assert identity.get_canonical_project_id(item["id"], settings=settings) == created_id


def test_get_canonical_project_returns_full_project_dict(tmp_path, settings):
    item = _adopt_real_project(tmp_path, settings)
    identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    project = identity.get_canonical_project(item["id"], settings=settings)
    assert project is not None
    assert project["name"] == "my-app"


def test_stale_link_self_heals(tmp_path, settings):
    """If the linked Project row was deleted out-of-band, resolution must
    not return a dangling id -- it re-resolves a fresh one."""
    item = _adopt_real_project(tmp_path, settings)
    old_id = identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    projects_db.delete_project(old_id, settings=settings)

    new_id = identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    assert new_id != old_id
    assert projects_db.get_project(new_id, settings=settings) is not None


def test_real_path_with_spaces_and_parentheses(tmp_path, settings):
    root = tmp_path / "My Drive (test@example.com)" / "1 - IA PROJECTS"
    _write(root / "my-app" / "README.md", "x")
    _write(root / "my-app" / "pyproject.toml", "[project]\nname='a'")
    service.rescan(settings=settings, root=str(root))
    items = service.list_hierarchy(view="top_level", settings=settings)
    item = next(i for i in items if i["name"] == "my-app")
    service.adopt_item(item["id"], settings=settings)

    project_id = identity.get_or_create_canonical_project_id(
        item["id"], item["root_path"], item["name"], settings=settings
    )
    assert projects_db.get_project(project_id, settings=settings) is not None


def test_desynced_overlay_resolves_via_projects_table_not_name_match(tmp_path, settings):
    """Regression (live-workspace crash): if the overlay's cached
    `canonical_project_id` is stale/missing (e.g. `role_os_workspace.db`
    and `role_os_projects.db` -- two independently-owned files -- drifted
    out of sync), resolution must check `projects.discovery_item_id`
    directly before falling back to a name match. Skipping that check let
    `find_unlinked_project_by_name` return a *different* same-named
    Project than the one already linked to this exact item_id, and
    linking it crashed the caller with an uncaught `IntegrityError`
    (`UNIQUE constraint failed: projects.discovery_item_id`)."""
    already_linked = projects_db.create_project(
        name="Duplicate Name", workspace="Products", settings=settings
    )
    projects_db.link_project_to_discovery_item(
        already_linked["id"], "some-item-id", settings=settings
    )
    other_unlinked = projects_db.create_project(
        name="Duplicate Name", workspace="Products", settings=settings
    )

    # No overlay row exists for "some-item-id" at all here -- simulating
    # the desync where the workspace db has no memory of the link that
    # the projects db already has.
    resolved_id = identity.get_or_create_canonical_project_id(
        "some-item-id", "/some/root/path", "Duplicate Name", settings=settings
    )

    assert resolved_id == already_linked["id"]
    assert resolved_id != other_unlinked["id"]
    resolved = projects_db.get_project(resolved_id, settings=settings)
    assert resolved["discovery_item_id"] == "some-item-id"
