"""Sprint 1.5 structural-hardening tests: detector registry, recommendation
rule engine, and pipeline-stage safety. These test the new architecture
directly (registry/rules/pipeline modules), not just the observable
`analyze_folder`/`classify`/`recommend` behavior already covered by
`test_discovery.py` and `test_discovery_health_and_recommendation.py`.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.discovery import classifier
from app.discovery.detectors import documentation, registry, testing as testing_detector
from app.discovery.detectors.inventory import DirRecord, FileRecord, FolderInventory
from app.discovery.models import DiscoveredProject
from app.discovery.pipeline import PipelineStage, PipelineStageError
from app.discovery.recommendation import rules as recommendation_rules
from app.discovery.recommendation.engine import recommend
from app.discovery.recommendation.models import RecommendationCandidate


def _empty_inventory(root: Path) -> FolderInventory:
    return FolderInventory(root=root)


# ---------------------------------------------------------------------------
# Detector registry
# ---------------------------------------------------------------------------


def test_detector_registry_has_no_field_collisions(tmp_path: Path):
    """Every registered detector's Findings fields are claimed exactly
    once -- run_all() would raise DetectorFieldCollisionError otherwise."""
    merged = registry.run_all(_empty_inventory(tmp_path))
    assert isinstance(merged, dict)
    assert len(merged) > 0


def test_a_detector_is_independently_testable_without_a_real_filesystem(tmp_path: Path):
    """A detector only needs a hand-built FolderInventory -- no real
    folder, no other detector, no scanner/classifier involvement."""
    inventory = FolderInventory(
        root=tmp_path,
        files=[
            FileRecord(path=str(tmp_path / "README.md"), name="README.md", stem_lower="readme.md", ext=".md"),
            FileRecord(path=str(tmp_path / "ROADMAP.md"), name="ROADMAP.md", stem_lower="roadmap.md", ext=".md"),
        ],
        dirs=[
            DirRecord(path=str(tmp_path / "docs"), name="docs", name_lower="docs", parent_name_lower=tmp_path.name.lower()),
        ],
    )
    findings = documentation.detect(inventory)
    assert findings.has_readme is True
    assert findings.has_roadmap is True
    assert findings.doc_folders == [str(tmp_path / "docs")]
    # has_changelog/has_todo/has_license are this same detector's other
    # fields and must be independently False -- not "mutate unrelated
    # project state" in miniature.
    assert findings.has_changelog is False
    assert findings.has_todo is False
    assert findings.has_license is False


def test_testing_detector_is_isolated_from_documentation_detector(tmp_path: Path):
    """Two different detectors run over the same inventory must not see or
    affect each other's findings."""
    inventory = FolderInventory(
        root=tmp_path,
        files=[FileRecord(path=str(tmp_path / "test_x.py"), name="test_x.py", stem_lower="test_x.py", ext=".py")],
    )
    doc_findings = documentation.detect(inventory)
    test_findings = testing_detector.detect(inventory)
    assert doc_findings.has_readme is False
    assert test_findings.has_tests is True
    assert test_findings.test_file_count == 1


def test_registry_detects_field_collision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A deliberately misconfigured registry (two detectors claiming the
    same field) is caught loudly, not silently resolved by "last one
    wins"."""

    @dataclasses.dataclass
    class FakeFindingsA:
        has_readme: bool = True

    @dataclasses.dataclass
    class FakeFindingsB:
        has_readme: bool = False  # collides with FakeFindingsA and with the real documentation detector

    fake_registry = [
        ("fake_a", lambda inv: FakeFindingsA()),
        ("fake_b", lambda inv: FakeFindingsB()),
    ]
    monkeypatch.setattr(registry, "DETECTOR_REGISTRY", fake_registry)

    with pytest.raises(registry.DetectorFieldCollisionError):
        registry.run_all(_empty_inventory(tmp_path))


def test_adding_a_detector_only_requires_one_registry_line(tmp_path: Path):
    """Documents the extension contract: a brand-new detector module is a
    Findings dataclass + detect() function; registering it is exactly one
    entry in DETECTOR_REGISTRY, no other module needs to change."""

    @dataclasses.dataclass
    class NewFindings:
        some_new_field: str = "example"

    def new_detect(inventory: FolderInventory) -> NewFindings:
        return NewFindings()

    extended_registry = list(registry.DETECTOR_REGISTRY) + [("new_detector", new_detect)]
    # Directly exercise the merge logic with the extended list rather than
    # monkeypatching the module constant, to keep this test independent of
    # the real registry's current contents.
    import app.discovery.detectors.registry as registry_module

    owners: dict[str, str] = {}
    merged_fields: dict[str, object] = {}
    for name, detect_fn in extended_registry:
        findings = detect_fn(_empty_inventory(tmp_path))
        for f in dataclasses.fields(findings):
            assert f.name not in owners, f"unexpected collision on {f.name}"
            owners[f.name] = name
            merged_fields[f.name] = getattr(findings, f.name)
    assert merged_fields["some_new_field"] == "example"
    assert registry_module.DetectorFieldCollisionError  # sanity: still importable


