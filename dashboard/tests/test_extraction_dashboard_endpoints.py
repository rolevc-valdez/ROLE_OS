"""Tests for the two Extraction endpoints added for the Dashboard
(Sprint 7): GET /extraction/recent and GET /extraction/runs. Both are
thin, additive wrappers around already-tested queries -- these tests
focus on the wrapper's own behavior (ordering, limit, empty state), not
re-testing extraction/search from scratch (see test_extraction_api.py /
test_advisor_search_api.py for that).
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def unique_id() -> str:
    return f"conv-{uuid.uuid4().hex[:8]}"


def import_conversation(text: str, conv_id: str | None = None) -> str:
    conv_id = conv_id or unique_id()
    payload = json.dumps(
        [
            {
                "id": conv_id,
                "title": f"Dashboard endpoint test {conv_id}",
                "create_time": 1700000000,
                "update_time": 1700003600,
                "mapping": {
                    "n1": {
                        "message": {
                            "author": {"role": "user"},
                            "create_time": 1700000000,
                            "content": {"parts": [text]},
                        }
                    }
                },
            }
        ]
    ).encode("utf-8")
    resp = client.post("/import/chatgpt", files={"file": ("export.json", payload, "application/json")})
    assert resp.status_code == 201, resp.text
    items = client.get(f"/import/conversations?q={conv_id}").json()["items"]
    return items[0]["id"]


def extract(conv_id: str) -> dict:
    resp = client.post(f"/extraction/conversations/{conv_id}/run")
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# GET /extraction/recent
# ---------------------------------------------------------------------------


def test_recent_objects_returns_newest_first():
    tag = unique_id()
    conv_id = import_conversation(f"Decidimos usar {tag}. Aprobado por todos.")
    extract(conv_id)

    resp = client.get("/extraction/recent?limit=5")
    assert resp.status_code == 200
    items = resp.json()
    assert items
    dates = [i["created_at"] for i in items]
    assert dates == sorted(dates, reverse=True)


def test_recent_objects_respects_limit():
    resp = client.get("/extraction/recent?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


def test_recent_objects_includes_newly_extracted():
    tag = unique_id()
    conv_id = import_conversation(f"Se me ocurre una idea sobre {tag}.")
    extract(conv_id)

    resp = client.get("/extraction/recent?limit=50")
    titles = [i["title"] for i in resp.json()]
    assert any(tag in t for t in titles)


# ---------------------------------------------------------------------------
# GET /extraction/runs
# ---------------------------------------------------------------------------


def test_extraction_runs_returns_newest_first():
    tag = unique_id()
    conv_id = import_conversation(f"Decidimos usar {tag}. Aprobado por todos.")
    extract(conv_id)

    resp = client.get("/extraction/runs?limit=10")
    assert resp.status_code == 200
    runs = resp.json()
    assert runs
    dates = [r["completed_at"] for r in runs]
    assert dates == sorted(dates, reverse=True)


def test_extraction_runs_most_recent_matches_latest_call():
    tag = unique_id()
    conv_id = import_conversation(f"Decidimos usar {tag}. Aprobado por todos.")
    run = extract(conv_id)

    resp = client.get("/extraction/runs?limit=1")
    assert resp.status_code == 200
    latest = resp.json()[0]
    assert latest["id"] == run["id"]
    assert latest["conversation_id"] == conv_id


def test_extraction_runs_respects_limit():
    resp = client.get("/extraction/runs?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


# ---------------------------------------------------------------------------
# Zero regressions
# ---------------------------------------------------------------------------


def test_existing_extraction_endpoints_unaffected():
    assert client.get("/extraction/metrics").status_code == 200
    assert client.get("/health").status_code == 200
