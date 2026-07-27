"""Integration tests for the Knowledge Extraction API (/extraction/*),
Sprint 4: run/re-run extraction, list/filter objects, delete, metrics.

Uses the shared TestClient/app instance (same pattern as
test_explorer_api.py) against the isolated temp imports/extraction DBs set
up in conftest.py.
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
                "title": f"API extraction test {conv_id}",
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


# ---------------------------------------------------------------------------
# Run / re-run extraction
# ---------------------------------------------------------------------------


def test_run_extraction_returns_structured_summary():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    resp = client.post(f"/extraction/conversations/{conv_id}/run")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["conversation_id"] == conv_id
    assert body["total_found"] >= 1
    assert body["counts_by_type"].get("Decision") == 1


def test_run_extraction_unknown_conversation_404():
    resp = client.post("/extraction/conversations/does-not-exist/run")
    assert resp.status_code == 404


def test_rerun_extraction_reports_unchanged_not_duplicated():
    conv_id = import_conversation("Todavia esta pendiente revisar el presupuesto.")
    first = client.post(f"/extraction/conversations/{conv_id}/run").json()
    second = client.post(f"/extraction/conversations/{conv_id}/run").json()

    assert first["created"] >= 1
    assert second["created"] == 0
    assert second["unchanged"] == first["total_found"]

    objects = client.get(f"/extraction/conversations/{conv_id}/objects").json()
    assert len(objects) == first["total_found"]


# ---------------------------------------------------------------------------
# List / filter extracted objects
# ---------------------------------------------------------------------------


def test_list_objects_for_conversation():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    client.post(f"/extraction/conversations/{conv_id}/run")

    resp = client.get(f"/extraction/conversations/{conv_id}/objects")
    assert resp.status_code == 200
    objects = resp.json()
    assert len(objects) == 1
    assert objects[0]["object_type"] == "Decision"
    assert objects[0]["conversation_id"] == conv_id


def test_list_objects_filtered_by_type():
    conv_id = import_conversation(
        "Decidimos usar Claude para el pipeline. Aprobado por todos.\nMaria Gonzalez confirmo."
    )
    client.post(f"/extraction/conversations/{conv_id}/run")

    decisions = client.get(f"/extraction/conversations/{conv_id}/objects?object_type=Decision").json()
    assert all(o["object_type"] == "Decision" for o in decisions)
    assert len(decisions) >= 1


def test_list_objects_rejects_unsupported_type():
    conv_id = import_conversation("hello")
    resp = client.get(f"/extraction/conversations/{conv_id}/objects?object_type=NotAType")
    assert resp.status_code == 400


def test_list_objects_empty_before_extraction_runs():
    conv_id = import_conversation("hello, nothing extracted yet")
    resp = client.get(f"/extraction/conversations/{conv_id}/objects")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_object_then_404():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    client.post(f"/extraction/conversations/{conv_id}/run")
    object_id = client.get(f"/extraction/conversations/{conv_id}/objects").json()[0]["id"]

    resp = client.delete(f"/extraction/objects/{object_id}")
    assert resp.status_code == 204

    resp = client.delete(f"/extraction/objects/{object_id}")
    assert resp.status_code == 404


def test_deleted_object_does_not_reappear_without_rerun():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    client.post(f"/extraction/conversations/{conv_id}/run")
    object_id = client.get(f"/extraction/conversations/{conv_id}/objects").json()[0]["id"]
    client.delete(f"/extraction/objects/{object_id}")

    assert client.get(f"/extraction/conversations/{conv_id}/objects").json() == []


def test_deleted_object_recreated_on_rerun():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    client.post(f"/extraction/conversations/{conv_id}/run")
    object_id = client.get(f"/extraction/conversations/{conv_id}/objects").json()[0]["id"]
    client.delete(f"/extraction/objects/{object_id}")

    rerun = client.post(f"/extraction/conversations/{conv_id}/run").json()
    assert rerun["created"] == 1
    assert len(client.get(f"/extraction/conversations/{conv_id}/objects").json()) == 1


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_extraction_metrics_reflects_persisted_objects():
    before = client.get("/extraction/metrics").json()["decision"]
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    client.post(f"/extraction/conversations/{conv_id}/run")
    after = client.get("/extraction/metrics").json()["decision"]
    assert after == before + 1


def test_import_metrics_includes_extraction_counts():
    conv_id = import_conversation("Maria Gonzalez confirmo la decision. Decidimos usar Claude.")
    client.post(f"/extraction/conversations/{conv_id}/run")

    resp = client.get("/import/metrics")
    assert resp.status_code == 200
    body = resp.json()
    for field in ("knowledge_objects", "projects", "people", "tasks", "decisions", "ideas", "documents", "assets"):
        assert field in body


# ---------------------------------------------------------------------------
# Zero regressions
# ---------------------------------------------------------------------------


def test_existing_import_and_explorer_endpoints_still_work():
    assert client.get("/health").status_code == 200
    assert client.get("/import/history").status_code == 200
    assert client.get("/import/conversations").status_code == 200
    assert client.get("/import/facets").status_code == 200
