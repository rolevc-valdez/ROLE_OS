"""Tests for the read-only asset discovery index (Sprint 4 §6).

Sprint C4 (Assets OS) replaced this module's classification/reusable
logic with `app.assets.classification`'s deterministic, richer rule set
(Title Case categories like "Logo"/"Photo"/"Illustration" instead of the
original lowercase "logo"/"image"; design files are no longer reusable by
default just for being a `.psd`/`.ai` -- only Logo/Brand/Character/
Template/Font/Icon are). The tests below were updated for the new,
intentionally different values; `index_assets_for_project` itself is
unchanged as a compatibility shim (see `app.workspace.assets_index`)."""

from __future__ import annotations

from pathlib import Path

from app.workspace.assets_index import find_duplicates, index_assets_for_project


def _write(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_indexes_all_supported_extensions(tmp_path: Path):
    _write(tmp_path / "a.png")
    _write(tmp_path / "b.jpg")
    _write(tmp_path / "c.jpeg")
    _write(tmp_path / "d.webp")
    _write(tmp_path / "e.svg")
    _write(tmp_path / "f.pdf")
    _write(tmp_path / "g.mp4")
    _write(tmp_path / "h.mov")
    _write(tmp_path / "i.psd")
    _write(tmp_path / "j.ai")
    _write(tmp_path / "k.ttf")
    _write(tmp_path / "not_an_asset.txt")

    records = index_assets_for_project(str(tmp_path), "myproj")
    names = {r.filename for r in records}
    assert names == {
        "a.png",
        "b.jpg",
        "c.jpeg",
        "d.webp",
        "e.svg",
        "f.pdf",
        "g.mp4",
        "h.mov",
        "i.psd",
        "j.ai",
        "k.ttf",
    }


def test_asset_record_fields(tmp_path: Path):
    _write(tmp_path / "photo.png", b"fake-png-content")
    records = index_assets_for_project(str(tmp_path), "myproj")
    r = records[0]
    assert r.filename == "photo.png"
    assert r.project == "myproj"
    assert r.path.endswith("photo.png")
    assert r.asset_type == "image"
    assert r.category == "Photo"  # Sprint C4: a generic .png with no other signal
    assert r.size_bytes == len(b"fake-png-content")
    assert r.modified_at
    assert r.duplicate_hash is not None


def test_logo_detected_as_category(tmp_path: Path):
    # Classification also matches against the folder path, not just the
    # filename (so a real "Client Logos/" folder tags its contents
    # appropriately) -- files are written under a neutral "files" subfolder
    # rather than directly in `tmp_path` so pytest's test-name-derived
    # tmp_path (which contains "test_logo_detected_as_category0") can't
    # accidentally match the "Logo" rule itself.
    root = tmp_path / "files"
    _write(root / "company-logo.png")
    _write(root / "favicon.ico".replace(".ico", ".png"))  # keep to supported ext
    _write(root / "photo.png")
    records = {r.filename: r for r in index_assets_for_project(str(root), "p")}
    assert records["company-logo.png"].category == "Logo"
    assert records["photo.png"].category == "Photo"


def test_reusable_flag_for_logo_font_design(tmp_path: Path):
    # Same neutral-subfolder reasoning as test_logo_detected_as_category
    # above: this test's own name contains "logo", which pytest folds
    # into `tmp_path`.
    root = tmp_path / "files"
    _write(root / "logo.png")
    _write(root / "brand.ttf")
    _write(root / "design.psd")
    _write(root / "screenshot.jpg")
    records = {r.filename: r for r in index_assets_for_project(str(root), "p")}
    assert records["logo.png"].reusable is True
    assert records["brand.ttf"].reusable is True
    # Sprint C4: a bare .psd is no longer reusable-by-default just for
    # being a design file -- only Logo/Brand/Character/Template/Font/Icon
    # default to reusable (see app.assets.classification.is_reusable).
    assert records["design.psd"].reusable is False
    assert records["screenshot.jpg"].reusable is False


def test_categories_document_video_font(tmp_path: Path):
    _write(tmp_path / "spec.pdf")
    _write(tmp_path / "clip.mp4")
    _write(tmp_path / "font.woff2")
    records = {r.filename: r for r in index_assets_for_project(str(tmp_path), "p")}
    assert records["spec.pdf"].asset_type == "document"
    assert records["clip.mp4"].asset_type == "video"
    assert records["font.woff2"].asset_type == "font"


def test_duplicate_hash_detects_identical_content(tmp_path: Path):
    _write(tmp_path / "a.png", b"same-bytes")
    _write(tmp_path / "b.png", b"same-bytes")
    _write(tmp_path / "c.png", b"different-bytes")
    records = index_assets_for_project(str(tmp_path), "p")
    duplicates = find_duplicates(records)
    assert len(duplicates) == 1
    group = next(iter(duplicates.values()))
    assert {r.filename for r in group} == {"a.png", "b.png"}


def test_ignores_technical_directories(tmp_path: Path):
    _write(tmp_path / "node_modules" / "pkg" / "logo.png")
    _write(tmp_path / ".git" / "objects" / "fake.png")
    _write(tmp_path / "real.png")
    records = index_assets_for_project(str(tmp_path), "p")
    assert {r.filename for r in records} == {"real.png"}


def test_never_copies_or_modifies_files(tmp_path: Path):
    import os

    _write(tmp_path / "photo.png", b"content")

    def snapshot():
        snap = set()
        for dirpath, _dirs, files in os.walk(tmp_path):
            for name in files:
                fp = Path(dirpath) / name
                st = fp.stat()
                snap.add((str(fp), st.st_mtime, st.st_size))
        return snap

    before = snapshot()
    index_assets_for_project(str(tmp_path), "p")
    after = snapshot()
    assert before == after


def test_nonexistent_root_returns_empty(tmp_path: Path):
    assert index_assets_for_project(str(tmp_path / "does-not-exist"), "p") == []


def test_real_path_with_spaces_and_parentheses(tmp_path: Path):
    root = tmp_path / "My Drive (test@example.com)" / "1 - IA PROJECTS" / "brand-assets"
    _write(root / "logo.png")
    records = index_assets_for_project(str(root), "brand-assets")
    assert len(records) == 1
    assert records[0].filename == "logo.png"