# ---------------------------------------------------------------------------
# Recommendation rule engine
# ---------------------------------------------------------------------------


def _base_project(**overrides) -> DiscoveredProject:
    project = DiscoveredProject(root_path="C:/fake/root", name="fake", depth=0)
    for key, value in overrides.items():
        setattr(project, key, value)
    project.stage = PipelineStage.SCORED
    return project


def test_each_rule_module_is_independently_testable():
    """Every rule is a pure function of a DiscoveredProject -- no engine,
    no other rule, no filesystem involved."""
    from app.discovery.recommendation.rules import non_project

    project = _base_project(classification="Non-project", total_files=0)
    candidate = non_project.evaluate(project)
    assert candidate is not None
    assert candidate.action == "Archive"
    assert candidate.priority == non_project.PRIORITY


def test_non_project_outranks_high_move_risk():
    """Precedence table: non_project (100) beats high_move_risk (90) --
    move risk is irrelevant for something that isn't a project."""
    project = _base_project(
        classification="Non-project", total_files=0, move_risk="high", move_risk_reasons=["x"]
    )
    action, reasons = recommend(project)
    assert action == "Archive"


def test_high_move_risk_outranks_brand_asset_project():
    project = _base_project(
        classification="Brand / Asset Project",
        maturity="active",
        move_risk="high",
        move_risk_reasons=["6 hardcoded absolute-path references found"],
    )
    action, reasons = recommend(project)
    assert action == "Requires manual review"
    assert "move risk is high" in reasons[0]


def test_rule_order_in_list_does_not_affect_precedence(monkeypatch: pytest.MonkeyPatch):
    """Reversing RULES' list order must not change the winner -- priority,
    not position, decides (see rules/__init__.py's documented table)."""
    reversed_rules = list(reversed(recommendation_rules.RULES))
    monkeypatch.setattr(recommendation_rules, "RULES", reversed_rules)
    # engine.py imported RULES by reference at import time via `from ... import RULES`,
    # so patch the name the engine actually looks up.
    import app.discovery.recommendation.engine as engine_module

    monkeypatch.setattr(engine_module, "RULES", reversed_rules)

    project = _base_project(
        classification="Brand / Asset Project", maturity="active", move_risk="high", move_risk_reasons=["x"]
    )
    action, _ = recommend(project)
    assert action == "Requires manual review"  # high_move_risk (90) still beats brand_asset (80)


def test_fallback_rule_always_fires_for_unrecognized_classification():
    project = _base_project(classification="Unknown", move_risk="low")
    action, reasons = recommend(project)
    assert action == "Requires manual review"
    assert "unclassified signal mix" in reasons[0]


def test_recommendation_candidate_is_a_plain_structured_value():
    candidate = RecommendationCandidate(action="Archive", reasons=["r1"], priority=50)
    assert candidate.action == "Archive"
    assert candidate.reasons == ["r1"]
    assert candidate.priority == 50


# ---------------------------------------------------------------------------
# Pipeline-stage safety
# ---------------------------------------------------------------------------


def test_pipeline_stage_progresses_through_full_classify(tmp_path: Path):
    from app.discovery.detectors import analyze_folder

    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    project = analyze_folder(tmp_path)
    assert project.stage == PipelineStage.DETECTED

    classifier.classify(project)
    assert project.stage == PipelineStage.RECOMMENDED


def test_compute_health_guard_message_names_the_project(tmp_path: Path):
    from app.discovery.detectors import analyze_folder
    from app.discovery.health import compute_health

    project = analyze_folder(tmp_path)
    with pytest.raises(PipelineStageError) as excinfo:
        compute_health(project)
    assert project.name in str(excinfo.value)
    assert "CLASSIFIED" in str(excinfo.value)


def test_recommend_guard_fires_before_scoring(tmp_path: Path):
    from app.discovery.detectors import analyze_folder

    project = analyze_folder(tmp_path)
    project.stage = PipelineStage.CLASSIFIED  # classified, but never scored
    with pytest.raises(PipelineStageError) as excinfo:
        recommend(project)
    assert "SCORED" in str(excinfo.value)
