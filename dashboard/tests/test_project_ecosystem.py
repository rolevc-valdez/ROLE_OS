"""Sprint C8 (Project Ecosystem Engine) acceptance tests.

Real Discovery Engine runs / real PI projects/dependencies/capabilities
throughout, nothing mocked -- except the one detector that reads Knowledge
cards, where the Knowledge database is a shared, read-only fixture with no
write API from this app; that detector is exercised directly against
synthetic card dicts (via monkeypatching `app.db.list_all_cards`), the
same "unit-test the pure function directly" approach used elsewhere in
this suite for read-only shared fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.main import app
from app.project_ecosystem import compute_relationships, get_project_ecosystem
from app.project_ecosystem.models import SUPPORTED_TYPES, make_relationship, project_ref
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
    root = tmp_path / f"eco-scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return adopted.json()


# ---------------------------------------------------------------------------
# Canonical relationship model
# ---------------------------------------------------------------------------


def test_supported_types_match_the_brief():
    assert set(SUPPORTED_TYPES) == {
        "depends_on",
        "uses",
        "consumes",
        "produces",
        "extends",
        "shares_assets",
        "shares_prompts",
        "shares_documentation",
        "shares_knowledge",
        "shares_sessions",
        "blocks",
        "blocked_by",
        "related",
    }


def test_make_relationship_has_every_mandated_field():
    rel = make_relationship(
        source_project=project_ref(canonical_project_id="a", display_name="A"),
        target_project=project_ref(canonical_project_id="b", display_name="B"),
        relationship_type="related",
        confidence=0.5,
        evidence=["test evidence"],
        detector="test_detector",
    )
    for field in (
        "relationship_id",
        "source_project",
        "target_project",
        "relationship_type",
        "confidence",
        "evidence",
        "detector",
        "discovered_at",
        "last_verified",
        "manual_override",
        "status",
    ):
        assert field in rel
    assert rel["manual_override"] is False
    assert rel["status"] == "active"


def test_relationship_id_is_deterministic():
    args = {
        "source_project": project_ref(canonical_project_id="a", display_name="A"),
        "target_project": project_ref(canonical_project_id="b", display_name="B"),
        "relationship_type": "related",
        "confidence": 0.5,
        "evidence": ["x"],
        "detector": "d",
    }
    rel1 = make_relationship(**args)
    rel2 = make_relationship(**args)
    assert rel1["relationship_id"] == rel2["relationship_id"]


# ---------------------------------------------------------------------------
# Dependency / capability detection (explicit PI data, high confidence)
# ---------------------------------------------------------------------------


def test_dependency_detection(settings):
    upstream = projects_db.create_project(name="Upstream", workspace="Products", settings=settings)
    downstream = projects_db.create_project(
        name="Downstream", workspace="Products", settings=settings
    )
    projects_db.create_dependency(
        downstream["id"], upstream["id"], note="needs the API", settings=settings
    )

    rels = compute_relationships(settings=settings)
    depends_on = [r for r in rels if r["relationship_type"] == "depends_on"]
    assert len(depends_on) == 1
    rel = depends_on[0]
    assert rel["source_project"]["display_name"] == "Downstream"
    assert rel["target_project"]["display_name"] == "Upstream"
    assert rel["confidence"] == 1.0
    assert any("needs the API" in e for e in rel["evidence"])


def test_blocked_dependency_detection(settings):
    upstream = projects_db.create_project(
        name="Blocked Upstream", workspace="Products", status="blocked", settings=settings
    )
    downstream = projects_db.create_project(name="Waiting", workspace="Products", settings=settings)
    projects_db.create_dependency(downstream["id"], upstream["id"], settings=settings)

    rels = compute_relationships(settings=settings)
    blocks = [r for r in rels if r["relationship_type"] == "blocks"]
    blocked_by = [r for r in rels if r["relationship_type"] == "blocked_by"]
    assert len(blocks) == 1
    assert blocks[0]["source_project"]["display_name"] == "Blocked Upstream"
    assert blocks[0]["target_project"]["display_name"] == "Waiting"
    assert len(blocked_by) == 1
    assert blocked_by[0]["source_project"]["display_name"] == "Waiting"


def test_capability_detection(settings):
    provider = projects_db.create_project(name="Provider", workspace="Products", settings=settings)
    consumer = projects_db.create_project(name="Consumer", workspace="Products", settings=settings)
    cap = projects_db.create_capability(provider["id"], "Auth Service", settings=settings)
    projects_db.consume_capability(cap["id"], consumer["id"], settings=settings)

    rels = compute_relationships(settings=settings)
    uses = [r for r in rels if r["relationship_type"] == "uses"]
    produces = [r for r in rels if r["relationship_type"] == "produces"]
    assert any(
        r["source_project"]["display_name"] == "Consumer"
        and r["target_project"]["display_name"] == "Provider"
        for r in uses
    )
    assert any(
        r["source_project"]["display_name"] == "Provider"
        and r["target_project"]["display_name"] == "Consumer"
        for r in produces
    )


# ---------------------------------------------------------------------------
# Shared assets (canonical Assets index, via real filesystem projects)
# ---------------------------------------------------------------------------


def test_shared_assets_detection(tmp_path):
    root = tmp_path / "eco-scan-root-assets"
    _write(root / "asset-app-a" / "README.md", "# A\n")
    _write(root / "asset-app-a" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "asset-app-a" / "logo.png", "identical-bytes-shared-logo")
    _write(root / "asset-app-b" / "README.md", "# B\n")
    _write(root / "asset-app-b" / "pyproject.toml", "[project]\nname='b'")
    _write(root / "asset-app-b" / "logo.png", "identical-bytes-shared-logo")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    for name in ("asset-app-a", "asset-app-b"):
        item = next(i for i in items if i["name"] == name)
        client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    rels = compute_relationships()
    shared = [r for r in rels if r["relationship_type"] == "shares_assets"]
    names = {r["source_project"]["display_name"] for r in shared} | {
        r["target_project"]["display_name"] for r in shared
    }
    assert "asset-app-a" in names and "asset-app-b" in names


# ---------------------------------------------------------------------------
# Shared knowledge (unit-tested directly against synthetic cards -- see
# module docstring for why this one detector is exercised this way)
# ---------------------------------------------------------------------------


def test_shared_knowledge_detection(monkeypatch, settings):
    from app import db as knowledge_db
    from app.project_ecosystem.detectors import detect_shared_knowledge

    cards = [
        {"project": "Proj Alpha", "people": [], "applications": ["Figma"], "vendors": []},
        {"project": "Proj Beta", "people": [], "applications": ["Figma"], "vendors": []},
        {"project": "Proj Gamma", "people": [], "applications": ["Notion"], "vendors": []},
    ]
    monkeypatch.setattr(knowledge_db, "list_all_cards", lambda settings=None: cards)

    all_contexts = [
        {"id": "a1", "item_id": None, "display_name": "Proj Alpha"},
        {"id": "b1", "item_id": None, "display_name": "Proj Beta"},
        {"id": "g1", "item_id": None, "display_name": "Proj Gamma"},
    ]
    rels = detect_shared_knowledge(all_contexts, settings)
    assert len(rels) == 1
    names = {rels[0]["source_project"]["display_name"], rels[0]["target_project"]["display_name"]}
    assert names == {"Proj Alpha", "Proj Beta"}
    assert "figma" in rels[0]["evidence"][0].lower()


# ---------------------------------------------------------------------------
# Shared documentation (bounded text-reference read)
# ---------------------------------------------------------------------------


def test_shared_documentation_detection(tmp_path):
    root = tmp_path / "eco-scan-root-docs"
    _write(root / "doc-app-alpha" / "README.md", "# Alpha\nBuilt on top of doc-app-beta.\n")
    _write(root / "doc-app-alpha" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "doc-app-beta" / "README.md", "# Beta\n")
    _write(root / "doc-app-beta" / "pyproject.toml", "[project]\nname='b'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    for name in ("doc-app-alpha", "doc-app-beta"):
        item = next(i for i in items if i["name"] == name)
        client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    rels = compute_relationships()
    shared_docs = [
        r
        for r in rels
        if r["relationship_type"] == "shares_documentation"
        and r["source_project"]["display_name"] == "doc-app-alpha"
    ]
    assert shared_docs
    assert "doc-app-beta" in shared_docs[0]["evidence"][0]


# ---------------------------------------------------------------------------
# Impact summary
# ---------------------------------------------------------------------------


def test_impact_summary_risk_levels(settings):
    upstream = projects_db.create_project(name="Core", workspace="Products", settings=settings)
    for i in range(3):
        dependent = projects_db.create_project(
            name=f"Dependent {i}", workspace="Products", settings=settings
        )
        projects_db.create_dependency(dependent["id"], upstream["id"], settings=settings)

    ecosystem = get_project_ecosystem(upstream["id"], settings=settings)
    assert ecosystem is not None
    assert ecosystem["impact_summary"]["risk"] == "high"
    assert len(ecosystem["impact_summary"]["affected_projects"]) == 3


def test_impact_summary_honest_when_no_relationships(settings):
    solo = projects_db.create_project(name="Solo Project", workspace="Products", settings=settings)
    ecosystem = get_project_ecosystem(solo["id"], settings=settings)
    assert ecosystem is not None
    assert ecosystem["impact_summary"]["risk"] == "none"
    assert ecosystem["impact_summary"]["confidence"] == 0.0
    assert ecosystem["relationships"] == []


def test_get_project_ecosystem_returns_none_for_unknown_project(settings):
    assert get_project_ecosystem("does-not-exist", settings=settings) is None


# ---------------------------------------------------------------------------
# Manual overrides
# ---------------------------------------------------------------------------


def test_manual_override_dismiss(settings):
    from app.project_ecosystem import db as ecosystem_db

    upstream = projects_db.create_project(
        name="Dep Upstream", workspace="Products", settings=settings
    )
    downstream = projects_db.create_project(
        name="Dep Downstream", workspace="Products", settings=settings
    )
    projects_db.create_dependency(downstream["id"], upstream["id"], settings=settings)

    rels_before = compute_relationships(settings=settings)
    depends_on = next(r for r in rels_before if r["relationship_type"] == "depends_on")

    ecosystem_db.set_override(depends_on["relationship_id"], "dismissed", settings=settings)
    rels_after = compute_relationships(settings=settings)
    assert depends_on["relationship_id"] not in {r["relationship_id"] for r in rels_after}

    ecosystem_db.clear_override(depends_on["relationship_id"], settings=settings)
    rels_restored = compute_relationships(settings=settings)
    assert depends_on["relationship_id"] in {r["relationship_id"] for r in rels_restored}


def test_manual_override_confirm(settings):
    from app.project_ecosystem import db as ecosystem_db

    upstream = projects_db.create_project(
        name="Conf Upstream", workspace="Products", settings=settings
    )
    downstream = projects_db.create_project(
        name="Conf Downstream", workspace="Products", settings=settings
    )
    projects_db.create_dependency(downstream["id"], upstream["id"], settings=settings)

    rels_before = compute_relationships(settings=settings)
    depends_on = next(r for r in rels_before if r["relationship_type"] == "depends_on")
    ecosystem_db.set_override(depends_on["relationship_id"], "confirmed", settings=settings)

    rels_after = compute_relationships(settings=settings)
    confirmed = next(r for r in rels_after if r["relationship_id"] == depends_on["relationship_id"])
    assert confirmed["status"] == "confirmed"
    assert confirmed["manual_override"] is True


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def test_api_returns_404_for_unknown_project():
    resp = client.get("/project-ecosystem/does-not-exist")
    assert resp.status_code == 404


def test_api_returns_full_shape():
    project = client.post(
        "/pi/projects", json={"name": "API Test Project", "workspace": "Products"}
    ).json()
    resp = client.get(f"/project-ecosystem/{project['id']}")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "relationships",
        "dependencies",
        "consumers",
        "blocks",
        "blocked_by",
        "shared_assets",
        "shared_prompts",
        "shared_documents",
        "shared_knowledge",
        "shared_sessions",
        "impact_summary",
    ):
        assert key in body


# ---------------------------------------------------------------------------
# Project Detail (Explorer's Project Hub) integration
# ---------------------------------------------------------------------------


def test_project_hub_includes_ecosystem_section(tmp_path):
    item = _make_and_adopt(tmp_path, "1", "hub-eco-app")
    resp = client.get(f"/explorer/project/{item['canonical_project_id']}")
    assert resp.status_code == 200
    assert "ecosystem" in resp.json()


# ---------------------------------------------------------------------------
# Explorer relationship search
# ---------------------------------------------------------------------------


def test_explorer_search_used_by():
    master = client.post(
        "/pi/projects", json={"name": "ROLE MASTER", "workspace": "Products"}
    ).json()
    consumer = client.post(
        "/pi/projects", json={"name": "ROLE Commerce Factory", "workspace": "Products"}
    ).json()
    client.post(
        f"/pi/projects/{consumer['id']}/dependencies",
        json={"depends_on_project_id": master["id"], "note": ""},
    )

    resp = client.get("/explorer/search", params={"q": "ROLE MASTER"})
    assert resp.status_code == 200
    results = resp.json()["groups"]["Ecosystem Relationship"]
    assert any("Used by ROLE Commerce Factory" in r["title"] for r in results)


# ---------------------------------------------------------------------------
# Mission Control / Operational Intelligence integration
# ---------------------------------------------------------------------------


def test_operational_intelligence_unblocks_dependents_rule(settings):
    upstream = projects_db.create_project(name="OI Core", workspace="Products", settings=settings)
    downstream = projects_db.create_project(
        name="OI Dependent", workspace="Products", settings=settings
    )
    projects_db.create_dependency(downstream["id"], upstream["id"], settings=settings)
    session = projects_db.create_ai_session(upstream["id"], assistant="claude", settings=settings)
    projects_db.create_ai_session_snapshot(
        session["id"], next_prompt="Finish the core API", settings=settings
    )

    from app.operational_intelligence import get_operational_intelligence

    recs = get_operational_intelligence(settings=settings)
    matching = [r for r in recs if r["rule_id"] == "rule_unblocks_dependents"]
    assert matching
    assert "OI Dependent" in matching[0]["recommendation"]


# ---------------------------------------------------------------------------
# Project Memory integration
# ---------------------------------------------------------------------------


def test_project_memory_includes_bounded_related_projects_section(settings):
    upstream = projects_db.create_project(
        name="Memory Upstream", workspace="Products", settings=settings
    )
    downstream = projects_db.create_project(
        name="Memory Downstream", workspace="Products", settings=settings
    )
    projects_db.create_dependency(downstream["id"], upstream["id"], settings=settings)

    from app.project_memory.service import build_project_memory

    memory = build_project_memory(downstream["id"], settings=settings)
    assert "related_projects" in memory
    assert "Memory Upstream" in memory["related_projects"]["dependencies"]


def test_project_memory_preview_skips_related_projects_for_performance(settings):
    """`preview_resume_state` (called on every ProjectContext build) must
    never trigger the Ecosystem Engine's whole-workspace pass."""
    from app.project_memory.service import build_project_memory

    project = projects_db.create_project(
        name="Cheap Preview", workspace="Products", settings=settings
    )
    memory = build_project_memory(
        project["id"],
        settings=settings,
        include_operational_recommendation=False,
        include_related_projects=False,
    )
    assert memory["related_projects"] == {
        "dependencies": [],
        "consumers": [],
        "recent_shared_decisions": [],
    }


