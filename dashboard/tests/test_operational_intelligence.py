"""Sprint C6 (Operational Intelligence Engine) acceptance tests.

Real Discovery Engine runs against synthetic folder trees, real PI
projects/dependencies, nothing mocked -- same convention as
`test_dashboard_v2.py`/`test_mission_control_api.py`.
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from app.operational_intelligence import get_operational_intelligence
from fastapi.testclient import TestClient

client = TestClient(app)

REQUIRED_FIELDS = {
    "recommendation",
    "priority",
    "confidence",
    "evidence",
    "project",
    "expected_benefit",
    "suggested_action",
}


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_and_adopt(tmp_path: Path, suffix: str, name: str = "app-a") -> dict:
    root = tmp_path / f"oi-scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


def _assert_canonical_shape(rec: dict) -> None:
    assert REQUIRED_FIELDS <= rec.keys()
    assert isinstance(rec["priority"], int) and 0 <= rec["priority"] <= 100
    assert isinstance(rec["confidence"], float) and 0.0 <= rec["confidence"] <= 1.0
    assert isinstance(rec["evidence"], list)
    assert rec["recommendation"]
    assert rec["expected_benefit"]
    assert rec["suggested_action"] is not None
    if rec["project"] is not None:
        assert "item_id" in rec["project"] and "canonical_project_id" in rec["project"]
        assert rec["project"].get("display_name")


def test_empty_workspace_yields_only_honest_workspace_wide_recommendations(tmp_path, monkeypatch):
    """The PI projects DB and Workspace scan cache are shared across this
    whole pytest run (see conftest.py's per-run temp DB setup), so other
    test modules may already have created real PI projects/workspace items
    by the time this test runs -- a genuine "nothing exists yet" workspace
    can only be proven against freshly isolated DBs, constructed here
    rather than assumed (same fix as Sprint C5's since-last-time fallback
    test)."""
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "empty_projects.db"))
    monkeypatch.setenv("ROLE_OS_ADVISOR_DB_PATH", str(tmp_path / "empty_advisor.db"))
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "empty_workspace.db"))
    from app.config import Settings

    recs = get_operational_intelligence(settings=Settings())
    for rec in recs:
        _assert_canonical_shape(rec)
    # Nothing here should ever be attributed to a specific project when
    # none exist.
    assert all(rec["project"] is None for rec in recs)


def test_every_recommendation_has_the_seven_mandated_fields(tmp_path):
    _make_and_adopt(tmp_path, "1", name="shape-app")
    recs = get_operational_intelligence()
    assert recs
    for rec in recs:
        _assert_canonical_shape(rec)


def test_recommendations_sorted_by_priority_then_confidence(tmp_path):
    _make_and_adopt(tmp_path, "2", name="sort-app")
    recs = get_operational_intelligence()
    keys = [(r["priority"], r["confidence"]) for r in recs]
    assert keys == sorted(keys, reverse=True)


def test_discovery_pack_evidence_surfaces_for_a_dirty_adopted_project(tmp_path):
    import subprocess

    root = tmp_path / "oi-scan-root-dirty"
    repo = root / "dirty-oi-app"
    _write(repo / "README.md", "# x\n")
    _write(repo / "pyproject.toml", "[project]\nname='a'")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
    )
    _write(repo / "untracked.txt", "dirty")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "dirty-oi-app")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    recs = get_operational_intelligence()
    dirty_recs = [
        r
        for r in recs
        if r["source"] == "discovery"
        and r["project"]
        and r["project"]["item_id"] == item["id"]
        and any("dirty" in e.lower() for e in r["evidence"])
    ]
    assert dirty_recs
    assert dirty_recs[0]["expected_benefit"]


def test_pi_pack_reuses_advisor_engine_for_dependencies():
    """Sprint C6: dependency evidence comes from the *existing* PI Advisor
    engine (`app.advisor.rules.blocked_dependency`), reused rather than
    reimplemented -- see `engine.py`'s "PI pack" docstring section."""
    upstream = client.post(
        "/pi/projects", json={"name": "OI Upstream Blocked", "workspace": "Products"}
    ).json()
    downstream = client.post(
        "/pi/projects", json={"name": "OI Downstream Waiting", "workspace": "Products"}
    ).json()
    client.patch(f"/pi/projects/{upstream['id']}", json={"status": "blocked"})
    client.post(
        f"/pi/projects/{downstream['id']}/dependencies",
        json={"depends_on_project_id": upstream["id"], "note": ""},
    )

    recs = get_operational_intelligence()
    pi_recs = [r for r in recs if r["source"] == "pi" and r["project"]]
    matching = [r for r in pi_recs if r["project"]["canonical_project_id"] == downstream["id"]]
    assert matching, "expected a PI-pack recommendation for the project with a blocked dependency"
    assert matching[0]["evidence"]


def test_paused_project_with_pending_work_rule(tmp_path):
    root = tmp_path / "oi-scan-root-paused"
    _write(root / "paused-app" / "README.md", "# x\n")
    _write(root / "paused-app" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "paused-app" / "NEXT_ACTION.md", "Finish the launch checklist\n")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "paused-app")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    client.patch(f"/workspace/discovered/{item['id']}", json={"status": "paused"})

    recs = get_operational_intelligence()
    matching = [
        r
        for r in recs
        if r["rule_id"] == "rule_paused_project_with_pending_work"
        and r["project"]
        and r["project"]["item_id"] == item["id"]
    ]
    assert matching
    assert any("paused" in e.lower() for e in matching[0]["evidence"])


def test_conflicting_duplicate_titles_collapse_to_one(tmp_path):
    """Conflict resolution: two workspace-wide rules never collide in this
    engine's design (each has a distinct title), so this test proves the
    *mechanism* directly against `engine._dedupe` rather than trying to
    force a naturally-occurring title collision."""
    from app.operational_intelligence.engine import _dedupe
    from app.operational_intelligence.models import make_recommendation, project_ref

    ref = project_ref(item_id="x1", canonical_project_id="c1", display_name="X")
    low = make_recommendation(
        recommendation="Same Title",
        priority=10,
        confidence=0.2,
        evidence=["low"],
        project=ref,
        suggested_action="do it",
        reason="r",
        source="discovery",
        rule_id="a",
    )
    high = make_recommendation(
        recommendation="Same Title",
        priority=90,
        confidence=0.9,
        evidence=["high"],
        project=ref,
        suggested_action="do it",
        reason="r",
        source="pi",
        rule_id="b",
    )
    result = _dedupe([low, high])
    assert len(result) == 1
    assert result[0]["priority"] == 90


def test_advisor_operational_intelligence_endpoint():
    resp = client.get("/advisor/operational-intelligence")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    for rec in body:
        _assert_canonical_shape(rec)


def test_explorer_recommendation_results_expose_evidence(tmp_path):
    _make_and_adopt(tmp_path, "3", name="explorer-evidence-app")
    resp = client.get("/explorer/search", params={"q": "explorer-evidence-app"})
    assert resp.status_code == 200
    recs = resp.json()["groups"]["Recommendation"]
    for rec in recs:
        assert "evidence" in rec
        assert isinstance(rec["evidence"], list)


def test_mission_control_consumes_operational_intelligence(tmp_path):
    _make_and_adopt(tmp_path, "4", name="mc-oi-app")
    body = client.get("/mission-control").json()
    for item in body["todays_focus"]:
        assert "expected_benefit" in item
    for item in body["needs_attention"]:
        assert "expected_benefit" in item
    if body["value_signal"]["available"]:
        assert "expected_benefit" in body["value_signal"]
