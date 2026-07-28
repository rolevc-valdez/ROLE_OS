"""Integration tests for the Knowledge Graph API (/conversation-graph/*),
Sprint 5: full graph, filters, node detail, connected nodes, and dashboard
metrics. Uses the shared TestClient/app instance (same pattern as
test_extraction_api.py) against the isolated temp DBs set up in
conftest.py.
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
                "title": f"Graph API test {conv_id}",
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
# Full graph / structured response shape
# ---------------------------------------------------------------------------


def test_get_graph_returns_structured_response():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    extract(conv_id)

    resp = client.get("/conversation-graph")
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body and "edges" in body and "metrics" in body
    assert body["metrics"]["nodes"] == len(body["nodes"])
    assert body["metrics"]["edges"] == len(body["edges"])

    conv_node = next(n for n in body["nodes"] if n["id"] == f"conversation:{conv_id}")
    assert conv_node["type"] == "conversation"
    decision_node = next(n for n in body["nodes"] if n["type"] == "decision" and n["data"]["conversation_id"] == conv_id)
    edge = next(e for e in body["edges"] if e["source"] == conv_node["id"] and e["target"] == decision_node["id"])
    assert edge["type"] == "contains"


def test_get_graph_empty_when_nothing_imported_yet():
    # Uses the /extraction/metrics-style "before" pattern: just assert the
    # shape is valid even if other tests in this session have added data --
    # true zero-state emptiness is covered at the engine level
    # (test_conversation_graph_engine.py::test_build_graph_is_empty_for_fresh_databases).
    resp = client.get("/conversation-graph")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["nodes"], list)
    assert isinstance(body["edges"], list)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_filter_by_conversation_id_returns_only_that_conversations_subgraph():
    conv_a = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    conv_b = import_conversation("Se me ocurre una idea: podriamos automatizar todo.")
    extract(conv_a)
    extract(conv_b)

    resp = client.get(f"/conversation-graph?conversation_id={conv_a}")
    body = resp.json()
    node_ids = {n["id"] for n in body["nodes"]}
    assert f"conversation:{conv_a}" in node_ids
    assert f"conversation:{conv_b}" not in node_ids
    assert all(n["type"] == "conversation" or n["data"].get("conversation_id") == conv_a for n in body["nodes"])


def test_filter_by_unknown_conversation_id_returns_empty():
    resp = client.get("/conversation-graph?conversation_id=does-not-exist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"] == []
    assert body["edges"] == []


def test_filter_by_node_type_returns_only_that_type():
    conv_id = import_conversation("Maria Gonzalez confirmo. Decidimos usar Claude para el pipeline.")
    extract(conv_id)

    resp = client.get("/conversation-graph?node_type=person")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"]
    assert all(n["type"] == "person" for n in body["nodes"])
    # filtering to one type drops every conversation->object edge, since
    # the conversation endpoint is no longer in the filtered node set.
    assert body["edges"] == []


def test_filter_by_unsupported_node_type_400():
    resp = client.get("/conversation-graph?node_type=not-a-type")
    assert resp.status_code == 400


def test_combined_filters_conversation_and_node_type():
    conv_id = import_conversation("Decidimos usar Claude. Maria Gonzalez confirmo.")
    extract(conv_id)

    resp = client.get(f"/conversation-graph?conversation_id={conv_id}&node_type=decision")
    body = resp.json()
    assert all(n["type"] == "decision" for n in body["nodes"])
    assert body["nodes"]


# ---------------------------------------------------------------------------
# Node detail / connected nodes
# ---------------------------------------------------------------------------


def test_node_detail_for_conversation():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    extract(conv_id)

    resp = client.get(f"/conversation-graph/nodes/conversation:{conv_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["node"]["type"] == "conversation"
    assert len(body["edges"]) == 1


def test_node_detail_404_for_unknown_node():
    resp = client.get("/conversation-graph/nodes/conversation:does-not-exist")
    assert resp.status_code == 404


def test_connected_nodes_for_conversation():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    extract(conv_id)

    resp = client.get(f"/conversation-graph/nodes/conversation:{conv_id}/neighbors")
    assert resp.status_code == 200
    neighbors = resp.json()
    assert len(neighbors) == 1
    assert neighbors[0]["node"]["type"] == "decision"
    assert neighbors[0]["edge"]["type"] == "contains"


def test_connected_nodes_404_for_unknown_node():
    resp = client.get("/conversation-graph/nodes/conversation:does-not-exist/neighbors")
    assert resp.status_code == 404


def test_connected_nodes_from_object_points_back_to_conversation():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    extract(conv_id)
    objects = client.get(f"/extraction/conversations/{conv_id}/objects").json()
    decision_id = objects[0]["id"]

    resp = client.get(f"/conversation-graph/nodes/decision:{decision_id}/neighbors")
    assert resp.status_code == 200
    neighbors = resp.json()
    assert len(neighbors) == 1
    assert neighbors[0]["node"]["id"] == f"conversation:{conv_id}"


# ---------------------------------------------------------------------------
# Dashboard metrics (graph node/edge counts)
# ---------------------------------------------------------------------------


def test_import_metrics_reports_real_graph_counts():
    before = client.get("/import/metrics").json()
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    extract(conv_id)
    after = client.get("/import/metrics").json()

    assert after["graph_nodes"] > before["graph_nodes"]
    assert after["graph_edges"] > before["graph_edges"]


def test_graph_metrics_match_direct_graph_endpoint():
    conv_id = import_conversation("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    extract(conv_id)

    graph_body = client.get("/conversation-graph").json()
    metrics_body = client.get("/import/metrics").json()
    assert metrics_body["graph_nodes"] == graph_body["metrics"]["nodes"]
    assert metrics_body["graph_edges"] == graph_body["metrics"]["edges"]


# ---------------------------------------------------------------------------
# Zero regressions
# ---------------------------------------------------------------------------


def test_existing_endpoints_still_work():
    assert client.get("/health").status_code == 200
    assert client.get("/import/history").status_code == 200
    assert client.get("/extraction/metrics").status_code == 200
    assert client.get("/graph/meta/types").status_code == 200
