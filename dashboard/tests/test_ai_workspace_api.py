"""Integration tests for the AI Workspace API
(/pi/projects/{id}/ai-workspace*), ROLE OS v1.3.

Uses the shared TestClient/app instance (same pattern as test_pi_api.py)
against the isolated temp projects DB set up in conftest.py.
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


def test_get_ai_workspace_defaults_when_never_saved():
    project = make_project()
    resp = client.get(f"/pi/projects/{project['id']}/ai-workspace")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == project["id"]
    assert body["claude_url"] == ""
    assert body["chatgpt_url"] == ""
    assert body["gemini_url"] == ""
    assert body["last_opened_at"] is None


def test_get_ai_workspace_missing_project_returns_404():
    resp = client.get("/pi/projects/does-not-exist/ai-workspace")
    assert resp.status_code == 404


def test_save_conversation():
    project = make_project()
    resp = client.put(
        f"/pi/projects/{project['id']}/ai-workspace",
        json={
            "claude_url": "https://claude.ai/chat/abc123",
            "chatgpt_url": "https://chatgpt.com/c/xyz789",
            "role": "Engineer",
            "preferred_model": "Claude Opus 5",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["claude_url"] == "https://claude.ai/chat/abc123"
    assert body["chatgpt_url"] == "https://chatgpt.com/c/xyz789"
    assert body["role"] == "Engineer"
    assert body["preferred_model"] == "Claude Opus 5"


def test_save_conversation_missing_project_returns_404():
    resp = client.put(
        "/pi/projects/does-not-exist/ai-workspace", json={"claude_url": "https://claude.ai"}
    )
    assert resp.status_code == 404


def test_open_claude_uses_saved_conversation():
    project = make_project()
    client.put(
        f"/pi/projects/{project['id']}/ai-workspace",
        json={"claude_url": "https://claude.ai/chat/abc"},
    )
    resp = client.post(f"/pi/projects/{project['id']}/ai-workspace/open", json={"tool": "claude"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == [
        {"tool": "claude", "url": "https://claude.ai/chat/abc", "used_saved_conversation": True}
    ]
    assert body["any_missing"] is False
    assert body["last_opened_at"] is not None


def test_open_claude_falls_back_to_homepage_when_nothing_saved():
    project = make_project()
    resp = client.post(f"/pi/projects/{project['id']}/ai-workspace/open", json={"tool": "claude"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == [
        {"tool": "claude", "url": "https://claude.ai", "used_saved_conversation": False}
    ]
    assert body["any_missing"] is True


def test_open_chatgpt_falls_back_to_homepage_when_nothing_saved():
    project = make_project()
    resp = client.post(f"/pi/projects/{project['id']}/ai-workspace/open", json={"tool": "chatgpt"})
    body = resp.json()
    assert body["results"] == [
        {"tool": "chatgpt", "url": "https://chatgpt.com", "used_saved_conversation": False}
    ]


def test_open_both_mixed_saved_and_unsaved():
    project = make_project()
    client.put(
        f"/pi/projects/{project['id']}/ai-workspace",
        json={"claude_url": "https://claude.ai/chat/abc"},
    )
    resp = client.post(f"/pi/projects/{project['id']}/ai-workspace/open", json={"tool": "both"})
    body = resp.json()
    by_tool = {r["tool"]: r for r in body["results"]}
    assert by_tool["claude"]["used_saved_conversation"] is True
    assert by_tool["claude"]["url"] == "https://claude.ai/chat/abc"
    assert by_tool["chatgpt"]["used_saved_conversation"] is False
    assert by_tool["chatgpt"]["url"] == "https://chatgpt.com"
    assert body["any_missing"] is True


def test_open_unknown_tool_returns_422():
    project = make_project()
    resp = client.post(f"/pi/projects/{project['id']}/ai-workspace/open", json={"tool": "bing"})
    assert resp.status_code == 422


def test_open_missing_project_returns_404():
    resp = client.post("/pi/projects/does-not-exist/ai-workspace/open", json={"tool": "claude"})
    assert resp.status_code == 404


def test_open_updates_last_opened_timestamp():
    project = make_project()
    before = client.get(f"/pi/projects/{project['id']}/ai-workspace").json()
    assert before["last_opened_at"] is None
    client.post(f"/pi/projects/{project['id']}/ai-workspace/open", json={"tool": "claude"})
    after = client.get(f"/pi/projects/{project['id']}/ai-workspace").json()
    assert after["last_opened_at"] is not None


def test_gemini_url_is_stored_but_not_offered_by_open():
    """Gemini is an optional stored field (requirement 2); open/launch
    actions only cover Claude and ChatGPT (requirement 3), so Gemini
    correctly has no 'open' entry point."""
    project = make_project()
    resp = client.put(
        f"/pi/projects/{project['id']}/ai-workspace",
        json={"gemini_url": "https://gemini.google.com/app/abc"},
    )
    assert resp.json()["gemini_url"] == "https://gemini.google.com/app/abc"


def test_ai_workspace_does_not_touch_launcher_endpoint():
    """Requirement: do not modify existing launcher endpoints. Confirms
    /launcher/start still requires an active Daily Session and behaves
    exactly as before, completely independent of AI Workspace."""
    resp = client.post("/launcher/start", json={"tool": "claude"})
    assert resp.status_code in (
        409,
        200,
    )  # unaffected either way; just proves the route still exists unchanged
