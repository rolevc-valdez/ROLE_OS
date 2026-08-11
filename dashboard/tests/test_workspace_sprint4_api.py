"""Integration tests for Sprint 4's Project Intelligence Wiring API
additions: /workspace/home, /workspace/advisor, /workspace/assets,
/workspace/activity, enriched /workspace/discovered/{id}, and freshness
fields on /workspace/summary. Real Discovery Engine runs throughout --
nothing mocked.
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_root(tmp_path: Path, suffix: str) -> Path:
    root = tmp_path / f"scan-root-{suffix}"
    _write(root / "app-a" / "README.md", "# A\n")
    _write(root / "app-a" / "NEXT_ACTION.md", "Ship the onboarding flow\n")
    _write(root / "app-a" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "app-a" / "main.py", "print(1)\n")
    _write(root / "app-a" / "logo.png", "fake-png")
    _write(root / "OTROS - no proyectos" / "junk.txt", "junk")
    return root


def _adopt_top_level(root: Path) -> dict:
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "app-a")
    client.post(
        f"/workspace/discovered/{item['id']}/adopt",
        json={"priority": "high", "business_value": "high"},
    )
    return item


def test_projects_page_top_level_view_is_enriched(tmp_path):
    root = _make_root(tmp_path, "1")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    app_a = next(i for i in items if i["name"] == "app-a")
    for field in (
        "next_action",
        "documentation_status",
        "test_status",
        "asset_count",
        "repository_count",
        "component_count",
    ):
        assert field in app_a, f"missing field: {field}"
    assert app_a["next_action"]["text"] == "Ship the onboarding flow"
    assert app_a["asset_count"] >= 1


def test_enriched_detail_endpoint_has_ai_sessions_and_next_action(tmp_path):
    root = _make_root(tmp_path, "2")
    item = _adopt_top_level(root)
    detail = client.get(f"/workspace/discovered/{item['id']}").json()
    assert "next_action" in detail
    assert "ai_sessions" in detail
    assert detail["ai_sessions"]["latest_session"] is None  # honest "not yet defined" case
    assert detail["documentation_status"]


def test_home_endpoint_not_all_zeros_with_real_data(tmp_path):
    root = _make_root(tmp_path, "3")
    _adopt_top_level(root)
    home = client.get("/workspace/home").json()
    assert home["total_adopted"] >= 1
    assert home["suggested_project"] is not None
    assert home["quick_resume"] is not None
    assert home["quick_resume"]["action_text"] == "Ship the onboarding flow"


def test_home_endpoint_latest_ai_session_is_real_when_a_session_exists(tmp_path):
    """Regression (Sprint C1: Consolidation): `get_home_portfolio`'s
    `latest_ai_session` loop read `item.get("ai_sessions")`, a key
    `enrich_project_item` never set -- so it was silently always `None`
    even with a real session in place. `enrich_project_item` now attaches
    the AI session summary it already computes, so this must be real."""
    root = _make_root(tmp_path, "4")
    item = _adopt_top_level(root)
    resume_resp = client.post(f"/workspace/discovered/{item['id']}/resume-work")
    assert resume_resp.status_code == 200

    home = client.get("/workspace/home").json()
    assert home["latest_ai_session"] is not None
    assert home["latest_ai_session"]["id"] == resume_resp.json()["session_id"]


def test_advisor_endpoint_produces_evidence_based_recommendations(tmp_path):
    root = _make_root(tmp_path, "4")
    _adopt_top_level(root)
    recs = client.get("/workspace/advisor").json()
    assert len(recs) >= 1
    for r in recs:
        assert r["evidence"], "recommendation must not be generic filler"
        assert r["project"] == "app-a"


def test_assets_endpoint_returns_real_files(tmp_path):
    root = _make_root(tmp_path, "5")
    item = _adopt_top_level(root)
    assets_by_project = client.get("/workspace/assets").json()
    assert item["id"] in assets_by_project
    filenames = {a["filename"] for a in assets_by_project[item["id"]]}
    assert "logo.png" in filenames

    scoped = client.get("/workspace/assets", params={"project_id": item["id"]}).json()
    assert {a["filename"] for a in scoped} == filenames


def test_activity_endpoint_reflects_real_events(tmp_path):
    root = _make_root(tmp_path, "6")
    _adopt_top_level(root)
    feed = client.get("/workspace/activity").json()
    assert isinstance(feed, list)
    assert any(e["type"] == "adopted" for e in feed)


def test_activity_endpoint_scopes_to_one_project_server_side(tmp_path):
    """Regression (Sprint C1: Consolidation): `project_id` now filters the
    feed on the server (restricting which projects' git/assets get
    computed at all), replacing the Discovered Project Detail page's
    previous approach of fetching the *entire* feed and filtering it
    client-side in `app.js`."""
    root = tmp_path / "scan-root-8"
    _write(root / "app-a" / "README.md", "x")
    _write(root / "app-a" / "NEXT_ACTION.md", "Ship app-a\n")
    _write(root / "app-a" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "app-b" / "README.md", "x")
    _write(root / "app-b" / "pyproject.toml", "[project]\nname='b'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item_a = next(i for i in items if i["name"] == "app-a")
    item_b = next(i for i in items if i["name"] == "app-b")
    client.post(f"/workspace/discovered/{item_a['id']}/adopt", json={})
    client.post(f"/workspace/discovered/{item_b['id']}/adopt", json={})

    full_feed = client.get("/workspace/activity").json()
    assert any(e["project_id"] == item_a["id"] for e in full_feed)
    assert any(e["project_id"] == item_b["id"] for e in full_feed)

    scoped = client.get("/workspace/activity", params={"project_id": item_a["id"]}).json()
    assert scoped
    assert all(e["project_id"] == item_a["id"] for e in scoped)


def test_excluded_folder_never_leaks_into_home_advisor_assets_activity(tmp_path):
    root = _make_root(tmp_path, "7")
    _adopt_top_level(root)

    home = client.get("/workspace/home").json()
    assert (
        home["most_recently_modified_project"] is None
        or home["most_recently_modified_project"]["name"] != "OTROS - no proyectos"
    )

    recs = client.get("/workspace/advisor").json()
    assert all(r["project"] != "OTROS - no proyectos" for r in recs)

    assets_by_project = client.get("/workspace/assets").json()
    project_names_via_assets = set()
    for records in assets_by_project.values():
        project_names_via_assets.update(a["project"] for a in records)
    assert "OTROS - no proyectos" not in project_names_via_assets

    feed = client.get("/workspace/activity").json()
    assert all(e["project_name"] != "OTROS - no proyectos" for e in feed)

    top_level = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    assert all(i["name"] != "OTROS - no proyectos" for i in top_level)


def test_summary_freshness_fields(tmp_path):
    root = _make_root(tmp_path, "8")
    client.post("/workspace/rescan", json={"root": str(root)})
    summary = client.get("/workspace/summary").json()
    for field in ("is_stale", "hours_since_scan", "stale_threshold_hours"):
        assert field in summary
    assert summary["is_stale"] is False
    assert summary["hours_since_scan"] < 1


def test_stale_data_warning_when_no_scan_yet():
    """A brand-new workspace db (no rescan ever run) must report stale."""
    import tempfile

    from app.config import Settings
    from app.workspace import service

    with tempfile.TemporaryDirectory() as d:
        settings = Settings()
        settings.workspace_db_path = Path(d) / "fresh_workspace.db"
        freshness = service.get_freshness(settings=settings)
        assert freshness["is_stale"] is True
        assert freshness["last_scan"] is None


def test_manual_projects_still_work_alongside_sprint4_wiring(tmp_path):
    root = _make_root(tmp_path, "9")
    _adopt_top_level(root)

    resp = client.post(
        "/pi/projects",
        json={"name": "Manual Sprint4 Project", "workspace": "Products", "description": "d"},
    )
    assert resp.status_code == 201
    project = resp.json()
    listed = client.get("/pi/projects").json()
    assert any(p["id"] == project["id"] for p in listed)

    # Manual project must not be duplicated into or confused with workspace data.
    top_level = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    assert all(i["name"] != "Manual Sprint4 Project" for i in top_level)


def test_real_path_with_spaces_and_parentheses(tmp_path):
    root = tmp_path / "My Drive (test@example.com)" / "1 - IA PROJECTS"
    _write(root / "app-a" / "README.md", "# A\n")
    _write(root / "app-a" / "NEXT_ACTION.md", "Ship it\n")
    _write(root / "app-a" / "pyproject.toml", "[project]\nname='a'")

    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    app_a = next(i for i in items if i["name"] == "app-a")
    client.post(f"/workspace/discovered/{app_a['id']}/adopt", json={})

    home = client.get("/workspace/home").json()
    assert home["total_adopted"] >= 1
    detail = client.get(f"/workspace/discovered/{app_a['id']}").json()
    assert detail["next_action"]["text"] == "Ship it"


def test_no_scanned_project_files_modified(tmp_path):
    import os

    root = _make_root(tmp_path, "10")

    def snapshot():
        snap = set()
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                fp = Path(dirpath) / name
                st = fp.stat()
                snap.add((str(fp), st.st_mtime, st.st_size))
        return snap

    before = snapshot()
    item = _adopt_top_level(root)
    client.get("/workspace/home")
    client.get("/workspace/advisor")
    client.get("/workspace/assets")
    client.get("/workspace/activity")
    client.get(f"/workspace/discovered/{item['id']}")
    after = snapshot()
    assert before == after
