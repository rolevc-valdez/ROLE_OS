"""Integration tests for the Advisor API (/advisor/*), Epic 2.

Uses the shared TestClient/app instance (same as test_pi_api.py) so this
exercises the real dependency-injected settings and the isolated temp
advisor/projects DBs set up in conftest.py.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

client = TestClient(app)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def make_project(**overrides) -> dict:
    payload = {"name": unique("AdvisorProject"), "workspace": "Products", "description": "desc"}
    payload.update(overrides)
    resp = client.post("/pi/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_stale_project(**overrides) -> dict:
    project = make_project(**overrides)
    settings = get_settings()
    stale_iso = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    conn = sqlite3.connect(str(settings.projects_db_path))
    conn.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (stale_iso, project["id"]))
    conn.commit()
    conn.close()
    return project


def test_list_recommendations_returns_generated_findings():
    project = make_stale_project()
    resp = client.get("/advisor/recommendations", params={"project_id": project["id"]})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["recommendation_type"] == "update_stale_project"
    assert "dedupe_key" not in body[0]


def test_get_recommendation_by_id():
    project = make_stale_project()
    listed = client.get("/advisor/recommendations", params={"project_id": project["id"]}).json()
    rec_id = listed[0]["id"]

    resp = client.get(f"/advisor/recommendations/{rec_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == rec_id


def test_get_recommendation_404_when_missing():
    assert client.get("/advisor/recommendations/does-not-exist").status_code == 404


def test_filter_by_workspace():
    project = make_stale_project(workspace=unique("Workspace"))
    resp = client.get("/advisor/recommendations", params={"workspace": project["workspace"]})
    assert resp.status_code == 200
    assert all(r["workspace"] == project["workspace"] for r in resp.json())
    assert any(r["project_id"] == project["id"] for r in resp.json())


def test_filter_by_recommendation_type():
    project = make_stale_project()
    resp = client.get(
        "/advisor/recommendations",
        params={"project_id": project["id"], "recommendation_type": "update_stale_project"},
    )
    assert resp.status_code == 200
    assert all(r["recommendation_type"] == "update_stale_project" for r in resp.json())

    resp_empty = client.get(
        "/advisor/recommendations",
        params={"project_id": project["id"], "recommendation_type": "reuse_capability"},
    )
    assert resp_empty.json() == []


def test_filter_by_minimum_priority_score():
    project = make_stale_project()
    baseline = client.get("/advisor/recommendations", params={"project_id": project["id"]}).json()
    assert len(baseline) == 1
    score = baseline[0]["priority_score"]

    at_score = client.get(
        "/advisor/recommendations", params={"project_id": project["id"], "minimum_priority_score": score}
    )
    assert at_score.status_code == 200
    assert len(at_score.json()) == 1

    above_score = client.get(
        "/advisor/recommendations",
        params={"project_id": project["id"], "minimum_priority_score": min(score + 1, 100)},
    )
    assert above_score.status_code == 200
    assert above_score.json() == []


def test_dismiss_then_include_dismissed_filter():
    project = make_stale_project()
    rec_id = client.get("/advisor/recommendations", params={"project_id": project["id"]}).json()[0]["id"]

    resp = client.post(f"/advisor/recommendations/{rec_id}/dismiss")
    assert resp.status_code == 200
    assert resp.json()["dismissed"] is True

    hidden = client.get("/advisor/recommendations", params={"project_id": project["id"]}).json()
    assert hidden == []

    shown = client.get(
        "/advisor/recommendations", params={"project_id": project["id"], "include_dismissed": True}
    ).json()
    assert len(shown) == 1
    assert shown[0]["dismissed"] is True


def test_dismiss_404_when_missing():
    assert client.post("/advisor/recommendations/does-not-exist/dismiss").status_code == 404


def test_complete_recommendation():
    project = make_stale_project()
    rec_id = client.get("/advisor/recommendations", params={"project_id": project["id"]}).json()[0]["id"]

    resp = client.post(f"/advisor/recommendations/{rec_id}/complete")
    assert resp.status_code == 200
    assert resp.json()["completed"] is True


def test_complete_404_when_missing():
    assert client.post("/advisor/recommendations/does-not-exist/complete").status_code == 404


def test_daily_brief_endpoint():
    make_stale_project(priority="high")
    resp = client.get("/advisor/daily-brief")
    assert resp.status_code == 200
    body = resp.json()
    assert "Good morning" in body["greeting"]
    assert isinstance(body["top_recommended_projects"], list)
    assert isinstance(body["critical_risks"], list)
    assert isinstance(body["blocked_projects"], list)
    assert isinstance(body["near_completion"], list)
    assert isinstance(body["stale_high_priority"], list)
    assert isinstance(body["capability_opportunities"], list)


def test_daily_brief_workspace_filter():
    project = make_stale_project(workspace=unique("Workspace"))
    resp = client.get("/advisor/daily-brief", params={"workspace": project["workspace"]})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Regression: every previous API and UI surface must be completely unaffected
# ---------------------------------------------------------------------------


def test_all_previous_endpoints_still_work():
    # Milestone 1
    assert client.get("/health").status_code == 200
    assert client.get("/projects").status_code == 200
    assert client.get("/search", params={"q": "Master"}).status_code == 200
    assert client.get("/knowledge/conv-1").status_code == 200
    assert client.get("/knowledge/does-not-exist").status_code == 404

    # Milestone 2 UI
    assert client.get("/").status_code == 200
    assert client.get("/ui/recent").status_code == 200
    assert client.get("/ui/timeline").status_code == 200

    # Epic 1 Project Intelligence
    assert client.get("/pi/workspaces").status_code == 200
    assert client.get("/pi/projects").status_code == 200


def test_dashboard_page_includes_advisor_tab():
    """Epic 4 redesigned the page into a Command Center shell with a
    persistent sidebar (no more tab bar) and client-side hash routing --
    the Advisor is now a sidebar nav item + a dedicated `#/advisor` page
    rendered by app.js, rather than a `data-tab="advisor"` panel."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert 'data-nav="advisor"' in body
