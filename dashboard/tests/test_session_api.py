"""Integration tests for the Daily Session API (/session/*).

Uses the shared TestClient/app instance (same pattern as test_pi_api.py)
against the isolated temp session DB set up in conftest.py. Because only
one session may be active at a time, an autouse fixture force-closes any
session left active by a previous test so tests never interfere with each
other regardless of execution order.
"""

from __future__ import annotations

import uuid

import pytest
from app.config import get_settings
from app.main import app
from app.session import db as session_db
from fastapi.testclient import TestClient

client = TestClient(app)


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


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def start_payload(**overrides) -> dict:
    payload = {
        "date": "2026-07-30",
        "project_id": "role-os",
        "project_name": "ROLE OS",
        "mode": "BUILD",
        "objective": unique("Objective"),
        "expected_result": "A working local dashboard",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def test_list_modes_returns_all_six():
    resp = client.get("/session/modes")
    assert resp.status_code == 200
    ids = {m["id"] for m in resp.json()}
    assert ids == {"PLAN", "BUILD", "CREATE", "LAUNCH", "OPERATE", "LEARN"}
    for mode in resp.json():
        assert mode["name"]
        assert mode["purpose"]
        assert mode["ai_behavior"]
        assert isinstance(mode["resources"], list) and mode["resources"]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_registry_includes_required_projects():
    resp = client.get("/session/registry")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()}
    assert {
        "ROLE OS",
        "ROLE ECOSYSTEM",
        "ROLE MASTER",
        "ROLE Commerce Factory",
        "Brand Character OS",
        "RoleValdez",
        "SUPER FACIL",
    }.issubset(names)


def test_patch_registry_project():
    resp = client.patch("/session/registry/role-master", json={"milestone": "Updated via test"})
    assert resp.status_code == 200
    assert resp.json()["milestone"] == "Updated via test"
    assert resp.json()["user_edited"] is True


def test_patch_registry_project_missing_returns_404():
    resp = client.patch("/session/registry/does-not-exist", json={"status": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sessions: lifecycle
# ---------------------------------------------------------------------------


def test_current_session_is_null_when_none_active():
    resp = client.get("/session/current")
    assert resp.status_code == 200
    assert resp.json() is None


def test_start_session_requires_fields():
    resp = client.post("/session/start", json=start_payload(objective=""))
    assert resp.status_code == 422


def test_start_session_then_it_is_current():
    started = client.post("/session/start", json=start_payload())
    assert started.status_code == 201
    body = started.json()
    assert body["status"] == "active"

    current = client.get("/session/current")
    assert current.json()["id"] == body["id"]


def test_start_session_conflict_when_already_active():
    client.post("/session/start", json=start_payload())
    second = client.post("/session/start", json=start_payload(project_name="Other"))
    assert second.status_code == 409


def test_complete_session_closes_it():
    started = client.post("/session/start", json=start_payload()).json()
    completed = client.post(
        f"/session/{started['id']}/complete",
        json={
            "completed_work": "Did the thing",
            "decisions": "d",
            "blockers": "b",
            "next_step": "n",
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert client.get("/session/current").json() is None


def test_complete_session_missing_returns_404():
    resp = client.post(
        "/session/does-not-exist/complete",
        json={"completed_work": "x", "decisions": "", "blockers": "", "next_step": ""},
    )
    assert resp.status_code == 404


def test_get_session_missing_returns_404():
    resp = client.get("/session/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Generated artifacts
# ---------------------------------------------------------------------------


def test_claude_prompt_endpoint():
    started = client.post("/session/start", json=start_payload(mode="LEARN")).json()
    resp = client.get(f"/session/{started['id']}/prompt")
    assert resp.status_code == 200
    prompt = resp.json()["prompt"]
    assert prompt.startswith("Initialize using SYSTEM.md.")
    assert "Mode:\nLEARN" in prompt


def test_markdown_endpoint():
    started = client.post("/session/start", json=start_payload()).json()
    resp = client.get(f"/session/{started['id']}/markdown")
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "2026-07-30.md"
    assert body["markdown"].startswith("# 2026-07-30")


def test_markdown_download_endpoint_sets_attachment_headers():
    started = client.post("/session/start", json=start_payload()).json()
    resp = client.get(f"/session/{started['id']}/markdown/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "attachment" in resp.headers["content-disposition"]
    assert "2026-07-30.md" in resp.headers["content-disposition"]


def test_vault_config_reports_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR", raising=False)
    get_settings.cache_clear()
    try:
        resp = client.get("/session/vault/config")
        assert resp.status_code == 200
        assert resp.json() == {"configured": False, "directory": None}
    finally:
        get_settings.cache_clear()


def test_save_to_vault_without_config_reports_not_saved():
    started = client.post("/session/start", json=start_payload()).json()
    resp = client.post(f"/session/{started['id']}/save-to-vault")
    assert resp.status_code == 200
    body = resp.json()
    assert body["saved"] is False
    assert "not configured" in body["reason"].lower()


def test_save_to_vault_writes_file_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        started = client.post("/session/start", json=start_payload()).json()
        resp = client.post(f"/session/{started['id']}/save-to-vault")
        assert resp.status_code == 200
        body = resp.json()
        assert body["saved"] is True
        written = tmp_path / "2026-07-30.md"
        assert written.exists()
        assert written.read_text(encoding="utf-8").startswith("# 2026-07-30")
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Recent ecosystem decisions
# ---------------------------------------------------------------------------


def test_recent_decisions_endpoint_shape():
    resp = client.get("/session/decisions/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] in {"ecosystem", "fallback"}
    assert isinstance(body["decisions"], list)
    assert body["note"]
