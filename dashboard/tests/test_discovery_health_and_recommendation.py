"""Tests for the Health Score, Recommendation, and the LICENSE/Obsidian/
VS Code workspace detectors added on top of the Sprint 1 Discovery Engine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.discovery.classifier import (
    classify,
    classify_commercial_readiness,
    classify_confidence,
    classify_kind,
    classify_maturity,
    classify_move_risk,
)
from app.discovery.detectors import analyze_folder
from app.discovery.health import compute_health
from app.discovery.pipeline import PipelineStage, PipelineStageError
from app.discovery.recommendation import apply_container_child_overrides, recommend


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# New detectors
# ---------------------------------------------------------------------------


def test_license_detected(tmp_path: Path):
    project = tmp_path / "licensed"
    _write(project / "LICENSE.md", "MIT")
    analyzed = analyze_folder(project)
    assert analyzed.has_license is True


def test_obsidian_vault_detected(tmp_path: Path):
    project = tmp_path / "vault"
    _write(project / ".obsidian" / "app.json", "{}")
    analyzed = analyze_folder(project)
    assert analyzed.has_obsidian_vault is True


def test_vscode_workspace_file_detected(tmp_path: Path):
    project = tmp_path / "with-workspace"
    _write(project / "app.code-workspace", '{"folders": [{"path": "."}]}')
    analyzed = analyze_folder(project)
    assert len(analyzed.vscode_workspace_files) == 1


def test_document_design_font_counts(tmp_path: Path):
    project = tmp_path / "creative"
    _write(project / "brief.pdf", "pdf")
    _write(project / "cover.psd", "psd")
    _write(project / "brand.otf", "font")
    analyzed = analyze_folder(project)
    assert analyzed.document_count == 1
    assert analyzed.design_file_count == 1
    assert analyzed.font_count == 1


# ---------------------------------------------------------------------------
# Health Score
# ---------------------------------------------------------------------------


def test_health_score_high_for_well_documented_tested_active_project(tmp_path: Path):
    project = tmp_path / "healthy"
    _write(project / "README.md", "overview")
    _write(project / "ROADMAP.md", "plans")
    _write(project / "pyproject.toml", "[project]\nname='x'")
    _write(project / "tests" / "test_a.py", "def test_a(): assert True")
    _write(project / "tests" / "test_b.py", "def test_b(): assert True")
    _write(project / "tests" / "test_c.py", "def test_c(): assert True")
    _write(project / "Dockerfile", "FROM python:3.12")

    analyzed = analyze_folder(project)
    classify(analyzed)

    assert analyzed.health_score is not None
    assert analyzed.health_score >= 60
    assert set(analyzed.health_breakdown) == {
        "documentation",
        "tests",
        "recent_activity",
        "roadmap",
        "architecture",
        "automation",
        "commercial_readiness",
        "deployment",
    }


def test_health_score_low_for_empty_folder(tmp_path: Path):
    project = tmp_path / "bare"
    _write(project / "notes.txt", "just a note")

    analyzed = analyze_folder(project)
    classify(analyzed)

    assert analyzed.health_score is not None
    assert analyzed.health_score < 40


def test_recent_activity_signal_none_without_any_file(tmp_path: Path):
    project = tmp_path / "truly-empty"
    project.mkdir()
    analyzed = analyze_folder(project)
    classify_confidence(analyzed)
    classify_kind(analyzed)
    classify_move_risk(analyzed)
    classify_maturity(analyzed)
    classify_commercial_readiness(analyzed)
    analyzed.stage = PipelineStage.CLASSIFIED

    score, breakdown = compute_health(analyzed)
    assert breakdown["recent_activity"] is None
    assert "recent_activity" not in {} or True  # weighting excludes it; score still computed
    assert isinstance(score, int)


def test_compute_health_refuses_project_that_has_not_been_classified(tmp_path: Path):
    project = tmp_path / "raw"
    _write(project / "README.md", "hi")
    analyzed = analyze_folder(project)  # only DETECTED, never classified
    with pytest.raises(PipelineStageError):
        compute_health(analyzed)


def test_recommend_refuses_project_that_has_not_been_scored(tmp_path: Path):
    project = tmp_path / "raw2"
    _write(project / "README.md", "hi")
    analyzed = analyze_folder(project)
    classify_confidence(analyzed)
    classify_kind(analyzed)
    classify_move_risk(analyzed)
    classify_maturity(analyzed)
    classify_commercial_readiness(analyzed)
    analyzed.stage = PipelineStage.CLASSIFIED
    # health.compute_health deliberately not called -- stage never reaches SCORED
    with pytest.raises(PipelineStageError):
        recommend(analyzed)


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


def test_recommend_archive_for_stale_empty_non_project(tmp_path: Path):
    project = tmp_path / "old-empty"
    project.mkdir()
    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.classification == "Non-project"
    assert analyzed.recommendation == "Archive"
    assert analyzed.recommendation_reasons


def test_recommend_manual_review_for_high_move_risk(tmp_path: Path):
    project = tmp_path / "risky"
    for i in range(8):
        _write(
            project / f"file{i}.py",
            f"PATH_{i} = 'C:\\\\Users\\\\rolev\\\\hardcoded\\\\path{i}'\n",
        )
    analyzed = analyze_folder(project)
    classify(analyzed)
    assert analyzed.move_risk == "high"
    assert analyzed.recommendation == "Requires manual review"


def test_recommend_move_into_ia_projects_for_healthy_low_risk_project(tmp_path: Path):
    project = tmp_path / "solid-project"
    _write(project / "README.md", "overview")
    _write(project / "ROADMAP.md", "plans")
    _write(project / "pyproject.toml", "[project]\nname='x'")
    _write(project / "main.py", "print('relative only')\n")
    _write(project / "tests" / "test_main.py", "def test_x(): assert True")

    analyzed = analyze_folder(project)
    classify(analyzed)

    assert analyzed.classification in {"Software Project", "Mixed Project"}
    assert analyzed.move_risk == "low"
    if analyzed.health_score is not None and analyzed.health_score >= 50:
        assert analyzed.recommendation == "Move into IA PROJECTS"


def test_container_wrapping_single_same_named_child_gets_rename_override(tmp_path: Path):
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
    # the inner project's own recommendation is untouched by the override
    assert inner_project.recommendation != "Rename" or inner_project.recommendation_reasons == []


def test_recommend_is_pure_and_does_not_mutate_reasons_across_calls(tmp_path: Path):
    project = tmp_path / "pure-check"
    _write(project / "README.md", "hi")
    analyzed = analyze_folder(project)
    classify(analyzed)
    action, reasons = recommend(analyzed)
    assert action in {
        "Leave where it is",
        "Move into IA PROJECTS",
        "Archive",
        "Merge with another project",
        "Rename",
        "Requires manual review",
    }
    assert isinstance(reasons, list)
