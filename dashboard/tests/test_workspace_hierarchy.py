"""Tests for Workspace Adoption's Sprint 3 hierarchy/override layer:
grouped views, filters, expansion of child items, user overrides, rescan
persistence (adoption/ignore/override survive a rescan), and renamed/
removed-folder behavior. Real (unmocked) Discovery Engine runs throughout.
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


def _make_factory_root(tmp_path: Path) -> Path:
    root = tmp_path / "scan-root"
    _write(root / "Commerce Factory" / "adapter-a" / "package.json", "{}")
    _write(root / "Commerce Factory" / "adapter-b" / "package.json", "{}")
    _write(root / "Docs Project" / "README.md", "overview")
    _write(root / "Docs Project" / "ROADMAP.md", "plans")
    for name in ["01_ONE", "02_TWO", "03_THREE"]:
        _write(root / "Docs Project" / name / "README.md", "x")
    return root


# ---------------------------------------------------------------------------
# Grouped view: top-level only by default, with rolled-up children/counts
# ---------------------------------------------------------------------------


def test_top_level_view_groups_children_and_counts(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))

    top = service.list_hierarchy(view="top_level", settings=settings)
    names = {t["name"] for t in top}
    assert names == {"Commerce Factory", "Docs Project"}

    factory = next(t for t in top if t["name"] == "Commerce Factory")
    assert factory["component_count"] == 2
    assert {c["name"] for c in factory["children"]} == {"adapter-a", "adapter-b"}

    docs = next(t for t in top if t["name"] == "Docs Project")
    assert docs["internal_folder_count"] == 3


def test_repositories_view_is_flat_with_parent_context(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))

    repos = service.list_hierarchy(view="repositories", settings=settings)
    names = {r["name"] for r in repos}
    assert names == {"adapter-a", "adapter-b"}
    for r in repos:
        assert r["parent_name"] == "Commerce Factory"


def test_excluded_view_and_default_exclusion_of_otros(settings, tmp_path):
    root = tmp_path / "scan-root"
    _write(root / "OTROS - no proyectos" / "junk.txt", "j")
    _write(root / "Real Project" / "README.md", "x")
    service.rescan(settings=settings, root=str(root))

    top = service.list_hierarchy(view="top_level", settings=settings)
    assert all(t["name"] != "OTROS - no proyectos" for t in top)

    excluded = service.list_hierarchy(view="excluded", settings=settings)
    assert any(e["name"] == "OTROS - no proyectos" for e in excluded)


def test_needs_review_view(settings, tmp_path):
    root = tmp_path / "scan-root"
    # A depth-1 folder with weak signal (some content, not enough for
    # promotion) should not appear top-level, and should surface here.
    _write(root / "ambiguous" / "some.md", "hmm")
    _write(root / "ambiguous" / "readme_but_not_matched.txt", "not a README file")
    service.rescan(settings=settings, root=str(root))

    review = service.list_hierarchy(view="needs_review", settings=settings)
    # Whatever ends up "unknown" in this scan must never also be top-level.
    top_names = {t["name"] for t in service.list_hierarchy(view="top_level", settings=settings)}
    for item in review:
        assert item["name"] not in top_names


def test_view_all_matches_flat_legacy_list(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))

    flat = service.list_workspace_items(settings=settings)
    via_view = service.list_hierarchy(view="all", settings=settings)
    assert {i["id"] for i in flat} == {i["id"] for i in via_view}


# ---------------------------------------------------------------------------
# User overrides (§8)
# ---------------------------------------------------------------------------


def test_override_top_level_promotes_nested_item(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    repos = service.list_hierarchy(view="repositories", settings=settings)
    adapter = next(r for r in repos if r["name"] == "adapter-a")

    updated = service.set_override(adapter["id"], "top_level", settings=settings)
    assert updated["effective_is_top_level_project"] is True
    assert updated["item_kind"] == "component"  # computed field untouched

    top = service.list_hierarchy(view="top_level", settings=settings)
    assert any(t["name"] == "adapter-a" for t in top)


def test_override_attach_to_parent(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    top = service.list_hierarchy(view="top_level", settings=settings)
    docs = next(t for t in top if t["name"] == "Docs Project")
    factory = next(t for t in top if t["name"] == "Commerce Factory")

    updated = service.set_override(
        docs["id"], "attach_to_parent", parent_id=factory["id"], settings=settings
    )
    assert updated["effective_is_top_level_project"] is False
    assert updated["effective_parent_item_id"] == factory["id"]

    top_after = service.list_hierarchy(view="top_level", settings=settings)
    assert all(t["name"] != "Docs Project" for t in top_after)
    factory_after = next(t for t in top_after if t["name"] == "Commerce Factory")
    assert any(c["name"] == "Docs Project" for c in factory_after["children"])


def test_clear_override_restores_computed_boundary(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    repos = service.list_hierarchy(view="repositories", settings=settings)
    adapter = next(r for r in repos if r["name"] == "adapter-a")

    service.set_override(adapter["id"], "top_level", settings=settings)
    cleared = service.clear_override(adapter["id"], settings=settings)
    assert cleared["override_action"] is None
    assert cleared["effective_is_top_level_project"] is False


def test_clear_override_unknown_id_returns_none(settings):
    assert service.clear_override("does-not-exist", settings=settings) is None


def test_dangling_override_parent_falls_back_to_top_level(settings, tmp_path):
    """§9: if a rescan removes the folder an override pointed at, the
    overridden item must not silently vanish -- it re-surfaces as its own
    top-level entry."""
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    top = service.list_hierarchy(view="top_level", settings=settings)
    docs = next(t for t in top if t["name"] == "Docs Project")
    factory = next(t for t in top if t["name"] == "Commerce Factory")
    service.set_override(docs["id"], "attach_to_parent", parent_id=factory["id"], settings=settings)

    # Now rescan a root where "Commerce Factory" no longer exists.
    root2 = tmp_path / "scan-root-2"
    _write(root2 / "Docs Project" / "README.md", "overview")
    _write(root2 / "Docs Project" / "ROADMAP.md", "plans")
    service.rescan(settings=settings, root=str(root2))

    top_after = service.list_hierarchy(view="top_level", settings=settings)
    assert any(t["name"] == "Docs Project" for t in top_after)


# ---------------------------------------------------------------------------
# Rescan persistence (§9): adoption/ignore/override survive a rescan
# ---------------------------------------------------------------------------


def test_adoption_and_ignore_survive_rescan(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    top = service.list_hierarchy(view="top_level", settings=settings)
    factory = next(t for t in top if t["name"] == "Commerce Factory")
    docs = next(t for t in top if t["name"] == "Docs Project")

    service.adopt_item(factory["id"], priority="high", settings=settings)
    service.ignore_item(docs["id"], settings=settings)

    service.rescan(settings=settings, root=str(root))

    top_after = service.list_hierarchy(view="top_level", settings=settings)
    factory_after = next(t for t in top_after if t["name"] == "Commerce Factory")
    assert factory_after["adopted"] is True
    assert factory_after["priority"] == "high"
    assert all(t["name"] != "Docs Project" for t in top_after)  # still ignored


def test_no_duplicates_created_across_repeated_rescans(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    service.rescan(settings=settings, root=str(root))
    service.rescan(settings=settings, root=str(root))

    items = service.list_workspace_items(settings=settings)
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids))


def test_deterministic_ids_stable_across_rescans(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    first = {i["name"]: i["id"] for i in service.list_workspace_items(settings=settings)}

    service.rescan(settings=settings, root=str(root))
    second = {i["name"]: i["id"] for i in service.list_workspace_items(settings=settings)}

    assert first == second


# ---------------------------------------------------------------------------
# Renamed / removed folder behavior (§9)
# ---------------------------------------------------------------------------


def test_removed_folder_disappears_and_does_not_inflate_counts(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    top = service.list_hierarchy(view="top_level", settings=settings)
    docs = next(t for t in top if t["name"] == "Docs Project")
    service.adopt_item(docs["id"], settings=settings)

    import shutil

    shutil.rmtree(root / "Docs Project")
    summary = service.rescan(settings=settings, root=str(root))

    # Commerce Factory + its two adapter components remain; Docs Project
    # and its three numbered subfolders are gone.
    assert summary["projects_found"] == 3
    # The removed project's adoption no longer counts toward the summary...
    assert summary["projects_adopted"] == 0
    # ...but the item itself simply disappears from the live list, rather
    # than crashing or duplicating -- its overlay row is harmlessly orphaned.
    names = {i["name"] for i in service.list_workspace_items(settings=settings)}
    assert "Docs Project" not in names


def test_renamed_folder_appears_as_new_item_old_overlay_orphaned(settings, tmp_path):
    """Renaming is, honestly, "remove + add" for a root_path-hash identity
    scheme -- documented explicitly rather than silently mis-tracked as
    "the same project"."""
    root = tmp_path / "scan-root"
    _write(root / "Old Name" / "README.md", "x")
    service.rescan(settings=settings, root=str(root))
    old_item = service.list_workspace_items(settings=settings)[0]
    service.adopt_item(old_item["id"], priority="high", settings=settings)

    (root / "Old Name").rename(root / "New Name")
    service.rescan(settings=settings, root=str(root))

    items = service.list_workspace_items(settings=settings)
    names = {i["name"] for i in items}
    assert "New Name" in names
    assert "Old Name" not in names
    new_item = next(i for i in items if i["name"] == "New Name")
    assert new_item["id"] != old_item["id"]
    assert new_item["adopted"] is False  # fresh identity, no carried-over state


# ---------------------------------------------------------------------------
# Expansion of child items (embedded, no extra request needed)
# ---------------------------------------------------------------------------


def test_children_embedded_inline_no_separate_request_needed(settings, tmp_path):
    root = _make_factory_root(tmp_path)
    service.rescan(settings=settings, root=str(root))
    top = service.list_hierarchy(view="top_level", settings=settings)
    factory = next(t for t in top if t["name"] == "Commerce Factory")

    assert isinstance(factory["children"], list)
    assert len(factory["children"]) == 2
    for child in factory["children"]:
        assert "discovery_detail" in child
