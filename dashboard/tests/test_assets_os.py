"""Sprint C4 (Assets OS) acceptance tests.

Real Discovery Engine runs against synthetic folder trees throughout --
nothing mocked, real PNG bytes written to disk for dimension/thumbnail
tests. Uses the shared `TestClient(app)` pattern (session-wide DBs, per
`dashboard/tests/conftest.py`) already established by prior sprint test
files, with unique per-test names/roots to avoid cross-test collisions.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest
from app.assets import classification
from app.assets.model import compute_asset_id
from app.assets.service import AssetPathError, resolve_safe_path
from app.config import Settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "proj" / "projects.db"))
    monkeypatch.setenv("ROLE_OS_DB_PATH", str(tmp_path / "knowledge" / "role_os.db"))
    monkeypatch.setenv("ROLE_OS_ASSETS_DB_PATH", str(tmp_path / "assets" / "assets.db"))
    monkeypatch.setenv("ROLE_OS_ASSET_THUMBNAIL_CACHE_DIR", str(tmp_path / "thumbs"))
    return Settings()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_png(width: int, height: int) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" + b"\x00\x00\x00" * width)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _adopt_with_assets(tmp_path: Path, suffix: str, name: str, files: dict[str, bytes]) -> dict:
    root = tmp_path / f"scan-root-{suffix}"
    _write(root / name / "README.md", "# x\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    for rel, content in files.items():
        p = root / name / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


# ---------------------------------------------------------------------------
# Canonical AssetRecord / image metadata / SVG / unsupported formats
# ---------------------------------------------------------------------------


def test_canonical_asset_record_has_full_field_set(tmp_path):
    item = _adopt_with_assets(tmp_path, "1", "Asset Model Proj", {"logo.png": _make_png(64, 64)})
    resp = client.get("/assets", params={"q": "Asset Model Proj"})
    assert resp.status_code == 200
    body = resp.json()
    asset = next(a for a in body["items"] if a["filename"] == "logo.png")
    for field in (
        "asset_id",
        "canonical_project_id",
        "discovery_item_id",
        "filename",
        "absolute_path",
        "relative_path",
        "extension",
        "asset_type",
        "category",
        "mime_type",
        "size_bytes",
        "width",
        "height",
        "duration_seconds",
        "modified_at",
        "reusable",
        "likely_logo",
        "duplicate_hash",
        "duplicate_group_id",
        "preview_available",
        "preview_url",
        "source",
        "favorite",
    ):
        assert field in asset, field
    assert asset["discovery_item_id"] == item["id"]
    assert asset["width"] == 64 and asset["height"] == 64
    assert asset["duration_seconds"] is None  # honestly unimplemented, never guessed


def test_image_dimensions_extracted_for_png(tmp_path):
    _adopt_with_assets(tmp_path, "2", "Dim Proj", {"banner.png": _make_png(300, 150)})
    resp = client.get("/assets", params={"q": "banner.png"})
    asset = resp.json()["items"][0]
    assert asset["width"] == 300
    assert asset["height"] == 150


def test_svg_dimensions_parsed_from_header(tmp_path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect/></svg>'
    _adopt_with_assets(tmp_path, "3", "Svg Proj", {"icon.svg": svg})
    resp = client.get("/assets", params={"q": "icon.svg"})
    asset = resp.json()["items"][0]
    assert asset["width"] == 120
    assert asset["height"] == 80
    assert asset["category"] == "Icon"


def test_svg_preview_served_as_image_svg_xml(tmp_path):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
    _adopt_with_assets(tmp_path, "4", "Svg Preview Proj", {"mark.svg": svg})
    asset = client.get("/assets", params={"q": "mark.svg"}).json()["items"][0]
    resp = client.get(f"/assets/{asset['asset_id']}/preview")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")


def test_unsupported_format_has_no_preview(tmp_path):
    _adopt_with_assets(
        tmp_path, "5", "Unsupported Proj", {"deck.pptx": b"not a real pptx but bytes"}
    )
    asset = client.get("/assets", params={"q": "deck.pptx"}).json()["items"][0]
    assert asset["preview_available"] is False
    assert asset["preview_url"] is None
    assert asset["category"] == "Document"


def test_oversized_image_preview_fails_honestly_not_with_a_500(tmp_path):
    """A declared-huge image (decompression-bomb-shaped) must be refused
    gracefully (never loaded fully into memory, never a raw 500) -- see
    `app.assets.preview`'s `Image.MAX_IMAGE_PIXELS` guard, found live
    against the real workspace (a genuine ~200-megapixel screenshot)."""
    _adopt_with_assets(tmp_path, "19", "Huge Image Proj", {"huge.png": _make_png(20000, 20000)})
    asset = client.get("/assets", params={"q": "huge.png"}).json()["items"][0]
    assert asset["preview_available"] is True  # still a supported extension
    resp = client.get(f"/assets/{asset['asset_id']}/preview")
    assert resp.status_code == 422
    assert "too large" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Reusable classification / category overrides / favorites
# ---------------------------------------------------------------------------


def test_logo_is_reusable_by_default(tmp_path):
    _adopt_with_assets(tmp_path, "6", "Logo Reusable Proj", {"company-logo.png": _make_png(64, 64)})
    asset = client.get("/assets", params={"q": "company-logo.png"}).json()["items"][0]
    assert asset["category"] == "Logo"
    assert asset["reusable"] is True
    assert asset["likely_logo"] is True


def test_screenshot_is_not_reusable_by_default(tmp_path):
    _adopt_with_assets(
        tmp_path, "7", "Screenshot Proj", {"app_screenshot.png": _make_png(1920, 1080)}
    )
    asset = client.get("/assets", params={"q": "app_screenshot.png"}).json()["items"][0]
    assert asset["category"] == "Screenshot"
    assert asset["reusable"] is False


def test_category_and_reusable_overrides_persist_without_touching_source(tmp_path):
    _adopt_with_assets(tmp_path, "8", "Override Proj", {"random_export.png": _make_png(500, 500)})
    root = tmp_path / "scan-root-8" / "Override Proj" / "random_export.png"
    before_mtime = root.stat().st_mtime
    before_bytes = root.read_bytes()

    asset = client.get("/assets", params={"q": "random_export.png"}).json()["items"][0]
    assert asset["reusable"] is False  # ordinary export, not reusable by default

    resp = client.patch(
        f"/assets/{asset['asset_id']}", json={"reusable": True, "category": "Template"}
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["reusable"] is True
    assert updated["category"] == "Template"

    # Source file untouched.
    assert root.stat().st_mtime == before_mtime
    assert root.read_bytes() == before_bytes

    # Override persists across a fresh index build.
    refetched = client.get("/assets", params={"q": "random_export.png"}).json()["items"][0]
    assert refetched["reusable"] is True
    assert refetched["category"] == "Template"


def test_favorite_override(tmp_path):
    _adopt_with_assets(tmp_path, "9", "Favorite Proj", {"pick.png": _make_png(64, 64)})
    asset = client.get("/assets", params={"q": "pick.png"}).json()["items"][0]
    assert asset["favorite"] is False
    client.patch(f"/assets/{asset['asset_id']}", json={"favorite": True})
    refetched = client.get("/assets", params={"q": "pick.png", "favorites_only": True}).json()
    assert any(a["filename"] == "pick.png" for a in refetched["items"])


# ---------------------------------------------------------------------------
# Duplicate grouping
# ---------------------------------------------------------------------------


def test_duplicate_group_detected_and_members_linked(tmp_path):
    same_bytes = _make_png(64, 64)
    _adopt_with_assets(
        tmp_path,
        "10",
        "Dup Proj",
        {"logo_v1.png": same_bytes, "logo_v2.png": same_bytes, "unique.png": _make_png(64, 65)},
    )
    items = client.get("/assets", params={"q": "Dup Proj"}).json()["items"]
    dup_items = [i for i in items if i["duplicate_group_id"]]
    assert len(dup_items) == 2
    assert {i["filename"] for i in dup_items} == {"logo_v1.png", "logo_v2.png"}

    unique_item = next(i for i in items if i["filename"] == "unique.png")
    assert unique_item["duplicate_group_id"] is None

    group_id = dup_items[0]["duplicate_group_id"]
    group_resp = client.get(f"/assets/duplicates/{group_id}")
    assert group_resp.status_code == 200
    group = group_resp.json()
    assert group["count"] == 2
    assert {m["filename"] for m in group["members"]} == {"logo_v1.png", "logo_v2.png"}

    detail = client.get(f"/assets/{dup_items[0]['asset_id']}").json()
    assert len(detail["duplicate_members"]) == 1


def test_index_project_assets_resolves_duplicate_group_id_directly(tmp_path, settings):
    """Found live (Sprint C4.1 audit): `index_project_assets` -- called
    *directly* by Dashboard/Home's recent assets, `ProjectContext.
    assets_count`'s recent-activity block, and Project Hub, not just
    through the `/assets` API's `list_all_assets` -- must resolve
    `duplicate_group_id` to `None` for a file that shares its hash with
    nothing else, the same way `/assets` does. Before this fix, every one
    of those direct callers saw the *raw*, unresolved value (`duplicate_
    group_id == duplicate_hash` for every hashable file, even a genuine
    singleton), while `/assets`/`GET /assets/duplicates/{id}` correctly
    treated it as not a duplicate -- a real cross-screen data mismatch,
    not just a missing test."""
    from app.assets.service import index_project_assets

    same_bytes = _make_png(64, 64)
    root = tmp_path / "dup-direct-proj"
    root.mkdir()
    (root / "a.png").write_bytes(same_bytes)
    (root / "b.png").write_bytes(same_bytes)
    (root / "solo.png").write_bytes(_make_png(10, 11))

    records = index_project_assets(str(root), "Dup Direct Proj", settings=settings)
    by_name = {r.filename: r for r in records}

    assert by_name["a.png"].duplicate_group_id is not None
    assert by_name["a.png"].duplicate_group_id == by_name["b.png"].duplicate_group_id
    assert by_name["solo.png"].duplicate_group_id is None


def test_list_all_assets_resolves_duplicate_group_id_across_projects(tmp_path):
    """Sprint C8 regression: `list_all_assets` combines every project's own
    `index_project_assets` records (each already passed through `group_
    duplicates` once, *within* that one project) and calls `group_
    duplicates` again on the combined list -- the old implementation only
    ever *cleared* `duplicate_group_id`, never (re)set it, so a file whose
    only duplicate lives in a *different* project (a group of exactly 1
    within its own project's pass, correctly cleared to `None` there) could
    never be resolved back to a shared group id by the outer call, even
    though two projects' assets did genuinely share a file. Found while
    building the Project Ecosystem Engine's `shares_assets` detector, which
    depends on this exact cross-project resolution."""
    # Both projects must be adopted from the *same* scan (the Discovery
    # scan cache is global -- a second `/workspace/rescan` against a
    # different root replaces the first scan's projects entirely, per
    # earlier sprints' own findings), so both live under one shared root.
    same_bytes = _make_png(64, 64)
    root = tmp_path / "scan-root-cross-dup"
    _write(root / "Cross Dup Proj A" / "README.md", "# x\n")
    _write(root / "Cross Dup Proj A" / "pyproject.toml", "[project]\nname='a'")
    (root / "Cross Dup Proj A" / "shared.png").write_bytes(same_bytes)
    _write(root / "Cross Dup Proj B" / "README.md", "# x\n")
    _write(root / "Cross Dup Proj B" / "pyproject.toml", "[project]\nname='a'")
    (root / "Cross Dup Proj B" / "shared.png").write_bytes(same_bytes)
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    for item in items:
        if item["name"] in ("Cross Dup Proj A", "Cross Dup Proj B"):
            client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    items_a = client.get("/assets", params={"q": "Cross Dup Proj A"}).json()["items"]
    items_b = client.get("/assets", params={"q": "Cross Dup Proj B"}).json()["items"]
    group_a = next(i for i in items_a if i["filename"] == "shared.png")["duplicate_group_id"]
    group_b = next(i for i in items_b if i["filename"] == "shared.png")["duplicate_group_id"]
    assert group_a is not None
    assert group_a == group_b


def test_duplicates_only_filter(tmp_path):
    same_bytes = _make_png(32, 32)
    _adopt_with_assets(
        tmp_path,
        "11",
        "DupFilter Proj",
        {"a.png": same_bytes, "b.png": same_bytes, "solo.png": _make_png(10, 10)},
    )
    resp = client.get("/assets", params={"q": "DupFilter Proj", "duplicates_only": True})
    items = resp.json()["items"]
    assert len(items) == 2
    assert all(i["duplicate_group_id"] for i in items)


# ---------------------------------------------------------------------------
# Project filtering / search / pagination
# ---------------------------------------------------------------------------


def test_filter_by_project(tmp_path):
    # Both projects must come from the same rescan -- Workspace's single
    # global scan cache is replaced wholesale on every /workspace/rescan
    # call (see test_explorer_v2.py's `_adopt_siblings` for the same
    # gotcha), so a second, separately-scanned project would otherwise
    # evict the first from the active top-level listing before we can
    # read its canonical_project_id.
    root = tmp_path / "scan-root-12"
    for name, files in (
        ("Filter Proj A", {"x.png": _make_png(10, 10)}),
        ("Filter Proj B", {"y.png": _make_png(10, 10)}),
    ):
        _write(root / name / "README.md", "# x\n")
        _write(root / name / "pyproject.toml", "[project]\nname='a'")
        for rel, content in files.items():
            (root / name / rel).write_bytes(content)
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item_a = next(i for i in items if i["name"] == "Filter Proj A")
    item_b = next(i for i in items if i["name"] == "Filter Proj B")
    client.post(f"/workspace/discovered/{item_a['id']}/adopt", json={})
    client.post(f"/workspace/discovered/{item_b['id']}/adopt", json={})
    project_a_id = client.get(f"/workspace/discovered/{item_a['id']}").json()[
        "canonical_project_id"
    ]

    resp = client.get("/assets", params={"project_id": project_a_id})
    items = resp.json()["items"]
    assert items
    assert all(i["canonical_project_id"] == project_a_id for i in items)
    assert any(i["filename"] == "x.png" for i in items)
    assert not any(i["filename"] == "y.png" for i in items)


def test_search_by_filename_category_extension_path(tmp_path):
    _adopt_with_assets(tmp_path, "13", "Search Proj", {"brand/company-logo.png": _make_png(64, 64)})
    assert client.get("/assets", params={"q": "company-logo"}).json()["total"] >= 1
    assert client.get("/assets", params={"q": "Logo", "category": "Logo"}).json()["total"] >= 1
    assert client.get("/assets", params={"extension": ".png"}).json()["total"] >= 1
    assert client.get("/assets", params={"q": "brand/company-logo"}).json()["total"] >= 1


def test_pagination(tmp_path):
    files = {f"img_{i}.png": _make_png(10, 10) for i in range(5)}
    _adopt_with_assets(tmp_path, "14", "Page Proj", files)
    page1 = client.get("/assets", params={"q": "Page Proj", "page": 1, "page_size": 2}).json()
    assert len(page1["items"]) == 2
    assert page1["total"] == 5
    assert page1["total_pages"] == 3
    page2 = client.get("/assets", params={"q": "Page Proj", "page": 2, "page_size": 2}).json()
    assert len(page2["items"]) == 2
    assert {i["asset_id"] for i in page1["items"]}.isdisjoint(
        {i["asset_id"] for i in page2["items"]}
    )


# ---------------------------------------------------------------------------
# Security: path traversal, outside adopted roots, missing files
# ---------------------------------------------------------------------------


def test_path_traversal_rejected(settings, tmp_path):
    """An `asset_id` is never treated as (or decoded back into) a path --
    it is only ever a lookup key into the live, already-scanned index.
    A traversal-shaped path that was never indexed simply has no
    corresponding asset_id, so it is rejected as "not found" -- the
    strongest possible rejection (the server never even attempts to
    resolve or open it)."""
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    fake_id = compute_asset_id(str((tmp_path / "adopted-root" / "../../outside.txt").resolve()))
    with pytest.raises(AssetPathError, match="no asset found"):
        resolve_safe_path(fake_id, settings=settings)


def test_asset_id_for_file_outside_any_adopted_root_is_rejected(settings, tmp_path):
    outside_dir = tmp_path / "not-adopted"
    outside_dir.mkdir()
    outside_file = outside_dir / "sneaky.png"
    outside_file.write_bytes(_make_png(4, 4))
    fake_id = compute_asset_id(str(outside_file.resolve()))
    with pytest.raises(AssetPathError, match="no asset found"):
        resolve_safe_path(fake_id, settings=settings)


def test_resolved_path_outside_adopted_roots_is_rejected(settings, tmp_path, monkeypatch):
    """Defense in depth: even if a (hypothetically corrupted) index record
    pointed at a real file that is no longer inside any adopted root, the
    containment check still catches it -- the "asset exists in the index"
    check and the "is it actually inside an adopted root right now" check
    are two independent guards, not one."""
    import app.assets.service as assets_service_module

    outside_file = tmp_path / "escaped.png"
    outside_file.write_bytes(_make_png(4, 4))

    class _FakeRecord:
        absolute_path = str(outside_file)

    monkeypatch.setattr(
        assets_service_module, "get_asset", lambda asset_id, settings=None: _FakeRecord()
    )
    with pytest.raises(AssetPathError, match="outside every adopted"):
        resolve_safe_path("whatever-id", settings=settings)


def test_unknown_asset_id_rejected_everywhere(tmp_path):
    assert client.get("/assets/does-not-exist-at-all").status_code == 404
    assert client.get("/assets/does-not-exist-at-all/preview").status_code == 404
    assert client.get("/assets/does-not-exist-at-all/file").status_code == 404
    assert client.patch("/assets/does-not-exist-at-all", json={"favorite": True}).status_code == 404


def test_missing_file_after_deletion_is_handled_honestly(tmp_path):
    _adopt_with_assets(tmp_path, "15", "Delete Proj", {"gone.png": _make_png(20, 20)})
    asset = client.get("/assets", params={"q": "gone.png"}).json()["items"][0]
    Path(asset["absolute_path"]).unlink()
    resp = client.get(f"/assets/{asset['asset_id']}/preview")
    assert resp.status_code == 404


def test_malicious_filename_does_not_escape_json_or_crash(tmp_path):
    # `< > : " / \ | ? *` are illegal in a Windows filename -- the
    # filesystem itself already rejects the classic "<script>" shape, so
    # the adversarial case worth testing on this platform is a name with
    # every character Windows *does* allow that could still misbehave in
    # HTML/JS if ever concatenated unescaped: quotes, ampersands, percent-
    # encoding lookalikes, unicode.
    tricky_name = "..%2f'weird & tricky; #(name) — ünïcödé.png"
    _adopt_with_assets(tmp_path, "16", "Malicious Name Proj", {tricky_name: _make_png(4, 4)})
    resp = client.get("/assets", params={"q": "Malicious Name Proj"})
    assert resp.status_code == 200
    assert any(a["filename"] == tricky_name for a in resp.json()["items"])


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------


