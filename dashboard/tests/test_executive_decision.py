"""Sprint C10 (Executive Decision Engine) acceptance tests.

Real Discovery Engine runs / real PI projects throughout, nothing
mocked -- same convention as `test_project_ecosystem.py`/
`test_impact_analysis.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.executive_decision.models import make_executive_decision
from app.executive_decision.planner import (
    build_today_plan,
    dependencies_status,
    estimate_effort_and_duration,
)
from app.executive_decision.scoring import compute_decision_score
from app.executive_decision.service import get_executive_decision
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    monkeypatch.setenv("ROLE_OS_ECOSYSTEM_DB_PATH", str(tmp_path / "ecosystem.db"))
    return Settings()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_and_adopt(
    tmp_path: Path,
    suffix: str,
    name: str,
    *,
    business_value: str | None = None,
    status: str | None = None,
) -> dict:
    root = tmp_path / f"exec-scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    payload = {}
    if business_value:
        payload["business_value"] = business_value
    if status:
        payload["status"] = status
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json=payload)
    return adopted.json()


def _make_and_adopt_many(
    tmp_path: Path, suffix: str, specs: list[tuple[str, dict]]
) -> dict[str, dict]:
    """Writes every synthetic project folder under one shared root, then
    rescans exactly once, before adopting each -- the Discovery Engine's
    scan cache is a single global cache, so a second `/workspace/rescan`
    against a *different* root would silently replace the first scan's
    projects entirely (the same pitfall `test_project_ecosystem.py`'s own
    multi-project tests avoid the same way)."""
    root = tmp_path / f"exec-scan-root-{suffix}"
    for name, _payload in specs:
        _write(root / name / "README.md", "# A\n")
        _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    result = {}
    for name, payload in specs:
        item = next(i for i in items if i["name"] == name)
        adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json=payload)
        result[name] = adopted.json()
    return result


# ---------------------------------------------------------------------------
# Scoring: every contributor is explainable and additive
# ---------------------------------------------------------------------------


def test_score_with_no_evidence_is_zero_and_honest():
    score, confidence, evidence = compute_decision_score(
        top_recommendation=None,
        business_value=None,
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert score == 0.0
    assert evidence == []
    assert confidence == 0.5


def test_operational_intelligence_priority_scales_into_score():
    rec = {"priority": 70, "recommendation": "Continue this project", "confidence": 0.8}
    score, confidence, evidence = compute_decision_score(
        top_recommendation=rec,
        business_value=None,
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert score == pytest.approx(28.0)  # 70 * 0.4
    assert any("priority 70/100" in e for e in evidence)
    assert confidence == 0.85


def test_business_value_contributes_named_points():
    score, _, evidence = compute_decision_score(
        top_recommendation=None,
        business_value="high",
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert score == 20.0
    assert any("business_value = high" in e for e in evidence)


def test_launch_ready_recommendation_adds_bonus_on_top_of_priority():
    rec = {"priority": 50, "recommendation": "Consider shipping/launching", "confidence": 0.9}
    score, _, evidence = compute_decision_score(
        top_recommendation=rec,
        business_value=None,
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert score == pytest.approx(50 * 0.4 + 15)
    assert any("launch-ready" in e for e in evidence)


def test_unblocks_contribution_is_capped():
    score, _, evidence = compute_decision_score(
        top_recommendation=None,
        business_value=None,
        dependent_names=["A", "B", "C", "D", "E"],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert score == 15.0  # capped at 3 projects worth
    assert any("Unblocks 5 project(s)" in e for e in evidence)


def test_already_blocking_contribution():
    score, _, evidence = compute_decision_score(
        top_recommendation=None,
        business_value=None,
        dependent_names=[],
        blocked_names=["Downstream Project"],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert score == 10.0
    assert any("Already blocking 1 project(s)" in e for e in evidence)


def test_impact_risk_scales_by_level():
    for risk, expected_points in (
        ("none", 0),
        ("low", 2),
        ("medium", 5),
        ("high", 10),
        ("critical", 15),
    ):
        score, _, evidence = compute_decision_score(
            top_recommendation=None,
            business_value=None,
            dependent_names=[],
            blocked_names=[],
            overall_risk=risk,
            pending_work="",
            days_since_activity=None,
            health_score=None,
            status=None,
            is_data_stale=False,
        )
        assert score == expected_points, risk
        if expected_points:
            assert any(risk in e for e in evidence)


def test_pending_work_contributes_a_fixed_bonus():
    score, _, evidence = compute_decision_score(
        top_recommendation=None,
        business_value=None,
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="Wire up webhooks",
        days_since_activity=None,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert score == 5.0
    assert any("pending work" in e for e in evidence)


def test_recent_activity_bonus_and_stale_penalty():
    recent_score, _, recent_evidence = compute_decision_score(
        top_recommendation=None,
        business_value=None,
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=1.0,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert recent_score == 5.0
    assert any("Active in the last" in e for e in recent_evidence)

    # Combined with a positive baseline so the penalty's actual magnitude
    # is provable without hitting the score's 0-point floor.
    stale_score, _, stale_evidence = compute_decision_score(
        top_recommendation=None,
        business_value="high",
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=45.0,
        health_score=None,
        status=None,
        is_data_stale=False,
    )
    assert stale_score == 15.0  # 20 (business_value=high) - 5 (stale penalty)
    assert any("No activity in" in e for e in stale_evidence)


def test_health_score_contributes_scaled_points():
    score, _, evidence = compute_decision_score(
        top_recommendation=None,
        business_value=None,
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=90,
        status=None,
        is_data_stale=False,
    )
    assert score == 9.0
    assert any("health score 90/100" in e for e in evidence)


def test_paused_and_blocked_status_are_penalized():
    # Combined with a positive baseline so the penalty's actual magnitude
    # is provable without hitting the score's 0-point floor.
    paused_score, _, paused_evidence = compute_decision_score(
        top_recommendation=None,
        business_value="critical",
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status="paused",
        is_data_stale=False,
    )
    assert paused_score == 5.0  # 25 (business_value=critical) - 20 (paused)
    assert any("paused" in e for e in paused_evidence)

    blocked_score, _, _ = compute_decision_score(
        top_recommendation=None,
        business_value="critical",
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status="blocked",
        is_data_stale=False,
    )
    assert blocked_score == 10.0  # 25 (business_value=critical) - 15 (blocked)


def test_stale_data_discounts_confidence_not_score():
    score, confidence, evidence = compute_decision_score(
        top_recommendation=None,
        business_value="high",
        dependent_names=[],
        blocked_names=[],
        overall_risk="none",
        pending_work="",
        days_since_activity=None,
        health_score=None,
        status=None,
        is_data_stale=True,
    )
    assert score == 20.0  # unaffected
    assert confidence == pytest.approx(0.5 * 0.85)
    assert any("confidence discounted" in e for e in evidence)


# ---------------------------------------------------------------------------
# Today Plan / effort-duration lookup
# ---------------------------------------------------------------------------


def test_estimate_effort_and_duration_matches_keyword():
    effort, duration = estimate_effort_and_duration("Consider shipping/launching")
    assert effort == "High"
    assert duration == "2-4 hours"


def test_estimate_effort_and_duration_default_when_no_keyword_matches():
    effort, duration = estimate_effort_and_duration("Some brand new action text")
    assert effort == "Medium"
    assert duration == "1-2 hours"


def test_dependencies_status_satisfied_when_nothing_unsatisfied():
    assert dependencies_status([]) == "Satisfied"


def test_dependencies_status_names_the_blocker():
    assert dependencies_status(["ROLE OS"]) == "Blocked on: ROLE OS"


def test_build_today_plan_is_a_single_step():
    project = {"canonical_project_id": "p1", "display_name": "ROLE Commerce Factory"}
    plan = build_today_plan(
        project=project,
        action_title="Finish Shopify adapter",
        objective="Finish Shopify adapter",
        expected_duration="2 hours",
        expected_result="Ready for Release Candidate",
        dependency_status="Satisfied",
    )
    assert len(plan) == 1
    step = plan[0]
    assert step["start_time"] == "09:00"
    assert step["project"] == project
    assert step["next_checkpoint"] == "Create Snapshot"
    assert step["dependencies_status"] == "Satisfied"


def test_build_today_plan_empty_when_no_project():
    assert (
        build_today_plan(
            project=None,
            action_title="",
            objective="",
            expected_duration="",
            expected_result="",
            dependency_status="Satisfied",
        )
        == []
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_make_executive_decision_rejects_unsupported_risk_level():
    with pytest.raises(AssertionError):
        make_executive_decision(
            recommended_project=None,
            decision_score=0,
            confidence=0,
            reason="",
            expected_benefit="",
            estimated_effort="",
            estimated_duration="",
            blocking_projects=[],
            projects_unblocked=[],
            commercial_value="Unknown",
            technical_value="Unknown",
            risk="extreme",
            dependencies={},
            today_plan=[],
            expected_result="",
            evidence=[],
            limitations=[],
        )


# ---------------------------------------------------------------------------
# Service: ranking, conflict resolution, security boundary
# ---------------------------------------------------------------------------


def test_no_adopted_projects_returns_honest_empty_decision(settings):
    """Passes empty `all_contexts`/`enriched_items` directly (rather than
    relying on nothing being adopted anywhere) -- the Workspace/Discovery
    overlay is a single, session-wide store not isolated by the
    `settings` fixture (only `PROJECTS_DB_PATH`/`ECOSYSTEM_DB_PATH` are),
    so other test files running earlier in the same pytest session may
    have already adopted real projects there. This still exercises the
    exact "no candidates" branch under test, deterministically."""
    result = get_executive_decision(settings=settings, all_contexts=[], enriched_items=[])
    assert result["decision"]["recommended_project"] is None
    assert result["ranked_projects"] == []
    assert "adopt a project" in result["decision"]["reason"].lower()


def test_higher_business_value_project_wins(settings, tmp_path):
    _make_and_adopt_many(
        tmp_path,
        "biz-value",
        [
            ("Low Value Project", {"business_value": "low"}),
            ("High Value Project", {"business_value": "high"}),
        ],
    )

    result = get_executive_decision(settings=settings)
    assert result["decision"]["recommended_project"]["display_name"] == "High Value Project"
    assert result["ranked_projects"][0]["project"]["display_name"] == "High Value Project"
    assert result["ranked_projects"][-1]["project"]["display_name"] == "Low Value Project"


def test_paused_project_never_beats_an_active_one(tmp_path):
    """`ProjectContext.status` resolves from the auto-created PI project
    record (Sprint 5's "every adopted project becomes a first-class
    Project"), not the Workspace overlay's own `status` passed at adopt
    time -- so the PI project's own status must be updated directly for
    this to actually reach `ProjectContext`, the same as a real user
    marking a project paused via the Projects page. Deliberately uses the
    default (cached) settings throughout -- the same ones the `client`
    TestClient's own dependency injection resolves to -- rather than the
    `settings` fixture's separately-constructed `Settings()`, so the
    adopt-time write and the read-time query are guaranteed to hit the
    same database (a fresh `Settings()` reads env vars set after
    `get_settings()`'s process-wide `lru_cache` already populated from an
    earlier import, so mixing the two would read from a different,
    empty database)."""
    adopted = _make_and_adopt_many(
        tmp_path,
        "paused-vs-active",
        [
            ("Paused Project", {"business_value": "high"}),
            ("Active Project", {"business_value": "medium"}),
        ],
    )

    from app.projects import db as projects_db

    projects_db.update_project(
        adopted["Paused Project"]["canonical_project_id"], {"status": "paused"}
    )

    result = get_executive_decision()
    assert result["decision"]["recommended_project"]["display_name"] == "Active Project"


def test_ranked_projects_are_sorted_descending_by_score(settings, tmp_path):
    _make_and_adopt_many(
        tmp_path,
        "sorted",
        [
            ("Project A", {"business_value": "low"}),
            ("Project B", {"business_value": "high"}),
            ("Project C", {"business_value": "medium"}),
        ],
    )

    result = get_executive_decision(settings=settings)
    scores = [rp["decision_score"] for rp in result["ranked_projects"]]
    assert scores == sorted(scores, reverse=True)
    assert [rp["rank"] for rp in result["ranked_projects"]] == [1, 2, 3]


def test_conflict_resolution_never_outputs_a_tie(settings, tmp_path):
    """Two projects with completely identical evidence must still resolve
    to exactly one winner, deterministically (health score, then
    canonical id, as documented in `service._sort_key`)."""
    _make_and_adopt_many(
        tmp_path,
        "twins",
        [
            ("Twin Project One", {}),
            ("Twin Project Two", {}),
        ],
    )

    result = get_executive_decision(settings=settings)
    assert len(result["ranked_projects"]) == 2
    ranks = [rp["rank"] for rp in result["ranked_projects"]]
    assert ranks == [1, 2]
    # Re-running must produce the exact same winner -- proving the
    # tie-break is a stable function of the data, not incidental ordering.
    result_again = get_executive_decision(settings=settings)
    assert (
        result["decision"]["recommended_project"]["canonical_project_id"]
        == result_again["decision"]["recommended_project"]["canonical_project_id"]
    )


def test_unadopted_discovered_projects_never_compete(settings, tmp_path):
    """Security boundary: a merely-discovered (not adopted) folder must
    never be scored or recommended."""
    root = tmp_path / "exec-scan-root-unadopted"
    _write(root / "Adopted Project" / "README.md", "# A\n")
    _write(root / "Adopted Project" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "Unadopted Project" / "README.md", "# B\n")
    _write(root / "Unadopted Project" / "pyproject.toml", "[project]\nname='b'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    adopted_item = next(i for i in items if i["name"] == "Adopted Project")
    client.post(f"/workspace/discovered/{adopted_item['id']}/adopt", json={})

    result = get_executive_decision(settings=settings)
    names = [rp["project"]["display_name"] for rp in result["ranked_projects"]]
    assert "Unadopted Project" not in names


def test_recommended_project_carries_a_today_plan(settings, tmp_path):
    _make_and_adopt(tmp_path, "plan", "Planned Project", business_value="high")
    result = get_executive_decision(settings=settings)
    plan = result["decision"]["today_plan"]
    assert len(plan) == 1
    assert plan[0]["start_time"] == "09:00"
    assert plan[0]["next_checkpoint"] == "Create Snapshot"


def test_passthrough_all_contexts_reduces_whole_workspace_passes(settings, tmp_path, monkeypatch):
    """Performance: `get_executive_decision`'s own code must never call
    `all_project_contexts` itself when the caller already computed
    `all_contexts`/`enriched_items` -- it only ever does so via its own
    documented lazy-import guard (`if all_contexts is None`). Counts calls
    rather than forbidding them outright, since Project Ecosystem's own
    `detect_shared_assets` detector independently calls
    `all_project_contexts` inside `compute_relationships` regardless of
    what Executive Decision passes through -- a pre-existing, documented
    Sprint C8 behavior this sprint does not change."""
    _make_and_adopt(tmp_path, "perf", "Perf Project", business_value="medium")

    from app.project_context import builder as builder_module

    real_all_project_contexts = builder_module.all_project_contexts
    call_count = {"n": 0}

    def _counting_wrapper(*args, **kwargs):
        call_count["n"] += 1
        return real_all_project_contexts(*args, **kwargs)

    all_contexts, enriched_items = real_all_project_contexts(settings=settings)

    monkeypatch.setattr(builder_module, "all_project_contexts", _counting_wrapper)
    call_count["n"] = 0
    result_without_passthrough = get_executive_decision(settings=settings)
    calls_without_passthrough = call_count["n"]

    call_count["n"] = 0
    result_with_passthrough = get_executive_decision(
        settings=settings, all_contexts=all_contexts, enriched_items=enriched_items
    )
    calls_with_passthrough = call_count["n"]

    assert result_without_passthrough["decision"]["recommended_project"] is not None
    assert result_with_passthrough["decision"]["recommended_project"] is not None
    assert calls_with_passthrough < calls_without_passthrough


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_returns_decision_and_ranked_projects_shape(settings, tmp_path):
    _make_and_adopt(tmp_path, "api", "API Test Project", business_value="high")
    response = client.get("/executive-decision")
    assert response.status_code == 200
    payload = response.json()
    assert "decision" in payload
    assert "ranked_projects" in payload
    assert payload["decision"]["recommended_project"] is not None
    for field in (
        "generated_at",
        "recommended_project",
        "decision_score",
        "confidence",
        "reason",
        "expected_benefit",
        "estimated_effort",
        "estimated_duration",
        "blocking_projects",
        "projects_unblocked",
        "commercial_value",
        "technical_value",
        "risk",
        "dependencies",
        "today_plan",
        "expected_result",
        "evidence",
        "limitations",
    ):
        assert field in payload["decision"], field


# ---------------------------------------------------------------------------
# Mission Control integration
# ---------------------------------------------------------------------------


def test_mission_control_includes_executive_decision_and_ranked_projects(settings, tmp_path):
    _make_and_adopt(tmp_path, "mc", "Mission Control Test Project", business_value="high")

    from app.mission_control.service import build_mission_control

    result = build_mission_control(settings=settings)
    assert "executive_decision" in result
    assert "ranked_projects" in result
    assert result["executive_decision"]["recommended_project"] is not None


# ---------------------------------------------------------------------------
# Explorer integration
# ---------------------------------------------------------------------------


def test_explorer_search_today_returns_executive_decision_result(settings, tmp_path):
    _make_and_adopt(tmp_path, "explorer", "Explorer Test Project", business_value="high")

    from app.explorer.service import search

    result = search("today", settings=settings)
    assert result["counts"]["Executive Decision"] >= 1
    items = result["groups"]["Executive Decision"]
    assert any("Today's Decision" in item["title"] for item in items)


def test_explorer_search_empty_query_never_computes_executive_decision(
    settings, tmp_path, monkeypatch
):
    """An empty/browse query must not trigger the (relatively) expensive
    Executive Decision computation -- same gating `_search_ecosystem`/
    `_search_impact` already use."""
    _make_and_adopt(tmp_path, "explorer-empty", "Explorer Empty Query Project")

    import app.executive_decision as executive_decision_package
    from app.explorer.service import search

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("get_executive_decision was called for an empty query")

    monkeypatch.setattr(executive_decision_package, "get_executive_decision", _fail_if_called)
    search("", settings=settings)
