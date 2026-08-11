"""Integration tests for the AI Launcher API (/launcher/start).

Uses the shared TestClient/app instance (same pattern as
test_session_api.py). Requires an active session, so an autouse fixture
starts one before each test and force-closes any lingering active
session afterward, so tests never interfere with each other.
"""

from __future__ import annotations

import uuid

import pytest
from app.config import get_settings
from app.main import app
from app.session import db as session_db
from fastapi.testclient import TestClient

client = TestClient(app)


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(autouse=True)
def _close_any_lingering_active_session():
    yield
    settings = get_settings()
    active = session_db.get_active_session(settings)
    if active:
        session_db.complete_session(
            active["id"],
            completed_work="(auto-closed by test teardown)",
            decisions="",
            blockers="",
            next_step="",
            settings=settings,
        )


def start_session(**overrides) -> dict:
    payload = {
        "date": "2026-07-30",
        "project_id": "role-os",
        "project_name": "ROLE OS",
        "mode": "BUILD",
        "objective": unique("Objective"),
        "expected_result": "A working AI Launcher",
    }
    payload.update(overrides)
    resp = client.post("/session/start", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_launch_requires_active_session():
    resp = client.post("/launcher/start", json={"tool": "claude"})
    assert resp.status_code == 409


def test_launch_claude():
    start_session()
    resp = client.post("/launcher/start", json={"tool": "claude"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tool"] == "claude"
    assert body["urls"] == ["https://claude.ai"]
    assert body["prompt"].startswith("Initialize using SYSTEM.md.")


def test_launch_chatgpt():
    start_session()
    resp = client.post("/launcher/start", json={"tool": "chatgpt"})
    assert resp.status_code == 200
    assert resp.json()["urls"] == ["https://chatgpt.com"]


def test_launch_both():
    start_session()
    resp = client.post("/launcher/start", json={"tool": "both"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["urls"]) == {"https://claude.ai", "https://chatgpt.com"}


def test_launch_unknown_tool_returns_422():
    start_session()
    resp = client.post("/launcher/start", json={"tool": "bing"})
    assert resp.status_code == 422


def test_launch_prompt_includes_active_project_and_objective():
    session = start_session(project_name="ROLE Commerce Factory", mode="LAUNCH")
    resp = client.post("/launcher/start", json={"tool": "claude"})
    prompt = resp.json()["prompt"]
    assert "Project:\nROLE Commerce Factory" in prompt
    assert "Mode:\nLAUNCH" in prompt
    assert f"Today's Objective:\n{session['objective']}" in prompt


def test_launch_prompt_includes_recent_decisions_section():
    start_session()
    resp = client.post("/launcher/start", json={"tool": "claude"})
    assert "Recent Decisions:" in resp.json()["prompt"]


def test_launch_session_id_matches_active_session():
    session = start_session()
    resp = client.post("/launcher/start", json={"tool": "claude"})
    assert resp.json()["session_id"] == session["id"]


def test_launcher_does_not_affect_session_status():
    """The launcher only reads the active session -- it must not
    complete, modify, or otherwise mutate it."""
    session = start_session()
    client.post("/launcher/start", json={"tool": "both"})
    current = client.get("/session/current").json()
    assert current["id"] == session["id"]
    assert current["status"] == "active"