def test_cache_invalidated_when_file_changes(tmp_path):
    from app.assets.service import index_project_assets

    root = tmp_path / "scan-root-cache"
    proj_dir = root / "Cache Proj"
    proj_dir.mkdir(parents=True)
    (proj_dir / "README.md").write_text("# x")
    (proj_dir / "pyproject.toml").write_text("[project]\nname='a'")
    img_path = proj_dir / "resizable.png"
    img_path.write_bytes(_make_png(50, 50))

    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "Cache Proj")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    first = index_project_assets(str(proj_dir), "Cache Proj")
    record = next(r for r in first if r.filename == "resizable.png")
    assert record.width == 50

    import os

    img_path.write_bytes(_make_png(99, 99))
    new_mtime = img_path.stat().st_mtime + 2
    os.utime(img_path, (new_mtime, new_mtime))

    second = index_project_assets(str(proj_dir), "Cache Proj")
    updated = next(r for r in second if r.filename == "resizable.png")
    assert updated.width == 99  # recomputed, not served stale from cache


# ---------------------------------------------------------------------------
# ProjectContext asset-count parity (must never disagree, per C1B/C4 §9)
# ---------------------------------------------------------------------------


def test_project_context_assets_count_matches_canonical_index(tmp_path):
    item = _adopt_with_assets(
        tmp_path,
        "17",
        "Parity Proj",
        {"one.png": _make_png(10, 10), "two.png": _make_png(20, 20)},
    )
    ctx = client.get(f"/project-context/{item['id']}").json()
    canonical = client.get("/assets", params={"q": "Parity Proj", "page_size": 200}).json()
    assert ctx["assets_count"] == canonical["total"]


