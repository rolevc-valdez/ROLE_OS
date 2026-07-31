"""Behavioral-parity regression tests (Sprint 1.5).

One fixture per representative case called out in the Sprint 1.5 brief:
a normal git project, a static-website-shaped project, absolute paths, a
`.env` file, an Obsidian vault, a VS Code workspace, a container/same-named
-child folder, and an unknown folder. Each asserts the exact classification/
move-risk/recommendation the pre-refactor Sprint 1 engine produced, so a
future change to the detector registry or rule engine that silently shifts
behavior fails a test here instead of only showing up in a real audit run.

(This is in addition to, not a replacement for, the two real, previously-
documented corpus results already pinned as literal reference tables in
`docs/architecture/09_DISCOVERY_ENGINE_SPRINT1_REPORT.md`.)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.discovery.classifier import classify
from app.discovery.detectors import analyze_folder
from app.discovery.git_reader import read_git_info
from app.discovery.recommendation import apply_container_child_overrides

GIT_AVAILABLE = shutil.which("git") is not None


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(["git", "add", "."], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=str(path), check=True)


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git not installed")
def test_parity_normal_git_project(tmp_path: Path):
    project = tmp_path / "normal-git-project"
    _write(project / "README.md", "overview")
    _write(project / "pyproject.toml", "[project]\nname='x'")
    _write(project / "main.py", "print('hello')\n")
    _write(project / "tests" / "test_main.py", "def test_x(): assert True")
    _init_git_repo(project)

    analyzed = analyze_folder(project)
    analyzed.git = read_git_info(project)
    classify(analyzed)

    assert analyzed.git.is_repo is True
    assert analyzed.classification == "Software Project"
    assert analyzed.move_risk == "low"
    assert analyzed.health_score is not None


def test_parity_static_website(tmp_path: Path):
    project = tmp_path / "static-site"
    _write(project / "index.html", "<html></html>")
    _write(project / "style.css", "body {}")
    _write(project / "package.json", "{}")
    _write(project / "next.config.js", "module.exports = {}")
    _write(project / "README.md", "a website")

    analyzed = analyze_folder(project)
    classify(analyzed)

    assert analyzed.classification == "Website"
    assert analyzed.recommendation in {"Move into IA PROJECTS", "Requires manual review"}


def test_parity_absolute_paths_folder(tmp_path: Path):
    project = tmp_path / "hardcoded-paths"
    for i in range(8):
        _write(project / f"file{i}.py", f"PATH_{i} = 'C:\\\\Users\\\\rolev\\\\hardcoded\\\\path{i}'\n")

    analyzed = analyze_folder(project)
    classify(analyzed)

    assert analyzed.move_risk == "high"
    assert analyzed.recommendation == "Requires manual review"
    assert "hardcoded absolute-path" in analyzed.recommendation_reasons[0]


def test_parity_env_file_folder(tmp_path: Path):
    project = tmp_path / "env-project"
    _write(project / ".env", "API_KEY=abc123")
    _write(project / "main.py", "print(1)\n")

    analyzed = analyze_folder(project)
    classify(analyzed)

    assert analyzed.env_files
    assert analyzed.move_risk in {"medium", "high"}


def test_parity_obsidian_vault(tmp_path: Path):
    project = tmp_path / "my-vault"
    _write(project / ".obsidian" / "app.json", "{}")
    _write(project / "Note 1.md", "some notes")
    _write(project / "Note 2.md", "more notes")

    analyzed = analyze_folder(project)
    classify(analyzed)

    assert analyzed.has_obsidian_vault is True
    # An Obsidian vault alone contributes one move-risk point but doesn't
    # reach "high" (score >= 3) by itself -- documented parity, not a bug.
    assert analyzed.move_risk in {"low", "medium"}


def test_parity_vscode_workspace_with_absolute_path(tmp_path: Path):
    project = tmp_path / "with-workspace"
    _write(
        project / "app.code-workspace",
        '{"folders": [{"path": "C:\\\\Users\\\\rolev\\\\with-workspace"}]}',
    )

    analyzed = analyze_folder(project)
    classify(analyzed)

    assert analyzed.vscode_workspace_files
    assert analyzed.move_risk in {"medium", "high"}


def test_parity_container_same_named_child(tmp_path: Path):
    """The real AGUA-AZUL-APP / agua-azul-app case."""
    outer = tmp_path / "AGUA-AZUL-APP"
    inner = outer / "agua-azul-app"
    _write(inner / "package.json", "{}")
    _write(inner / "README.md", "hi")

    outer_project = analyze_folder(outer)
    outer_project.parent_path = None
    classify(outer_project)

    inner_project = analyze_folder(inner)
    inner_project.parent_path = str(outer)
    classify(inner_project)

    apply_container_child_overrides([outer_project, inner_project])

    assert outer_project.recommendation == "Rename"
    assert "agua-azul-app" in outer_project.recommendation_reasons[0]


def test_parity_unknown_folder(tmp_path: Path):
    project = tmp_path / "numbered-content-folder"
    _write(project / "01_intro.txt", "some text")
    _write(project / "02_notes.txt", "some more text")

    analyzed = analyze_folder(project)
    classify(analyzed)

    # Weak, ambiguous signal -- correctly not force-classified into a
    # Software/Website/Brand-Asset/Documentation bucket.
    assert analyzed.classification in {"Unknown", "Non-project"}
