"""Tests for app.workspace.service: real Discovery Engine runs (no mocks),
cached against a temporary root, merged with the overlay database.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.workspace import service


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    return Settings()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_root(tmp_path: Path) -> Path:
    root = tmp_path / "scan-root"
    _write(root / "code-project" / "pyproject.toml", "[project]\nname='x'")
    _write(root / "code-project" / "main.py", "print(1)\n")
    _write(root / "docs-project" / "README.md", "hello")
    _write(root / "docs-project" / "ROADMAP.md", "plans")
    return root


def test_rescan_runs_real_discovery_engine_and_caches(settings, tmp_path):
    root = _make_root(tmp_path)
    summary = service.rescan(settings=settings, root=str(root))

    assert summary["projects_found"] == 2
    assert summary["projects_adopted"] == 0
    assert summary["projects_ignored"] == 0
    assert summary["last_scan"] is not None
    assert summary["root"] == str(root)


def test_rescan_without_root_or_configured_default_raises(settings):
    settings.discovery_root = ""
    with pytest.raises(ValueError):
        service.rescan(settings=settings, root=None)


def test_list_workspace_items_default_overlay(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))

    items = service.list_workspace_items(settings=settings)
    assert len(items) == 2
    names = {i["name"] for i in items}
    assert names == {"code-project", "docs-project"}
    for item in items:
        assert item["adopted"] is False
        assert item["ignored"] is False
        assert item["priority"] == "medium"
        assert "discovery_detail" in item
        assert item["classification"] in {"Software Project", "Documentation Project"}


def test_adopt_item_persists_overlay_and_survives_rescan(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_workspace_items(settings=settings)
    code_item = next(i for i in items if i["name"] == "code-project")

    adopted = service.adopt_item(
        code_item["id"], priority="critical", business_value="high", settings=settings
    )
    assert adopted["adopted"] is True
    assert adopted["priority"] == "critical"

    # Re-scanning must not clobber the overlay -- the filesystem metadata
    # refreshes, the user's own priority/business value do not.
    service.rescan(settings=settings, root=str(root))
    items_after = service.list_workspace_items(settings=settings)
    code_after = next(i for i in items_after if i["name"] == "code-project")
    assert code_after["adopted"] is True
    assert code_after["priority"] == "critical"


def test_adopt_unknown_id_returns_none(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    assert service.adopt_item("not-a-real-id", settings=settings) is None


def test_ignore_hides_from_default_listing(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_workspace_items(settings=settings)
    target = items[0]

    service.ignore_item(target["id"], settings=settings)

    visible = service.list_workspace_items(settings=settings)
    assert target["id"] not in {i["id"] for i in visible}

    visible_with_ignored = service.list_workspace_items(include_ignored=True, settings=settings)
    assert target["id"] in {i["id"] for i in visible_with_ignored}


def test_unignore_restores_visibility(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_workspace_items(settings=settings)
    target = items[0]

    service.ignore_item(target["id"], settings=settings)
    service.unignore_item(target["id"], settings=settings)

    visible = service.list_workspace_items(settings=settings)
    assert target["id"] in {i["id"] for i in visible}


def test_get_item_review_detail_has_full_discovery_signals(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_workspace_items(settings=settings)
    code_item = next(i for i in items if i["name"] == "code-project")

    detail = service.get_item(code_item["id"], settings=settings)
    assert detail is not None
    full = detail["discovery_detail"]
    assert full["root_path"] == code_item["root_path"]
    assert "languages" in full
    assert "confidence_reasons" in full


def test_add_note(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_workspace_items(settings=settings)
    target = items[0]

    service.adopt_item(target["id"], settings=settings)
    updated = service.add_note(target["id"], "remember to check this", settings=settings)
    assert updated["notes"][0]["text"] == "remember to check this"


def test_update_item_patches_status(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_workspace_items(settings=settings)
    target = items[0]

    service.adopt_item(target["id"], settings=settings)
    updated = service.update_item(target["id"], {"status": "paused"}, settings=settings)
    assert updated["status"] == "paused"


def test_summary_counts_adopted_and_ignored(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_workspace_items(settings=settings)

    service.adopt_item(items[0]["id"], settings=settings)
    service.ignore_item(items[1]["id"], settings=settings)

    summary = service.get_summary(settings=settings)
    assert summary["projects_found"] == 2
    assert summary["projects_adopted"] == 1
    assert summary["projects_ignored"] == 1


def test_list_adopted_as_projects_shape(settings, tmp_path):
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_workspace_items(settings=settings)
    service.adopt_item(items[0]["id"], priority="high", business_value="high", settings=settings)

    projects = service.list_adopted_as_projects(settings=settings)
    assert len(projects) == 1
    p = projects[0]
    assert p["workspace"] == "Discovered"
    assert p["is_discovered"] is True
    assert p["priority"] == "high"
    assert "health_score" in p
    assert "root_path" in p


def test_get_enriched_item_computes_ai_session_summary_exactly_once(
    settings, tmp_path, monkeypatch
):
    """Regression (Sprint C1: Consolidation): `get_enriched_item` used to
    call `get_ai_session_summary` twice for the same item -- once inside
    `enrich_project_item`, and again directly afterward to set the
    `ai_sessions` key. `enrich_project_item` now accepts a precomputed
    `ai_summary` and attaches it itself, so `get_enriched_item` must only
    trigger one real `list_ai_sessions` lookup per call."""
    from app.projects import db as projects_db

    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_hierarchy(view="top_level", settings=settings)
    item = next(i for i in items if i["name"] == "code-project")
    service.adopt_item(item["id"], settings=settings)

    call_count = 0
    real_list_ai_sessions = projects_db.list_ai_sessions

    def counting_list_ai_sessions(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return real_list_ai_sessions(*args, **kwargs)

    monkeypatch.setattr(projects_db, "list_ai_sessions", counting_list_ai_sessions)

    result = service.get_enriched_item(item["id"], settings=settings)
    assert result is not None
    assert call_count == 1, f"expected exactly one list_ai_sessions call, got {call_count}"


def test_enrich_project_item_attaches_ai_sessions_for_home_portfolio(settings, tmp_path):
    """Regression: `enrich_project_item`'s output must carry an
    `ai_sessions` key (previously absent), since `get_home_portfolio`
    reads `item.get("ai_sessions")` to find the most-recently-used
    session across all adopted projects -- without this key present, that
    lookup silently always returned `None`."""
    root = _make_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    items = service.list_hierarchy(view="top_level", settings=settings)
    item = next(i for i in items if i["name"] == "code-project")
    service.adopt_item(item["id"], settings=settings)

    enriched = service.enrich_project_item(item, settings=settings)
    assert "ai_sessions" in enriched
    assert enriched["ai_sessions"] == {
        "sessions": [],
        "latest_session": None,
        "latest_snapshot": None,
    }


def test_discovery_id_stable_across_calls():
    assert service.discovery_id("C:\\some\\path") == service.discovery_id("C:\\some\\path")
    assert service.discovery_id("C:\\a") != service.discovery_id("C:\\b")


def _make_second_root(tmp_path: Path) -> Path:
    root = tmp_path / "scan-root-2"
    _write(root / "second-project" / "pyproject.toml", "[project]\nname='y'")
    _write(root / "second-project" / "main.py", "print(2)\n")
    return root


def test_rescan_with_no_explicit_root_and_single_configured_root_is_unchanged(
    settings, tmp_path, monkeypatch
):
    """Phase 2 Task 2.1 backward-compat guarantee: with no
    ROLE_OS_DISCOVERY_ROOTS set, `rescan(root=None)` must behave exactly
    as the pre-multi-root single-root path always did."""
    monkeypatch.delenv("ROLE_OS_DISCOVERY_ROOTS", raising=False)
    root = _make_root(tmp_path)
    settings.discovery_root = str(root)

    summary = service.rescan(settings=settings, root=None)
    assert summary["projects_found"] == 2
    assert summary["root"] == str(root)


def test_rescan_multi_root_merges_projects_from_both_roots(settings, tmp_path, monkeypatch):
    root_a = _make_root(tmp_path)
    root_b = _make_second_root(tmp_path)
    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOTS", f"{root_a},{root_b}")

    summary = service.rescan(settings=settings, root=None)
    assert summary["projects_found"] == 3

    items = service.list_workspace_items(settings=settings)
    names = {i["name"] for i in items}
    assert names == {"code-project", "docs-project", "second-project"}


def test_rescan_multi_root_reports_both_roots(settings, tmp_path, monkeypatch):
    root_a = _make_root(tmp_path)
    root_b = _make_second_root(tmp_path)
    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOTS", f"{root_a},{root_b}")

    summary = service.rescan(settings=settings, root=None)
    assert str(Path(root_a).resolve()) in summary["root"]
    assert str(Path(root_b).resolve()) in summary["root"]


def test_rescan_multi_root_with_duplicate_configured_root_does_not_duplicate_projects(
    settings, tmp_path, monkeypatch
):
    root_a = _make_root(tmp_path)
    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOTS", f"{root_a},{root_a}")

    summary = service.rescan(settings=settings, root=None)
    assert summary["projects_found"] == 2  # not 4


def test_rescan_multi_root_with_nested_configured_roots_does_not_duplicate_projects(
    settings, tmp_path, monkeypatch
):
    outer = tmp_path / "outer"
    _write(outer / "code-project" / "pyproject.toml", "[project]\nname='x'")
    inner = outer / "code-project"
    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOTS", f"{outer},{inner}")

    summary = service.rescan(settings=settings, root=None)
    # Only the outer root is scanned; the nested root is dropped, so
    # "code-project" is found exactly once, not once per configured root.
    assert summary["projects_found"] == 1


def test_rescan_multi_root_skips_a_nonexistent_configured_root_without_failing(
    settings, tmp_path, monkeypatch
):
    root_a = _make_root(tmp_path)
    missing = tmp_path / "does-not-exist-at-all"
    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOTS", f"{root_a},{missing}")

    summary = service.rescan(settings=settings, root=None)
    assert summary["projects_found"] == 2


def test_rescan_multi_root_project_ids_stable_and_match_single_root_scan(
    settings, tmp_path, monkeypatch
):
    """The same real folder must resolve to the same Workspace item id
    whether it's found via a single-root scan or a multi-root scan --
    identity is derived from `root_path` alone (`app.discovery.identity`),
    never from which configured root found it."""
    root_a = _make_root(tmp_path)
    root_b = _make_second_root(tmp_path)

    service.rescan(settings=settings, root=str(root_a))
    single_root_id = next(
        i["id"] for i in service.list_workspace_items(settings=settings) if i["name"] == "code-project"
    )

    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOTS", f"{root_a},{root_b}")
    service.rescan(settings=settings, root=None)
    multi_root_id = next(
        i["id"] for i in service.list_workspace_items(settings=settings) if i["name"] == "code-project"
    )

    assert single_root_id == multi_root_id


def test_rescan_multi_root_never_auto_adopts_discovered_projects(settings, tmp_path, monkeypatch):
    root_a = _make_root(tmp_path)
    root_b = _make_second_root(tmp_path)
    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOTS", f"{root_a},{root_b}")

    summary = service.rescan(settings=settings, root=None)
    assert summary["projects_adopted"] == 0
    for item in service.list_workspace_items(settings=settings):
        assert item["adopted"] is False


def test_no_filesystem_modification_during_rescan(settings, tmp_path):
    import os

    root = _make_root(tmp_path)

    def snapshot():
        snap = set()
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                fp = Path(dirpath) / name
                st = fp.stat()
                snap.add((str(fp), st.st_mtime, st.st_size))
        return snap

    before = snapshot()
    service.rescan(settings=settings, root=str(root))
    after = snapshot()
    assert before == after