# ---------------------------------------------------------------------------
# Explorer integration
# ---------------------------------------------------------------------------


def test_explorer_asset_result_opens_canonical_asset_detail(tmp_path):
    _adopt_with_assets(
        tmp_path, "18", "Explorer Asset Proj", {"explorer_logo.png": _make_png(40, 40)}
    )
    result = client.get("/explorer/search", params={"q": "explorer_logo.png"}).json()
    asset_results = result["groups"]["Asset"]
    assert asset_results
    r = asset_results[0]
    open_asset_action = next(a for a in r["actions"] if a["label"] == "Open Asset")
    assert open_asset_action["nav"] == "asset"
    detail = client.get(f"/assets/{open_asset_action['param']}")
    assert detail.status_code == 200
    assert detail.json()["filename"] == "explorer_logo.png"


# ---------------------------------------------------------------------------
# Manual vs discovered projects
# ---------------------------------------------------------------------------


def test_manual_project_has_no_assets_but_does_not_error():
    client.post("/pi/projects", json={"name": "Manual No Assets Proj", "workspace": "Products"})
    resp = client.get("/assets", params={"q": "Manual No Assets Proj"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Paths with spaces and parentheses (the real workspace's actual path shape)
# ---------------------------------------------------------------------------


def test_real_world_path_with_spaces_and_parentheses(tmp_path):
    root = tmp_path / "1 - IA PROJECTS (test)"
    proj = root / "My Project (v2)"
    proj.mkdir(parents=True)
    (proj / "README.md").write_text("# x")
    (proj / "pyproject.toml").write_text("[project]\nname='a'")
    (proj / "brand assets").mkdir()
    (proj / "brand assets" / "logo (final).png").write_bytes(_make_png(64, 64))

    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "My Project (v2)")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    resp = client.get("/assets", params={"q": "logo (final)"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    asset = resp.json()["items"][0]
    assert "brand assets" in asset["relative_path"]

    preview = client.get(f"/assets/{asset['asset_id']}/preview")
    assert preview.status_code == 200


# ---------------------------------------------------------------------------
# Excluded folders never leak into Assets
# ---------------------------------------------------------------------------


def test_excluded_dirs_never_appear_in_assets(tmp_path):
    root = tmp_path / "scan-root-excl"
    proj = root / "Excl Proj"
    (proj / "node_modules").mkdir(parents=True)
    (proj / "README.md").write_text("# x")
    (proj / "pyproject.toml").write_text("[project]\nname='a'")
    (proj / "node_modules" / "leaked.png").write_bytes(_make_png(10, 10))
    (proj / "real.png").write_bytes(_make_png(10, 10))

    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "Excl Proj")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    resp = client.get("/assets", params={"q": "Excl Proj", "page_size": 200})
    filenames = {a["filename"] for a in resp.json()["items"]}
    assert "real.png" in filenames
    assert "leaked.png" not in filenames


def test_role_os_own_runtime_var_directory_never_leaks_into_assets(settings, tmp_path):
    """Found live: if a scanned project root happens to *contain* ROLE
    OS's own runtime data directory (as "ROLE_OS" itself does, being this
    checkout), the generated thumbnail cache under it would otherwise be
    walked back in as "discovered assets" and re-thumbnailed every scan.

    `asset_thumbnail_cache_dir` (like every other `var/`-relative default
    in `config.py`) is a *relative* path resolved against the process's
    cwd at `Settings()` construction time -- not against `repo_root` --
    so live runs saw it land under `dashboard/var/...` instead of the
    repo-root `var/...` an earlier version of this exclusion assumed.
    `index_project_assets` must exclude the real, resolved
    `Settings.asset_thumbnail_cache_dir`'s parent unconditionally, the
    same way `.git`/`node_modules` are excluded, regardless of where that
    happens to physically resolve."""
    from app.assets.service import index_project_assets

    fake_repo_root = tmp_path / "fake-repo"
    var_dir = fake_repo_root / "var" / "role_os_dashboard" / "asset_thumbnails"
    var_dir.mkdir(parents=True)
    (var_dir / "cached-thumb.png").write_bytes(_make_png(10, 10))
    (fake_repo_root / "real-project-file.png").write_bytes(_make_png(10, 10))

    settings.repo_root = fake_repo_root
    settings.asset_thumbnail_cache_dir = var_dir
    records = index_project_assets(str(fake_repo_root), "Fake Repo", settings=settings)
    filenames = {r.filename for r in records}
    assert "real-project-file.png" in filenames
    assert "cached-thumb.png" not in filenames


def test_a_second_runtime_dir_from_a_different_process_cwd_also_excluded(settings, tmp_path):
    """Found live: a *second* process (a pytest run launched from the repo
    root while a dev server was already running from `dashboard/`) resolved
    the same relative `var/role_os_dashboard/...` default to a different
    physical directory than the one `settings.asset_thumbnail_cache_dir`
    (this process's own, already-resolved value) points at. A single
    resolved-path exclusion can only ever know about its own process's
    runtime dir, not one an unrelated process independently created
    elsewhere under the same scanned root -- excluding by the literal,
    never-varying `role_os_dashboard` directory *name* (the one path
    segment every `var/`-relative default in `config.py` shares
    regardless of which `var/` parent it resolves under) catches every
    physical copy structurally, the same way `.git`/`node_modules` are
    excluded by name rather than by one specific resolved location."""
    from app.assets.service import index_project_assets

    fake_repo_root = tmp_path / "fake-repo"
    this_process_var_dir = fake_repo_root / "var" / "role_os_dashboard" / "asset_thumbnails"
    this_process_var_dir.mkdir(parents=True)

    other_process_var_dir = (
        fake_repo_root / "dashboard" / "var" / "role_os_dashboard" / "asset_thumbnails"
    )
    other_process_var_dir.mkdir(parents=True)
    (other_process_var_dir / "leaked-from-elsewhere.png").write_bytes(_make_png(10, 10))

    (fake_repo_root / "real-project-file.png").write_bytes(_make_png(10, 10))

    settings.repo_root = fake_repo_root
    settings.asset_thumbnail_cache_dir = this_process_var_dir
    records = index_project_assets(str(fake_repo_root), "Fake Repo", settings=settings)
    filenames = {r.filename for r in records}
    assert "real-project-file.png" in filenames
    assert "leaked-from-elsewhere.png" not in filenames


# ---------------------------------------------------------------------------
# Classification module unit tests (pure functions, no I/O)
# ---------------------------------------------------------------------------


def test_classify_category_icon_by_dimensions():
    assert (
        classification.classify_category(
            filename="x.png", folder_path="/proj", extension=".png", width=32, height=32
        )
        == "Icon"
    )


def test_classify_category_screenshot_by_common_resolution():
    assert (
        classification.classify_category(
            filename="Screen Shot 2026-01-01.png",
            folder_path="/proj",
            extension=".png",
            width=1920,
            height=1080,
        )
        == "Screenshot"
    )


def test_classify_category_font_by_extension():
    assert (
        classification.classify_category(
            filename="Inter-Bold.ttf", folder_path="/proj/fonts", extension=".ttf"
        )
        == "Font"
    )


def test_is_reusable_font_true_screenshot_false():
    assert classification.is_reusable(category="Font", filename="Inter-Bold.ttf") is True
    assert classification.is_reusable(category="Screenshot", filename="shot.png") is False