# ---------------------------------------------------------------------------
# Security: excluded folders / adopted-only boundary
# ---------------------------------------------------------------------------


def test_ecosystem_ignores_unadopted_discovered_projects(tmp_path):
    root = tmp_path / "eco-scan-root-unadopted"
    _write(root / "not-adopted-app" / "README.md", "# x\n")
    _write(root / "not-adopted-app" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "not-adopted-app")
    # deliberately not adopted

    rels = compute_relationships()
    names = set()
    for r in rels:
        names.add(r["source_project"]["display_name"])
        names.add(r["target_project"]["display_name"])
    assert "not-adopted-app" not in names
    del item


# ---------------------------------------------------------------------------
# Performance: one detector pass per request, no repeated asset walk
# ---------------------------------------------------------------------------


def test_no_duplicate_asset_walk_when_computing_ecosystem(tmp_path, monkeypatch):
    root = tmp_path / "eco-scan-root-perf"
    _write(root / "perf-eco-app" / "README.md", "# x\n")
    _write(root / "perf-eco-app" / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "perf-eco-app")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    from app.assets import service as assets_service

    calls = []
    original = assets_service.assets_db.list_overrides

    def counting_list_overrides(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(assets_service.assets_db, "list_overrides", counting_list_overrides)

    from app.assets.service import request_scope

    with request_scope():
        compute_relationships()
    assert len(calls) == 1
