"""Persistence tests for app.workspace.db.

Each test gets its own isolated SQLite file via a temporary
ROLE_OS_WORKSPACE_DB_PATH, mirroring test_advisor_db.py.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.workspace import db


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "workspace.db"))
    return Settings()


def test_scan_cache_round_trip(settings):
    assert db.load_scan_cache(settings) is None

    db.save_scan_cache(
        root="C:\\fake\\root",
        scanned_at="2026-08-01T00:00:00+00:00",
        duration_seconds=1.23,
        projects=[{"root_path": "C:\\fake\\root\\a", "name": "a"}],
        settings=settings,
    )
    cache = db.load_scan_cache(settings)
    assert cache["root"] == "C:\\fake\\root"
    assert cache["project_count"] == 1
    assert cache["projects"][0]["name"] == "a"


def test_scan_cache_overwrite_replaces_previous(settings):
    db.save_scan_cache(
        root="root1", scanned_at="t1", duration_seconds=1.0, projects=[{"name": "a"}], settings=settings
    )
    db.save_scan_cache(
        root="root2", scanned_at="t2", duration_seconds=2.0, projects=[{"name": "b"}], settings=settings
    )
    cache = db.load_scan_cache(settings)
    assert cache["root"] == "root2"
    assert cache["project_count"] == 1
    assert cache["projects"][0]["name"] == "b"


def test_adopt_creates_overlay_row_with_defaults(settings):
    overlay = db.adopt(
        "item-1", "C:\\proj\\a", priority="high", business_value="high", status="active", settings=settings
    )
    assert overlay["adopted"] is True
    assert overlay["ignored"] is False
    assert overlay["priority"] == "high"
    assert overlay["business_value"] == "high"
    assert overlay["adopted_at"] is not None
    assert overlay["tags"] == []
    assert overlay["notes"] == []


def test_ignore_creates_row_and_hides(settings):
    overlay = db.ignore("item-2", "C:\\proj\\b", settings=settings)
    assert overlay["ignored"] is True
    assert overlay["adopted"] is False


def test_unignore_missing_row_returns_none(settings):
    assert db.unignore("does-not-exist", settings=settings) is None


def test_unignore_clears_flag(settings):
    db.ignore("item-3", "C:\\proj\\c", settings=settings)
    overlay = db.unignore("item-3", settings=settings)
    assert overlay["ignored"] is False


def test_adopt_then_ignore_then_adopt_again(settings):
    db.adopt("item-4", "C:\\proj\\d", settings=settings)
    db.ignore("item-4", "C:\\proj\\d", settings=settings)
    overlay = db.get_overlay("item-4", settings)
    assert overlay["adopted"] is True
    assert overlay["ignored"] is True

    # Re-adopting explicitly un-hides it (you can't adopt something you're
    # hiding from yourself).
    overlay = db.adopt("item-4", "C:\\proj\\d", settings=settings)
    assert overlay["ignored"] is False


def test_update_overlay_partial_patch_does_not_clobber_other_fields(settings):
    db.adopt("item-5", "C:\\proj\\e", priority="low", business_value="low", settings=settings)
    db.update_overlay("item-5", "C:\\proj\\e", {"priority": "critical"}, settings=settings)
    overlay = db.get_overlay("item-5", settings)
    assert overlay["priority"] == "critical"
    assert overlay["business_value"] == "low"  # untouched


def test_update_overlay_tags(settings):
    db.adopt("item-6", "C:\\proj\\f", settings=settings)
    db.update_overlay("item-6", "C:\\proj\\f", {"tags": ["alpha", "beta"]}, settings=settings)
    overlay = db.get_overlay("item-6", settings)
    assert overlay["tags"] == ["alpha", "beta"]


def test_add_note_appends(settings):
    db.adopt("item-7", "C:\\proj\\g", settings=settings)
    db.add_note("item-7", "C:\\proj\\g", "first note", settings=settings)
    db.add_note("item-7", "C:\\proj\\g", "second note", settings=settings)
    overlay = db.get_overlay("item-7", settings)
    assert [n["text"] for n in overlay["notes"]] == ["first note", "second note"]
    assert all("id" in n and "created_at" in n for n in overlay["notes"])


def test_list_overlays_keyed_by_id(settings):
    db.adopt("item-8", "C:\\proj\\h", settings=settings)
    db.ignore("item-9", "C:\\proj\\i", settings=settings)
    overlays = db.list_overlays(settings)
    assert set(overlays.keys()) == {"item-8", "item-9"}
    assert overlays["item-8"]["adopted"] is True
    assert overlays["item-9"]["ignored"] is True


def test_get_overlay_missing_returns_none(settings):
    assert db.get_overlay("nope", settings) is None
