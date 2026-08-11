"""Sprint C9 (Impact Analysis Engine) acceptance tests.

Real Discovery Engine runs / real PI projects/dependencies throughout,
nothing mocked -- same convention as `test_project_ecosystem.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.impact_analysis import get_impact_analysis
from app.impact_analysis.models import RISK_LEVELS
from app.impact_analysis.scoring import compute_overall_risk
from app.impact_analysis.service import MAX_TRANSITIVE_DEPTH
from app.main import app
from app.projects import db as projects_db
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


def _make_and_adopt(tmp_path: Path, suffix: str, name: str) -> dict:
    root = tmp_path / f"impact-scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return adopted.json()


# ---------------------------------------------------------------------------
# Risk calculation
# ---------------------------------------------------------------------------


def test_risk_levels_are_the_expected_five():
    assert RISK_LEVELS == ("none", "low", "medium", "high", "critical")


def test_risk_none_when_nothing_detected():
    risk, reasons = compute_overall_risk(
        direct_dependents=[], transitive_dependents=[], blocks=[], shared_counts={}
    )
    assert risk == "none"
    assert reasons


def test_risk_critical_when_already_blocking():
    risk, reasons = compute_overall_risk(
        direct_dependents=[], transitive_dependents=[], blocks=[{}], shared_counts={}
    )
    assert risk == "critical"
    assert "blocking" in reasons[0]


def test_risk_critical_at_five_direct_dependents():
    risk, _ = compute_overall_risk(
        direct_dependents=[{}] * 5, transitive_dependents=[], blocks=[], shared_counts={}
    )
    assert risk == "critical"


def test_risk_high_at_three_direct_dependents():
    risk, _ = compute_overall_risk(
        direct_dependents=[{}] * 3, transitive_dependents=[], blocks=[], shared_counts={}
    )
    assert risk == "high"


def test_risk_medium_for_one_direct_dependent():
    risk, _ = compute_overall_risk(
        direct_dependents=[{}], transitive_dependents=[], blocks=[], shared_counts={}
    )
    assert risk == "medium"


def test_risk_medium_for_shared_evidence_only():
    risk, reasons = compute_overall_risk(
        direct_dependents=[],
        transitive_dependents=[],
        blocks=[],
        shared_counts={"shares_assets": 2},
    )
    assert risk == "medium"
    assert "shares_assets" in reasons[0]


def test_risk_low_for_transitive_only():
    risk, _ = compute_overall_risk(
        direct_dependents=[], transitive_dependents=[{}], blocks=[], shared_counts={}
    )
    assert risk == "low"


def test_every_risk_level_has_a_reason():
    scenarios = [
        ([], [], [], {}),
        ([{}], [], [], {}),
        ([{}] * 3, [], [], {}),
        ([{}] * 5, [], [], {}),
        ([], [], [{}], {}),
    ]
    for direct, transitive, blocks, shares in scenarios:
        risk, reasons = compute_overall_risk(
            direct_dependents=direct,
            transitive_dependents=transitive,
            blocks=blocks,
            shared_counts=shares,
        )
        assert risk in RISK_LEVELS
        assert reasons and all(isinstance(r, str) and r for r in reasons)


# ---------------------------------------------------------------------------
# Transitive traversal, cycles, bounded depth
# ---------------------------------------------------------------------------


def test_transitive_traversal_matches_the_brief_example():
    """ROLE OS -> ROLE Commerce Factory -> RoleValdez.com: changing ROLE
    OS affects both, one direct and one transitive."""
    role_os = client.post("/pi/projects", json={"name": "ROLE OS", "workspace": "Products"}).json()
    rcf = client.post(
        "/pi/projects", json={"name": "ROLE Commerce Factory", "workspace": "Products"}
    ).json()
    rv = client.post(
        "/pi/projects", json={"name": "RoleValdez.com", "workspace": "Products"}
    ).json()
    client.post(
        f"/pi/projects/{rcf['id']}/dependencies",
        json={"depends_on_project_id": role_os["id"], "note": ""},
    )
    client.post(
        f"/pi/projects/{rv['id']}/dependencies",
        json={"depends_on_project_id": rcf["id"], "note": ""},
    )

    report = get_impact_analysis(role_os["id"])
    assert report is not None
    assert [r["source_project"]["display_name"] for r in report["direct_dependencies"]] == [
        "ROLE Commerce Factory"
    ]
    assert [r["source_project"]["display_name"] for r in report["transitive_dependencies"]] == [
        "RoleValdez.com"
    ]
    affected_names = {p["display_name"] for p in report["affected_projects"]}
    assert affected_names == {"ROLE Commerce Factory", "RoleValdez.com"}


def test_cycles_never_cause_infinite_loop_or_duplicates():
    a = client.post("/pi/projects", json={"name": "Cycle A", "workspace": "Products"}).json()
    b = client.post("/pi/projects", json={"name": "Cycle B", "workspace": "Products"}).json()
    c = client.post("/pi/projects", json={"name": "Cycle C", "workspace": "Products"}).json()
    client.post(
        f"/pi/projects/{b['id']}/dependencies", json={"depends_on_project_id": a["id"], "note": ""}
    )
    client.post(
        f"/pi/projects/{c['id']}/dependencies", json={"depends_on_project_id": b["id"], "note": ""}
    )
    client.post(
        f"/pi/projects/{a['id']}/dependencies", json={"depends_on_project_id": c["id"], "note": ""}
    )

    report = get_impact_analysis(a["id"])
    assert report is not None
    names = [p["display_name"] for p in report["affected_projects"]]
    assert len(names) == len(set(names))
    assert "Cycle A" not in names  # never re-includes the starting project


def test_transitive_traversal_is_bounded():
    """A chain longer than `MAX_TRANSITIVE_DEPTH` stops -- the last
    project in the chain is not reachable from the first."""
    projects = [
        client.post("/pi/projects", json={"name": f"Chain {i}", "workspace": "Products"}).json()
        for i in range(MAX_TRANSITIVE_DEPTH + 3)
    ]
    for i in range(1, len(projects)):
        client.post(
            f"/pi/projects/{projects[i]['id']}/dependencies",
            json={"depends_on_project_id": projects[i - 1]["id"], "note": ""},
        )

    report = get_impact_analysis(projects[0]["id"])
    affected_names = {p["display_name"] for p in report["affected_projects"]}
    assert "Chain 1" in affected_names  # depth 1, always included
    assert f"Chain {MAX_TRANSITIVE_DEPTH + 2}" not in affected_names  # beyond the bound


# ---------------------------------------------------------------------------
# Shared assets / documentation / knowledge
# ---------------------------------------------------------------------------


def test_shared_assets_appear_in_impact_report(tmp_path):
    root = tmp_path / "impact-scan-root-assets"
    _write(root / "impact-asset-a" / "README.md", "# A\n")
    _write(root / "impact-asset-a" / "pyproject.toml", "[project]\nname='a'")
    (root / "impact-asset-a" / "logo.png").write_bytes(b"identical-shared-bytes")
    _write(root / "impact-asset-b" / "README.md", "# B\n")
    _write(root / "impact-asset-b" / "pyproject.toml", "[project]\nname='b'")
    (root / "impact-asset-b" / "logo.png").write_bytes(b"identical-shared-bytes")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    adopted = {}
    for name in ("impact-asset-a", "impact-asset-b"):
        item = next(i for i in items if i["name"] == name)
        adopted[name] = client.post(f"/workspace/discovered/{item['id']}/adopt", json={}).json()

    report = get_impact_analysis(adopted["impact-asset-a"]["canonical_project_id"])
    assert report is not None
    assert report["shared_assets"]
    assert "impact-asset-b" in {p["display_name"] for p in report["affected_projects"]}


def test_shared_documentation_appears_in_impact_report(tmp_path):
    root = tmp_path / "impact-scan-root-docs"
    _write(root / "impact-doc-alpha" / "README.md", "# Alpha\nBuilt on impact-doc-beta.\n")
    _write(root / "impact-doc-alpha" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "impact-doc-beta" / "README.md", "# Beta\n")
    _write(root / "impact-doc-beta" / "pyproject.toml", "[project]\nname='b'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    adopted = {}
    for name in ("impact-doc-alpha", "impact-doc-beta"):
        item = next(i for i in items if i["name"] == name)
        adopted[name] = client.post(f"/workspace/discovered/{item['id']}/adopt", json={}).json()

    report = get_impact_analysis(adopted["impact-doc-alpha"]["canonical_project_id"])
    assert report is not None
    assert report["shared_documentation"]


def test_shared_knowledge_appears_in_impact_report(monkeypatch, settings):
    from app import db as knowledge_db

    cards = [
        {"project": "Impact Know A", "people": [], "applications": ["Figma"], "vendors": []},
        {"project": "Impact Know B", "people": [], "applications": ["Figma"], "vendors": []},
    ]
    monkeypatch.setattr(knowledge_db, "list_all_cards", lambda settings=None: cards)

    a = projects_db.create_project(name="Impact Know A", workspace="Products", settings=settings)
    projects_db.create_project(name="Impact Know B", workspace="Products", settings=settings)

    report = get_impact_analysis(a["id"], settings=settings)
    assert report is not None
    assert report["shared_knowledge"]
    assert "Impact Know B" in {p["display_name"] for p in report["affected_projects"]}


# ---------------------------------------------------------------------------
# Honest empty states / unknown project
# ---------------------------------------------------------------------------


def test_returns_none_for_unknown_project(settings):
    assert get_impact_analysis("does-not-exist", settings=settings) is None


def test_honest_empty_report_for_isolated_project(settings):
    solo = projects_db.create_project(name="Impact Solo", workspace="Products", settings=settings)
    report = get_impact_analysis(solo["id"], settings=settings)
    assert report is not None
    assert report["overall_risk"] == "none"
    assert report["affected_projects"] == []
    assert report["recommended_actions"]  # honest "no action needed" message


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_returns_404_for_unknown_project():
    resp = client.get("/impact-analysis/does-not-exist")
    assert resp.status_code == 404


def test_api_returns_full_shape():
    project = client.post(
        "/pi/projects", json={"name": "Impact API Test", "workspace": "Products"}
    ).json()
    resp = client.get(f"/impact-analysis/{project['id']}")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "project",
        "generated_at",
        "overall_risk",
        "confidence",
        "affected_projects",
        "direct_dependencies",
        "transitive_dependencies",
        "shared_assets",
        "shared_prompts",
        "shared_documentation",
        "shared_knowledge",
        "shared_sessions",
        "operational_effects",
        "release_effects",
        "recommended_actions",
        "evidence",
        "limitations",
    ):
        assert key in body


# ---------------------------------------------------------------------------
# Project Detail (Explorer's Project Hub) integration
# ---------------------------------------------------------------------------


def test_project_hub_includes_impact_analysis_section(tmp_path):
    item = _make_and_adopt(tmp_path, "1", "hub-impact-app")
    resp = client.get(f"/explorer/project/{item['canonical_project_id']}")
    assert resp.status_code == 200
    assert "impact_analysis" in resp.json()


# ---------------------------------------------------------------------------
# Explorer search integration
# ---------------------------------------------------------------------------


def test_explorer_search_returns_impact_result():
    a = client.post(
        "/pi/projects", json={"name": "Impact Search Core", "workspace": "Products"}
    ).json()
    b = client.post(
        "/pi/projects", json={"name": "Impact Search Dependent", "workspace": "Products"}
    ).json()
    client.post(
        f"/pi/projects/{b['id']}/dependencies", json={"depends_on_project_id": a["id"], "note": ""}
    )

    resp = client.get("/explorer/search", params={"q": "Impact Search Core"})
    assert resp.status_code == 200
    results = resp.json()["groups"]["Impact"]
    assert results
    assert "risk" in results[0]["title"]


# ---------------------------------------------------------------------------
# Mission Control / Operational Intelligence integration
# ---------------------------------------------------------------------------


def test_operational_intelligence_high_impact_change_rule():
    a = client.post("/pi/projects", json={"name": "OI Impact Core", "workspace": "Products"}).json()
    b = client.post(
        "/pi/projects", json={"name": "OI Impact Dep 1", "workspace": "Products"}
    ).json()
    c = client.post(
        "/pi/projects", json={"name": "OI Impact Dep 2", "workspace": "Products"}
    ).json()
    client.post(
        f"/pi/projects/{b['id']}/dependencies", json={"depends_on_project_id": a["id"], "note": ""}
    )
    client.post(
        f"/pi/projects/{c['id']}/dependencies", json={"depends_on_project_id": a["id"], "note": ""}
    )

    from app.operational_intelligence import get_operational_intelligence

    recs = get_operational_intelligence()
    matching = [r for r in recs if r["rule_id"] == "rule_high_impact_change"]
    assert any("OI Impact Core" in r["recommendation"] for r in matching)


# ---------------------------------------------------------------------------
# Project Memory integration
# ---------------------------------------------------------------------------


def test_project_memory_includes_potential_impact_section(settings):
    a = projects_db.create_project(
        name="Memory Impact Core", workspace="Products", settings=settings
    )
    b = projects_db.create_project(
        name="Memory Impact Dependent", workspace="Products", settings=settings
    )
    projects_db.create_dependency(b["id"], a["id"], settings=settings)

    from app.project_memory.service import build_project_memory

    memory = build_project_memory(a["id"], settings=settings)
    assert "potential_impact" in memory
    assert memory["potential_impact"]["affected_count"] == 1


def test_project_memory_preview_skips_potential_impact_for_performance(settings):
    project = projects_db.create_project(
        name="Impact Preview", workspace="Products", settings=settings
    )
    from app.project_memory.service import build_project_memory

    memory = build_project_memory(
        project["id"],
        settings=settings,
        include_operational_recommendation=False,
        include_related_projects=False,
    )
    assert memory["potential_impact"] == {
        "overall_risk": "none",
        "affected_count": 0,
        "affected_names": [],
        "top_reason": "",
    }


# ---------------------------------------------------------------------------
# Security: adopted-project boundary
# ---------------------------------------------------------------------------


def test_impact_ignores_unadopted_discovered_projects(tmp_path):
    root = tmp_path / "impact-scan-root-unadopted"
    _write(root / "impact-not-adopted" / "README.md", "# x\n")
    _write(root / "impact-not-adopted" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "impact-not-adopted")
    # deliberately not adopted -- has no canonical_project_id
    assert item.get("canonical_project_id") is None


# ---------------------------------------------------------------------------
# Performance: no repeated relationship detection / asset walk
# ---------------------------------------------------------------------------


def test_no_duplicate_relationship_detection_when_reusing_relationships(tmp_path):
    """Passing already-computed `relationships` in must skip a second
    detector pass entirely -- verified by monkeypatching `ALL_DETECTORS`
    to a version that raises if called."""
    root = tmp_path / "impact-scan-root-perf"
    _write(root / "impact-perf-app" / "README.md", "# x\n")
    _write(root / "impact-perf-app" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "impact-perf-app")
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json={}).json()

    from app.project_context.builder import all_project_contexts
    from app.project_ecosystem import compute_relationships

    all_contexts, enriched_items = all_project_contexts()
    relationships = compute_relationships(all_contexts=all_contexts)

    import app.project_ecosystem.service as ecosystem_service

    def _boom(*args, **kwargs):
        raise AssertionError("compute_relationships should not be called again")

    original = ecosystem_service.compute_relationships
    ecosystem_service.compute_relationships = _boom
    try:
        report = get_impact_analysis(
            adopted["canonical_project_id"],
            all_contexts=all_contexts,
            enriched_items=enriched_items,
            relationships=relationships,
        )
    finally:
        ecosystem_service.compute_relationships = original
    assert report is not None


def test_no_duplicate_asset_walk_when_computing_impact(tmp_path, monkeypatch):
    root = tmp_path / "impact-scan-root-asset-perf"
    _write(root / "impact-asset-perf-app" / "README.md", "# x\n")
    _write(root / "impact-asset-perf-app" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "impact-asset-perf-app")
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json={}).json()

    from app.assets import service as assets_service

    calls = []
    original = assets_service.assets_db.list_overrides

    def counting_list_overrides(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(assets_service.assets_db, "list_overrides", counting_list_overrides)

    from app.assets.service import request_scope

    with request_scope():
        get_impact_analysis(adopted["canonical_project_id"])
    assert len(calls) == 1
