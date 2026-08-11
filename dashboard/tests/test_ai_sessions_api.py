"""Integration tests for the AI Sessions API
(/pi/projects/{id}/ai-sessions*, /pi/projects/{id}/timeline), ROLE OS
v1.4 "Context Engine".

Uses the shared TestClient/app instance (same pattern as
test_pi_api.py / test_ai_workspace_api.py) against the isolated temp
projects DB set up in conftest.py.
"""

from __future__ import annotations

import uuid

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def make_project(**overrides) -> dict:
    payload = {"name": unique("Project"), "workspace": "Products", "description": "desc"}
    payload.update(overrides)
    resp = client.post("/pi/projects", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_session(project_id: str, **overrides) -> dict:
    payload = {"assistant": "claude", "title": unique("Session")}
    payload.update(overrides)
    resp = client.post(f"/pi/projects/{project_id}/ai-sessions", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Create / list / get
# ---------------------------------------------------------------------------


def test_create_session():
    project = make_project()
    resp = client.post(
        f"/pi/projects/{project['id']}/ai-sessions",
        json={"assistant": "claude", "title": "Design v1.4", "role": "Architect"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["assistant"] == "claude"
    assert body["title"] == "Design v1.4"
    assert body["role"] == "Architect"
    assert body["status"] == "active"
    assert body["favorite"] is False
    assert body["current"] is False


def test_create_session_missing_project_returns_404():
    resp = client.post("/pi/projects/does-not-exist/ai-sessions", json={"assistant": "claude"})
    assert resp.status_code == 404


def test_create_session_invalid_assistant_returns_422():
    project = make_project()
    resp = client.post(f"/pi/projects/{project['id']}/ai-sessions", json={"assistant": "bing"})
    assert resp.status_code == 422


def test_multiple_sessions_per_assistant():
    project = make_project()
    make_session(project["id"], assistant="claude", title="First")
    make_session(project["id"], assistant="claude", title="Second")
    sessions = client.get(f"/pi/projects/{project['id']}/ai-sessions").json()
    assert len(sessions) == 2


def test_list_sessions_filter_by_assistant():
    project = make_project()
    make_session(project["id"], assistant="claude")
    make_session(project["id"], assistant="chatgpt")
    resp = client.get(f"/pi/projects/{project['id']}/ai-sessions", params={"assistant": "claude"})
    assert len(resp.json()) == 1
    assert resp.json()[0]["assistant"] == "claude"


def test_get_session():
    project = make_project()
    session = make_session(project["id"])
    resp = client.get(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == session["id"]


def test_get_session_wrong_project_returns_404():
    project1 = make_project()
    project2 = make_project()
    session = make_session(project1["id"])
    resp = client.get(f"/pi/projects/{project2['id']}/ai-sessions/{session['id']}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update / delete
# ---------------------------------------------------------------------------


def test_update_session():
    project = make_project()
    session = make_session(project["id"])
    resp = client.patch(
        f"/pi/projects/{project['id']}/ai-sessions/{session['id']}", json={"favorite": True}
    )
    assert resp.status_code == 200
    assert resp.json()["favorite"] is True


def test_update_session_invalid_status_returns_422():
    project = make_project()
    session = make_session(project["id"])
    resp = client.patch(
        f"/pi/projects/{project['id']}/ai-sessions/{session['id']}", json={"status": "archived"}
    )
    assert resp.status_code == 422


def test_delete_session():
    project = make_project()
    session = make_session(project["id"])
    resp = client.delete(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}")
    assert resp.status_code == 204
    assert (
        client.get(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}").status_code == 404
    )


# ---------------------------------------------------------------------------
# Set current / open
# ---------------------------------------------------------------------------


def test_set_current():
    project = make_project()
    s1 = make_session(project["id"], assistant="claude")
    s2 = make_session(project["id"], assistant="claude")
    client.post(f"/pi/projects/{project['id']}/ai-sessions/{s1['id']}/set-current")
    resp = client.post(f"/pi/projects/{project['id']}/ai-sessions/{s2['id']}/set-current")
    assert resp.status_code == 200
    assert resp.json()["current"] is True
    assert (
        client.get(f"/pi/projects/{project['id']}/ai-sessions/{s1['id']}").json()["current"]
        is False
    )


def test_open_session_with_saved_url_uses_it():
    project = make_project()
    session = make_session(
        project["id"], assistant="claude", conversation_url="https://claude.ai/chat/abc"
    )
    resp = client.post(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/open")
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"] == "https://claude.ai/chat/abc"
    assert body["used_saved_conversation"] is True
    assert body["message"] is None


def test_open_session_without_saved_url_falls_back_to_homepage():
    project = make_project()
    session = make_session(project["id"], assistant="claude")
    resp = client.post(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/open")
    body = resp.json()
    assert body["url"] == "https://claude.ai"
    assert body["used_saved_conversation"] is False
    assert body["message"] == "No conversation saved yet."


def test_open_session_other_assistant_without_url_has_no_homepage():
    project = make_project()
    session = make_session(project["id"], assistant="other")
    resp = client.post(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/open")
    body = resp.json()
    assert body["url"] is None
    assert "No conversation saved yet" in body["message"]


def test_open_session_updates_last_used():
    project = make_project()
    session = make_session(project["id"])
    assert (
        client.get(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}").json()[
            "last_used_at"
        ]
        is None
    )
    client.post(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/open")
    assert (
        client.get(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}").json()[
            "last_used_at"
        ]
        is not None
    )


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


def test_create_and_list_snapshots():
    project = make_project()
    session = make_session(project["id"])
    resp = client.post(
        f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/snapshots",
        json={"accomplishments": "Did X", "next_prompt": "Do Y"},
    )
    assert resp.status_code == 201
    assert resp.json()["accomplishments"] == "Did X"

    listing = client.get(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/snapshots")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_create_snapshot_missing_session_returns_404():
    project = make_project()
    resp = client.post(
        f"/pi/projects/{project['id']}/ai-sessions/does-not-exist/snapshots", json={}
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Resume Engine
# ---------------------------------------------------------------------------


def test_resume_without_snapshot():
    project = make_project()
    session = make_session(project["id"], title="My Session")
    resp = client.get(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/resume")
    assert resp.status_code == 200
    body = resp.json()
    assert "My Session" in body["prompt"]
    assert "Where We Left Off:\nNo prior activity recorded." in body["prompt"]


def test_resume_with_snapshot_includes_next_prompt():
    project = make_project()
    session = make_session(
        project["id"], assistant="claude", conversation_url="https://claude.ai/chat/abc"
    )
    client.post(
        f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/snapshots",
        json={"next_prompt": "Write the tests now"},
    )
    resp = client.get(f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/resume")
    body = resp.json()
    assert "Write the tests now" in body["prompt"]
    assert body["url"] == "https://claude.ai/chat/abc"
    assert body["used_saved_conversation"] is True


def test_resume_missing_session_returns_404():
    project = make_project()
    resp = client.get(f"/pi/projects/{project['id']}/ai-sessions/does-not-exist/resume")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


def test_timeline_endpoint():
    project = make_project()
    session = make_session(project["id"], title="Timeline Test")
    client.post(
        f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/snapshots",
        json={"summary": "progress"},
    )
    resp = client.get(f"/pi/projects/{project['id']}/timeline")
    assert resp.status_code == 200
    types = [e["type"] for e in resp.json()]
    assert types == ["session_started", "snapshot"]


def test_timeline_missing_project_returns_404():
    resp = client.get("/pi/projects/does-not-exist/timeline")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Backward compatibility: v1.2 launcher and v1.3 AI Workspace unaffected
# ---------------------------------------------------------------------------


def test_launcher_endpoint_still_exists_unchanged():
    resp = client.post("/launcher/start", json={"tool": "claude"})
    assert resp.status_code in (409, 200)


def test_ai_workspace_endpoints_still_exist_unchanged():
    project = make_project()
    resp = client.get(f"/pi/projects/{project['id']}/ai-workspace")
    assert resp.status_code == 200
    assert resp.json()["claude_url"] == ""

    saved = client.put(
        f"/pi/projects/{project['id']}/ai-workspace",
        json={"claude_url": "https://claude.ai/chat/legacy"},
    )
    assert saved.status_code == 200
    assert saved.json()["claude_url"] == "https://claude.ai/chat/legacy"
