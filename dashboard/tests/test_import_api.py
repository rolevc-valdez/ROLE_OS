"""Integration tests for the ChatGPT conversation importer API (/import/*),
Sprint B1. Uses the shared TestClient/app instance (same pattern as
test_pi_api.py) against the isolated temp imports DB set up in conftest.py.
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def unique_id() -> str:
    return f"conv-{uuid.uuid4().hex[:8]}"


def conversation(conv_id: str) -> dict:
    return {
        "id": conv_id,
        "title": f"Conversation {conv_id}",
        "create_time": 1700000000,
        "update_time": 1700003600,
        "mapping": {
            "n1": {
                "message": {
                    "author": {"role": "user"},
                    "create_time": 1700000000,
                    "content": {"parts": ["Hello there"]},
                }
            },
        },
    }


def upload(conversations: list, filename: str = "export.json"):
    payload = json.dumps(conversations).encode("utf-8")
    return client.post(
        "/import/chatgpt",
        files={"file": (filename, payload, "application/json")},
    )


def test_import_chatgpt_returns_structured_summary():
    cid = unique_id()
    resp = upload([conversation(cid)])
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["total_found"] == 1
    assert body["imported"] == 1
    assert body["updated"] == 0
    assert body["skipped"] == 0
    assert body["invalid"] == 0
    assert body["errors"] == []
    assert "id" in body
    assert body["source_filename"] == "export.json"


def test_import_chatgpt_rejects_malformed_json():
    resp = client.post(
        "/import/chatgpt",
        files={"file": ("export.json", b"{not valid json", "application/json")},
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_import_chatgpt_does_not_break_existing_knowledge_endpoints():
    resp = client.get("/health")
    assert resp.status_code == 200
    resp = client.get("/projects")
    assert resp.status_code == 200


def test_import_history_lists_recent_runs():
    cid = unique_id()
    upload([conversation(cid)], filename="history-check.json")
    resp = client.get("/import/history")
    assert resp.status_code == 200
    runs = resp.json()
    assert any(r["source_filename"] == "history-check.json" for r in runs)


def test_import_conversations_lists_imported_records():
    cid = unique_id()
    upload([conversation(cid)])
    resp = client.get("/import/conversations")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body
    assert any(c["external_id"] == cid for c in body["items"])


def test_reimport_same_file_reports_skipped_not_duplicated():
    cid = unique_id()
    payload = [conversation(cid)]
    first = upload(payload, filename="dup.json")
    second = upload(payload, filename="dup.json")

    assert first.json()["imported"] == 1
    assert second.json()["imported"] == 0
    assert second.json()["skipped"] == 1
