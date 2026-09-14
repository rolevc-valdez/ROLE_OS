"""Phase 2 Task 2.1 (Multi-Root Discovery): `app.discovery.roots.resolve_roots`
validates and de-duplicates a list of configured roots before any of them is
scanned. Read-only -- no filesystem writes, no Discovery Engine invocation.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.discovery.roots import resolve_roots


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_single_valid_root_passes_through(tmp_path):
    root = _mkdir(tmp_path / "root-a")
    resolution = resolve_roots([str(root)])
    assert resolution.valid == [str(root.resolve())]
    assert resolution.skipped == []


def test_two_independent_valid_roots_both_kept(tmp_path):
    root_a = _mkdir(tmp_path / "root-a")
    root_b = _mkdir(tmp_path / "root-b")
    resolution = resolve_roots([str(root_a), str(root_b)])
    assert set(resolution.valid) == {str(root_a.resolve()), str(root_b.resolve())}
    assert resolution.skipped == []


def test_nonexistent_root_is_skipped_not_fatal(tmp_path):
    root_a = _mkdir(tmp_path / "root-a")
    missing = tmp_path / "does-not-exist"
    resolution = resolve_roots([str(root_a), str(missing)])
    assert resolution.valid == [str(root_a.resolve())]
    assert len(resolution.skipped) == 1
    assert resolution.skipped[0].reason == "does not exist"


def test_file_instead_of_directory_is_skipped(tmp_path):
    root_a = _mkdir(tmp_path / "root-a")
    a_file = tmp_path / "a-file.txt"
    a_file.write_text("x", encoding="utf-8")
    resolution = resolve_roots([str(root_a), str(a_file)])
    assert resolution.valid == [str(root_a.resolve())]
    assert resolution.skipped[0].reason == "not a directory"


def test_exact_duplicate_root_configured_twice_is_deduplicated(tmp_path):
    root_a = _mkdir(tmp_path / "root-a")
    resolution = resolve_roots([str(root_a), str(root_a)])
    assert resolution.valid == [str(root_a.resolve())]
    assert len(resolution.skipped) == 1
    assert "duplicate" in resolution.skipped[0].reason


def test_duplicate_root_with_different_casing_is_deduplicated_on_windows(tmp_path):
    root_a = _mkdir(tmp_path / "root-a")
    resolution = resolve_roots([str(root_a), str(root_a).upper()])
    if os.name == "nt":
        # Windows paths are case-insensitive -- the uppercased variant
        # resolves to the same real directory and must be deduplicated.
        assert len(resolution.valid) == 1
        assert "duplicate" in resolution.skipped[0].reason
    else:
        # On a case-sensitive filesystem the uppercased path is simply a
        # different, nonexistent directory -- correctly skipped, not merged.
        assert len(resolution.valid) == 1
        assert resolution.skipped[0].reason == "does not exist"


def test_nested_root_is_dropped_in_favor_of_the_outer_root(tmp_path):
    outer = _mkdir(tmp_path / "outer")
    inner = _mkdir(outer / "inner")
    resolution = resolve_roots([str(outer), str(inner)])
    assert resolution.valid == [str(outer.resolve())]
    assert any("nested inside" in d.reason for d in resolution.skipped)


def test_nested_root_dropped_regardless_of_configured_order(tmp_path):
    outer = _mkdir(tmp_path / "outer")
    inner = _mkdir(outer / "inner")
    resolution = resolve_roots([str(inner), str(outer)])
    assert resolution.valid == [str(outer.resolve())]


def test_empty_and_whitespace_entries_are_ignored(tmp_path):
    root_a = _mkdir(tmp_path / "root-a")
    resolution = resolve_roots([str(root_a), "", "   "])
    assert resolution.valid == [str(root_a.resolve())]
    assert resolution.skipped == []


def test_no_roots_configured_returns_empty_resolution():
    resolution = resolve_roots([])
    assert resolution.valid == []
    assert resolution.skipped == []
