"""Sprint C5 (Mission Control) acceptance tests.

Mirrors `test_dashboard_v2.py`'s convention: real Discovery Engine runs
against synthetic folder trees, no mocking of the domain logic -- only the
one filesystem-walk counter test below monkeypatches anything, and only to
observe a call count, never to fake a result.
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from app.mission_control.service import build_mission_control
from fastapi.testclient import TestClient

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_and_adopt(tmp_path: Path, suffix: str, name: str = "app-a", dirty: bool = False) -> dict:
    root = tmp_path / f"mc-scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    _write(root / name / "logo.png", "fake-png-bytes")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


PAYLOAD_KEYS = {
    "generated_at",
    "data_freshness",
    "primary_focus",
    "todays_focus",
    "since_last_time",
    "needs_attention",
    "value_signal",
    "portfolio",
    "recent_activity",
    "daily_session",
    "snapshot_continuity",
    "quick_actions",
    "total_projects_tracked",
}


def test_mission_control_router_registered_and_shaped():
    resp = client.get("/mission-control")
    assert resp.status_code == 200
    assert set(resp.json().keys()) >= PAYLOAD_KEYS


def test_empty_workspace_gives_honest_empty_state():
    """A fresh workspace (nothing adopted in this test's own isolated
    DBs -- see conftest.py's per-session temp DB setup) must not crash and
    must not fabricate a per-project recommendation that doesn't exist.
    Sprint C6: a workspace-wide item (e.g. "Rescan the Workspace" from the
    Operational Intelligence Engine's `rule_discovery_scan_stale`) is
    honest, real evidence and may legitimately appear in Today's Focus even
    with zero tracked projects -- that is not a fabricated project
    recommendation, so it's explicitly allowed here."""
    resp = client.get("/mission-control").json()
    if resp["total_projects_tracked"] == 0:
        assert resp["primary_focus"]["available"] is False
        assert resp["primary_focus"]["best_action"]["label"]
        assert resp["portfolio"] == []
        assert all(item["project"] is None for item in resp["todays_focus"])


def test_primary_focus_uses_canonical_project_context_and_reasons(tmp_path):
    item = _make_and_adopt(tmp_path, "1", name="primary-app")
    root = tmp_path / "mc-scan-root-1"
    _write(root / "primary-app" / "NEXT_ACTION.md", "Ship the thing\n")
    client.post("/workspace/rescan", json={"root": str(root)})

    body = client.get("/mission-control").json()
    focus = body["primary_focus"]
    if focus["available"]:
        ctx = focus["project_context"]
        assert ctx["item_id"] is not None
        assert "resume_state" in ctx and "available" in ctx["resume_state"]
        assert isinstance(focus["reasons"], list) and focus["reasons"]
        # Snapshot Continuity must report on the same project the Primary
        # Focus card recommends -- never a second, independently-ranked one.
        sc = body["snapshot_continuity"]
        if sc["available"]:
            assert sc["canonical_project_id"] == ctx["id"]
    del item  # only used to trigger adoption


def test_needs_attention_sorted_by_severity(tmp_path):
    _make_and_adopt(tmp_path, "2", name="attn-app")
    body = client.get("/mission-control").json()
    order = {"critical": 0, "warning": 1, "info": 2}
    severities = [order[i["severity"]] for i in body["needs_attention"]]
    assert severities == sorted(severities)


def test_needs_attention_items_carry_evidence(tmp_path):
    _make_and_adopt(tmp_path, "3", name="evidence-app")
    body = client.get("/mission-control").json()
    for item in body["needs_attention"]:
        assert item["reason"]
        assert isinstance(item["evidence"], list)
        assert item["suggested_action"]


def test_portfolio_only_lists_adopted_projects_no_duplicates(tmp_path):
    _make_and_adopt(tmp_path, "4", name="portfolio-app")
    body = client.get("/mission-control").json()
    item_ids = [p["item_id"] for p in body["portfolio"] if p["item_id"]]
    assert len(item_ids) == len(set(item_ids))
    assert all(p["display_name"] for p in body["portfolio"])


def test_since_last_time_falls_back_to_a_labeled_window_when_no_session(tmp_path, monkeypatch):
    """The session DB is shared across this whole pytest run (see
    conftest.py's per-run temp DB setup), so other test modules may well
    have already started/completed sessions in it by the time this test
    runs -- a real "no session yet" fallback can only be proven against a
    genuinely empty session DB, constructed here rather than assumed."""
    monkeypatch.setenv("ROLE_OS_SESSION_DB_PATH", str(tmp_path / "empty_session.db"))
    from app.config import Settings

    body = build_mission_control(settings=Settings())
    since = body["since_last_time"]
    assert "baseline" in since and "label" in since and "events" in since
    assert since["baseline_is_fallback"] is True
    assert "24 hours" in since["label"]


def test_since_last_time_excludes_noise_filesystem_events(tmp_path):
    _make_and_adopt(tmp_path, "5", name="noise-app")
    body = client.get("/mission-control").json()
    assert all(e["type"] != "filesystem_modified" for e in body["since_last_time"]["events"])


def test_daily_session_absent_state_offers_start_my_day():
    body = client.get("/mission-control").json()
    daily = body["daily_session"]
    if not daily["has_active_session"]:
        assert daily["action"]["label"] == "Start My Day"


def test_daily_session_present_state_reflects_active_session(tmp_path):
    _make_and_adopt(tmp_path, "6", name="session-app")
    started = client.post(
        "/session/start",
        json={
            "date": "2026-01-01",
            "project_name": "session-app",
            "mode": "build",
            "objective": "Ship the feature",
            "expected_result": "Feature shipped",
        },
    ).json()
    body = client.get("/mission-control").json()
    daily = body["daily_session"]
    assert daily["has_active_session"] is True
    assert daily["session"]["id"] == started["id"]
    assert daily["action"]["label"] == "End My Day"
    client.post(f"/session/{started['id']}/complete", json={"completed_work": "done"})


def test_value_signal_is_honest_when_no_launch_ready_project():
    body = client.get("/mission-control").json()
    signal = body["value_signal"]
    if not signal["available"]:
        assert "insufficient evidence" in signal["message"].lower()


def test_snapshot_continuity_prompts_for_a_snapshot_when_none_exists(tmp_path):
    _make_and_adopt(tmp_path, "7", name="snap-app")
    root = tmp_path / "mc-scan-root-7"
    _write(root / "snap-app" / "NEXT_ACTION.md", "Do the thing\n")
    client.post("/workspace/rescan", json={"root": str(root)})

    body = client.get("/mission-control").json()
    focus = body["primary_focus"]
    if focus["available"] and not focus["project_context"].get("latest_snapshot"):
        sc = body["snapshot_continuity"]
        if sc["available"]:
            assert sc["has_snapshot"] is False
            assert "snapshot" in sc["message"].lower()


def test_recent_activity_is_deduplicated(tmp_path):
    _make_and_adopt(tmp_path, "8", name="dedup-app")
    body = client.get("/mission-control").json()
    keys = [(e["type"], e["timestamp"], e["project_id"]) for e in body["recent_activity"]]
    assert len(keys) == len(set(keys))


def test_no_double_asset_walk_per_project_per_request(tmp_path, monkeypatch):
    """Sprint C5 §12 regression: without `request_scope()`, one adopted
    project's filesystem gets walked by `index_project_assets` at least
    three times in a single Mission Control build --
    `all_project_contexts` (via `ProjectContext.assets_count`),
    `get_home_portfolio` (via `list_project_assets`), and
    `list_activity_feed` (via `list_project_assets` again, called twice --
    once for the general feed, once for Since Last Time's wider window).
    `assets_db.list_overrides` is the one call inside `index_project_assets`
    that only runs on an actual walk, never on a `request_scope()` cache
    hit, so counting it across one `build_mission_control()` call proves
    the fix: exactly one walk for this one adopted project, not four."""
    _make_and_adopt(tmp_path, "9", name="perf-app-a")

    from app.assets import service as assets_service

    calls = []
    original = assets_service.assets_db.list_overrides

    def counting_list_overrides(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(assets_service.assets_db, "list_overrides", counting_list_overrides)

    build_mission_control()

    assert len(calls) == 1
