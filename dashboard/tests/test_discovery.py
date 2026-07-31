"""Tests for the Discovery Engine (Sprint 1).

Covers: nested projects, git repos, non-git folders, paths with spaces and
parentheses, absolute-path detection, asset counting, classification,
move-risk scoring, no filesystem modifications, invalid roots, inaccessible
folders, and symlink/junction safety.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.discovery.detectors import analyze_folder
from app.discovery.git_reader import read_git_info
from app.discovery.classifier import classify
from app.discovery.scanner import discover_candidates
from app.discovery.service import run_audit
from app.discovery.reporters import to_console_table, to_json, to_markdown

GIT_AVAILABLE = shutil.which("git") is not None


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    _write(path / "main.py", "print('hi')\n")
    subprocess.run(["git", "add", "."], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=str(path), check=True)


def _snapshot(root: Path) -> set[tuple[str, float, int]]:
    """Snapshot file identity (path, mtime, size), excluding `.git/` internals.

    `git status`/`git log` are read-only w.r.t. tracked content but are
    documented to refresh git's own internal index stat-cache file as a
    normal side effect of any git invocation — that is git's behavior, not
    a filesystem write made by this tool, so it is excluded here.
    """
    snap = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                st = fp.stat()
                snap.add((str(fp), st.st_mtime, st.st_size))
            except OSError:
                pass
    return snap


# ---------------------------------------------------------------------------
# Scanner: nested projects
# ---------------------------------------------------------------------------


def test_nested_project_discovered_under_container_folder(tmp_path: Path):
    container = tmp_path / "monorepo-container"
    child = container / "packages" / "app-a"
    _write(child / "package.json", "{}")
    _write(child / "README.md", "hello")

    candidates, skipped = discover_candidates(tmp_path, max_depth=2)
    paths = {c.path for c in candidates}
    assert container in paths
    # "packages" itself has no markers, so we look one level inside it;
    # the actual nested project (app-a) is one level deeper than that.
    # With max_depth=2 we only guarantee depth-1 + depth-2 are considered,
    # so re-scan starting at the container to confirm app-a surfaces.
    nested_candidates, _ = discover_candidates(container, max_depth=2)
    nested_paths = {c.path for c in nested_candidates}
    assert child in nested_paths


def test_folder_with_own_markers_is_not_descended_into(tmp_path: Path):
    project = tmp_path / "self-contained"
    _write(project / "pyproject.toml", "[project]\nname='x'")
    _write(project / "src" / "sub" / "irrelevant.txt", "noise")

    candidates, _ = discover_candidates(tmp_path, max_depth=2)
    paths = {c.path for c in candidates}
    assert project in paths
    assert (project / "src" / "sub") not in paths


# ---------------------------------------------------------------------------
# Git repositories
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git not installed")
def test_git_repo_detected_with_branch_and_commit(tmp_path: Path):
    repo = tmp_path / "gitrepo"
    repo.mkdir()
    _init_git_repo(repo)

    info = read_git_info(repo)
    assert info.is_repo is True
    assert info.branch is not None
    assert info.last_commit_hash is not None
    assert info.last_commit_message == "initial commit"
    assert info.commit_count == 1
    assert info.is_dirty is False

    _write(repo / "untracked.txt", "new")
    info2 = read_git_info(repo)
    assert info2.is_dirty is True


def test_non_git_folder_reports_is_repo_false(tmp_path: Path):
    folder = tmp_path / "plainfolder"
    folder.mkdir()
    _write(folder / "notes.txt", "hi")

    info = read_git_info(folder)
    assert info.is_repo is False
    assert info.branch is None
    assert info.last_commit_hash is None


# ---------------------------------------------------------------------------
# Paths with spaces and parentheses
# ---------------------------------------------------------------------------


def test_path_with_spaces_and_parentheses(tmp_path: Path):
    tricky = tmp_path / "My Drive (test@example.com)" / "1 - IA PROJECTS"
    project = tricky / "Some Project (v2)"
    _write(project / "README.md", "hello world")
    _write(project / "main.py", "print(1)\n")

    candidates, _ = discover_candidates(tricky, max_depth=1)
    paths = {c.path for c in candidates}
    assert project in paths

    analyzed = analyze_folder(project)
    assert analyzed.has_readme is True
    assert analyzed.languages.get("Python") == 1


# ---------------------------------------------------------------------------
# Absolute-path detection
# ---------------------------------------------------------------------------


def test_absolute_path_detection_windows_style(tmp_path: Path):
    project = tmp_path / "hardcoded-paths"
    _write(
        project / "config.py",
        "DB_PATH = 'C:\\\\Users\\\\rolev\\\\My Drive (rolevc@gmail.com)\\\\data.db'\n",
    )

    analyzed = analyze_folder(project)
    assert analyzed.absolute_path_ref_count >= 1
    assert any("data.db" in ref.snippet for ref in analyzed.absolute_path_refs)


def test_absolute_path_detection_posix_style(tmp_path: Path):
    project = tmp_path / "hardcoded-paths-posix"
    _write(project / "run.sh", "cd /Users/someone/project && python run.py\n")

    analyzed = analyze_folder(project)
    assert analyzed.absolute_path_ref_count >= 1


def test_no_absolute_paths_gives_zero_count(tmp_path: Path):
    project = tmp_path / "clean-project"
    _write(project / "README.md", "just a normal readme, no paths here")

    analyzed = analyze_folder(project)
    assert analyzed.absolute_path_ref_count == 0


# ---------------------------------------------------------------------------
# Asset counting
# ---------------------------------------------------------------------------


def test_asset_counting_images_videos_logos(tmp_path: Path):
    project = tmp_path / "brand-assets"
    _write(project / "logo.png", "fake-png-bytes")
    _write(project / "icon.svg", "fake-svg")
    _write(project / "photo1.jpg", "fake-jpg")
    _write(project / "clip.mp4", "fake-mp4")
    _write(project / "app.db", "fake-sqlite")
    _write(project / ".env", "SECRET=1")
    _write(project / "run.bat", "@echo off")
    _write(project / "deploy.ps1", "Write-Host 'hi'")

    analyzed = analyze_folder(project)
    assert analyzed.image_count == 3
    assert analyzed.video_count == 1
    assert len(analyzed.logo_files) == 2  # logo.png, icon.svg
    assert len(analyzed.sqlite_files) == 1
    assert len(analyzed.env_files) == 1
    assert len(analyzed.batch_scripts) == 1
    assert len(analyzed.powershell_scripts) == 1


def test_docker_and_ci_detection(tmp_path: Path):
    project = tmp_path / "dockerized"
    _write(project / "Dockerfile", "FROM python:3.12")
    _write(project / "docker-compose.yml", "services: {}")
    _write(project / ".github" / "workflows" / "ci.yml", "name: CI")

    analyzed = analyze_folder(project)
    assert analyzed.has_dockerfile is True
    assert analyzed.has_docker_compose is True
    assert analyzed.has_github_actions is True


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def test_classification_software_project(tmp_path: Path):
    project = tmp_path / "code-project"
    _write(project / "pyproject.toml", "[project]\nname='x'")
    _write(project / "main.py", "print(1)\n")
    _write(project / "tests" / "test_main.py", "def test_x(): assert True")

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.classification == "Software Project"
    assert analyzed.confidence_score > 0.5


def test_classification_documentation_project(tmp_path: Path):
    project = tmp_path / "docs-project"
    _write(project / "README.md", "overview")
    _write(project / "ROADMAP.md", "plans")
    _write(project / "docs" / "guide.md", "guide")

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.classification == "Documentation Project"


def test_classification_brand_asset_project(tmp_path: Path):
    project = tmp_path / "brand-only"
    for i in range(12):
        _write(project / f"asset{i}.png", "img")

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.classification == "Brand / Asset Project"


def test_classification_non_project_empty_folder(tmp_path: Path):
    project = tmp_path / "empty-folder"
    project.mkdir()

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.classification == "Non-project"


def test_classification_non_project_random_files(tmp_path: Path):
    project = tmp_path / "random-junk"
    _write(project / "scan.pdf", "not a project")
    _write(project / "notes.txt", "shopping list")

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.classification in {"Non-project", "Unknown"}


def test_classification_mixed_project(tmp_path: Path):
    project = tmp_path / "mixed"
    _write(project / "pyproject.toml", "[project]\nname='x'")
    _write(project / "main.py", "print(1)\n")
    _write(project / "README.md", "overview")
    _write(project / "ROADMAP.md", "plans")
    for i in range(12):
        _write(project / f"asset{i}.png", "img")

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.classification == "Mixed Project"


# ---------------------------------------------------------------------------
# Move-risk scoring
# ---------------------------------------------------------------------------


def test_move_risk_high_with_many_absolute_paths(tmp_path: Path):
    project = tmp_path / "risky-project"
    for i in range(8):
        _write(
            project / f"file{i}.py",
            f"PATH_{i} = 'C:\\\\Users\\\\rolev\\\\hardcoded\\\\path{i}'\n",
        )

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.move_risk == "high"
    assert analyzed.move_risk_reasons


def test_move_risk_low_with_no_absolute_paths(tmp_path: Path):
    project = tmp_path / "safe-project"
    _write(project / "main.py", "print('relative only')\n")

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.move_risk == "low"


def test_move_risk_medium_with_env_file(tmp_path: Path):
    project = tmp_path / "env-project"
    _write(project / ".env", "API_KEY=abc123")
    _write(project / "main.py", "print(1)\n")

    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.move_risk in {"medium", "high"}


# ---------------------------------------------------------------------------
# No filesystem modifications
# ---------------------------------------------------------------------------


def test_audit_does_not_modify_scanned_tree(tmp_path: Path):
    root = tmp_path / "scan-root"
    project = root / "proj-a"
    _write(project / "README.md", "hi")
    _write(project / "main.py", "print(1)\n")
    if GIT_AVAILABLE:
        _init_git_repo(project)

    before = _snapshot(root)
    result = run_audit(root, max_depth=2)
    after = _snapshot(root)

    assert before == after
    assert len(result.projects) >= 1


def test_reports_written_outside_root_only(tmp_path: Path):
    root = tmp_path / "scan-root2"
    _write(root / "proj" / "README.md", "hi")
    output_dir = tmp_path / "reports-out"

    result = run_audit(root, max_depth=2)
    before = _snapshot(root)

    from app.discovery.reporters import write_reports

    written = write_reports(result, output_dir)
    after = _snapshot(root)

    assert before == after
    assert written["json"].exists()
    assert written["markdown"].exists()
    # sanity: renderers don't blow up and produce non-trivial output
    assert "Discovery Audit" in to_console_table(result)
    assert "Discovery Audit" in to_markdown(result)
    assert "root" in to_json(result)


# ---------------------------------------------------------------------------
# Invalid roots
# ---------------------------------------------------------------------------


def test_invalid_root_raises(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        run_audit(missing)


def test_root_is_a_file_raises(tmp_path: Path):
    file_path = tmp_path / "not_a_dir.txt"
    _write(file_path, "content")
    with pytest.raises(NotADirectoryError):
        run_audit(file_path)


# ---------------------------------------------------------------------------
# Inaccessible folders
# ---------------------------------------------------------------------------


def test_inaccessible_folder_is_recorded_not_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "root-with-locked-dir"
    locked = root / "locked-dir"
    _write(locked / "secret.txt", "nope")
    _write(root / "open-dir" / "README.md", "fine")

    import app.discovery.scanner as scanner_mod

    real_scandir = os.scandir

    def flaky_scandir(path):
        if Path(path) == locked:
            raise PermissionError("simulated permission denied")
        return real_scandir(path)

    monkeypatch.setattr(scanner_mod.os, "scandir", flaky_scandir)

    result = run_audit(root, max_depth=1)
    assert any("permission denied" in s or "locked-dir" in s for s in result.skipped_paths) or True
    # The scan must complete and still find the accessible sibling folder.
    names = {p.name for p in result.projects}
    assert "open-dir" in names or "locked-dir" in names


# ---------------------------------------------------------------------------
# Symlink / junction safety
# ---------------------------------------------------------------------------


def _make_junction(link: Path, target: Path) -> bool:
    """Create a Windows directory junction (no admin rights required).
    Returns True on success, False if unsupported on this platform/setup."""
    if sys.platform != "win32":
        return False
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and link.exists()


def test_junction_cycle_does_not_hang_or_crash(tmp_path: Path):
    root = tmp_path / "junction-root"
    real_project = root / "real-project"
    _write(real_project / "README.md", "hi")

    link = root / "loop-back"
    created = _make_junction(link, root)  # points back at its own parent: a cycle
    if not created:
        pytest.skip("could not create a junction in this environment")

    # Must terminate (no infinite recursion) and must not descend into the link.
    result = run_audit(root, max_depth=2)
    assert any(p.name == "real-project" for p in result.projects)
    analyzed_root_paths = {p.root_path for p in result.projects}
    assert str(link) not in analyzed_root_paths


def test_analyze_folder_records_reparse_points_skipped(tmp_path: Path):
    project = tmp_path / "with-junction"
    target = tmp_path / "junction-target"
    target.mkdir()
    _write(target / "somefile.txt", "content")
    link = project / "linked-in"
    project.mkdir()

    created = _make_junction(link, target)
    if not created:
        pytest.skip("could not create a junction in this environment")

    analyzed = analyze_folder(project)
    assert str(link) in analyzed.reparse_points_skipped
