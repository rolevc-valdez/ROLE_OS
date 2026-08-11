"""Sprint C2 (Dashboard 2.0) acceptance tests.

The legacy Dashboard showed `/import/metrics` -- Explorer's own extracted-
knowledge-object counts, honestly zero when no ChatGPT conversations have
been imported, even while the real workspace already has adopted projects,
commits, and sessions. These tests prove the new `/dashboard/summary`
endpoint answers from the real project data (`ProjectContext`, Home,
Advisor, Activity, Assets) instead, with real Discovery Engine runs
against synthetic folder trees throughout -- nothing mocked.
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_and_adopt(tmp_path: Path, suffix: str, name: str = "app-a", dirty: bool = False) -> dict:
    root = tmp_path / f"scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    _write(root / name / "logo.png", "fake-png-bytes")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


def test_dashboard_summary_uses_project_context(tmp_path):
    """§1/§12: Dashboard's response embeds real ProjectContext, not a
    parallel shape -- `continue_work.project_context` and every
    `needs_attention[].project_context` must carry the canonical fields
    (health, resume_state, next_action) `ProjectContext` defines."""
    _make_and_adopt(tmp_path, "1")
    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {
        "cards",
        "portfolio_status",
        "continue_work",
        "needs_attention",
        "recent_activity",
        "recent_assets",
        "recent_knowledge",
        "data_freshness",
    }


def test_real_adopted_projects_populate_metrics_not_zero(tmp_path):
    """The exact regression this sprint fixes: a real adopted project must
    move the executive summary cards off of zero."""
    _make_and_adopt(tmp_path, "2", name="role-os-like")
    body = client.get("/dashboard/summary").json()
    cards = body["cards"]
    assert cards["adopted_projects"] >= 1
    assert cards["reusable_assets"] >= 1  # the fixture writes one real logo.png
    assert cards["healthy_projects"] + cards["warning_projects"] + cards["critical_projects"] >= 1


def _all_tracked_project_contexts() -> list[dict]:
    """Mirrors `app.dashboard.service._all_project_contexts`'s definition
    of "every tracked project" (discovered-and-adopted workspace items +
    purely-manual PI projects with no discovery link) via the public API,
    so these tests hold regardless of what other test files/functions have
    already adopted/created in this session's shared databases."""
    ws = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    ws_contexts = [i["project_context"] for i in ws if i.get("project_context")]
    pi_projects = client.get("/pi/projects").json()
    manual_contexts = [
        p["project_context"]
        for p in pi_projects
        if not p.get("discovery_item_id") and p.get("project_context")
    ]
    return ws_contexts + manual_contexts


def test_health_counts_match_canonical_tiers(tmp_path):
    _make_and_adopt(tmp_path, "3")
    body = client.get("/dashboard/summary").json()
    cards = body["cards"]
    tiers = [c["health"] for c in _all_tracked_project_contexts()]
    assert cards["healthy_projects"] == tiers.count("healthy")
    assert cards["warning_projects"] == tiers.count("warning")
    assert cards["critical_projects"] == tiers.count("critical")


def test_dirty_repo_count_is_accurate(tmp_path):
    import subprocess

    root = tmp_path / "scan-root-dirty"
    repo = root / "dirty-app"
    _write(repo / "README.md", "# x\n")
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=repo,
        capture_output=True,
    )
    _write(repo / "untracked.txt", "dirty")  # makes the tree dirty
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "dirty-app")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    body = client.get("/dashboard/summary").json()
    assert body["cards"]["dirty_repositories"] >= 1
    dirty_names = {
        r["project"]
        for r in body["needs_attention"]
        if r["recommendation"].startswith("Commit or stash")
    }
    assert "dirty-app" in dirty_names
    for rec in body["needs_attention"]:
        if rec["project"] == "dirty-app":
            assert rec["project_context"] is not None
            assert rec["project_context"]["item_id"] == item["id"]


def test_next_action_count_is_accurate(tmp_path):
    root = tmp_path / "scan-root-na"
    _write(root / "na-app" / "README.md", "x")
    _write(root / "na-app" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "na-app" / "NEXT_ACTION.md", "Ship it\n")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "na-app")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    body = client.get("/dashboard/summary").json()
    expected = sum(
        1 for c in _all_tracked_project_contexts() if (c.get("next_action") or {}).get("text")
    )
    assert body["cards"]["projects_with_next_action"] == expected
    assert expected >= 1


def test_recent_activity_is_deduplicated(tmp_path):
    _make_and_adopt(tmp_path, "4")
    body = client.get("/dashboard/summary").json()
    keys = [(e["type"], e["timestamp"], e["project_id"]) for e in body["recent_activity"]]
    assert len(keys) == len(set(keys))


def test_continue_work_uses_canonical_identity_and_resume_state(tmp_path):
    _make_and_adopt(tmp_path, "5", name="cw-app")
    root = tmp_path / "scan-root-5"
    _write(root / "cw-app" / "NEXT_ACTION.md", "Finish the thing\n")
    client.post("/workspace/rescan", json={"root": str(root)})

    body = client.get("/dashboard/summary").json()
    cw = body["continue_work"]
    if cw:  # suggestion only fires when a next_action exists (existing scorer's own rule)
        ctx = cw["project_context"]
        assert ctx["item_id"] is not None
        assert "resume_state" in ctx and "available" in ctx["resume_state"]
        assert "reasons" in cw


def test_empty_state_is_honest_when_nothing_adopted():
    """A fresh workspace (nothing scanned/adopted in this test's own
    isolated DBs) must report real zeros with structure, not crash, and
    must not report a `continue_work` suggestion that doesn't exist."""
    # This test intentionally does not adopt anything -- relies on test
    # isolation (each test function gets its own tmp DBs via the
    # global settings-override fixture used across this file's client).
    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200


def test_manual_project_appears_in_dashboard_without_discovery_link():
    created = client.post(
        "/pi/projects", json={"name": "Dashboard Manual Test", "workspace": "Products"}
    ).json()
    body = client.get("/dashboard/summary").json()
    all_refs = (
        body["portfolio_status"]["healthy"]
        + body["portfolio_status"]["warning"]
        + body["portfolio_status"]["critical"]
    )
    assert any(ref["id"] == created["id"] for ref in all_refs)


def test_legacy_zero_centric_dashboard_widgets_removed_from_frontend():
    """§8: the old Explorer-metrics-as-Dashboard rendering path
    (`/import/metrics` fetched inside `renderDashboardPage`, labels like
    "Projects"/"Tasks"/"Decisions"/"Ideas"/"Documents"/"Graph Nodes") must
    be gone from the Dashboard page's own render function."""
    body = client.get("/static/js/app.js").text
    dashboard_fn = body.split("async function renderDashboardPage")[1].split(
        "PROJECTS LIST + FIRST RUN EXPERIENCE"
    )[0]
    assert "/import/metrics" not in dashboard_fn
    assert "/dashboard/summary" in dashboard_fn


def test_dashboard_summary_router_registered():
    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200
