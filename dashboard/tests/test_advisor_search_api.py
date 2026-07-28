"""Integration tests for the Advisor Search API (/advisor/search/*),
Sprint 6: search, filters, conversation/object lookup, and graph
navigation (a search result's graph_node_id must resolve on the Sprint 5
Knowledge Graph API). Also confirms zero regressions to the existing
Epic 2 Advisor endpoints, which this sprint's router leaves untouched.

Uses the shared TestClient/app instance against the isolated temp DBs set
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


def import_conversation(text: str, title: str | None = None, conv_id: str | None = None) -> str:
    conv_id = conv_id or unique_id()
    payload = json.dumps(
        [
            {
                "id": conv_id,
                "title": title or f"Advisor API test {conv_id}",
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


def extract(conv_id: str) -> None:
    resp = client.post(f"/extraction/conversations/{conv_id}/run")
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------


def test_search_returns_structured_response():
    tag = unique_id()
    conv_id = import_conversation(f"Decidimos usar {tag}. Aprobado por todos.")
    extract(conv_id)

    resp = client.get(f"/advisor/search?q={tag}")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body and "total" in body
    assert body["total"] == len(body["results"])
    assert any(r["object_type"] == "Decision" for r in body["results"])


def test_search_partial_match():
    tag = unique_id()
    conv_id = import_conversation(f"Decidimos usar {tag}suffix. Aprobado por todos.")
    extract(conv_id)

    resp = client.get(f"/advisor/search?q={tag}")
    assert resp.status_code == 200
    assert any(tag in r["name"] for r in resp.json()["results"])


def test_search_with_no_query_and_no_type_returns_all_matching_nothing_specific():
    # No special API-level restriction on an empty search -- the UI is
    # what avoids calling with neither q nor type. At the API level this
    # is just "list everything", bounded by limit.
    resp = client.get("/advisor/search?limit=5")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) <= 5


def test_search_empty_query_shows_all_of_filtered_type():
    tag = unique_id()
    conv_id = import_conversation(f"Se me ocurre una idea: {tag}.")
    extract(conv_id)

    resp = client.get("/advisor/search?type=Idea")
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"]
    assert all(r["object_type"] == "Idea" for r in body["results"])


def test_search_type_filter_conversations():
    tag = unique_id()
    conv_id = import_conversation("irrelevant", title=f"Filter test {tag}")

    resp = client.get(f"/advisor/search?q={tag}&type=Conversation")
    body = resp.json()
    assert body["results"]
    assert all(r["object_type"] == "Conversation" for r in body["results"])


def test_search_default_limit_comes_from_settings():
    """Sprint 8: an omitted `limit` now defers to Settings.search_result_limit
    rather than a hardcoded default baked into the query param."""
    from app.config import get_settings

    resp = client.get("/advisor/search")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) <= get_settings().search_result_limit


def test_search_explicit_limit_still_overrides_settings_default():
    resp = client.get("/advisor/search?limit=3")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) <= 3


def test_search_invalid_type_400():
    resp = client.get("/advisor/search?type=NotARealType")
    assert resp.status_code == 400


def test_search_no_match_returns_empty_list():
    resp = client.get(f"/advisor/search?q=no-such-thing-{uuid.uuid4().hex}")
    assert resp.status_code == 200
    assert resp.json() == {"results": [], "total": 0}


# ---------------------------------------------------------------------------
# Conversation / object lookup
# ---------------------------------------------------------------------------


def test_conversation_lookup():
    tag = unique_id()
    conv_id = import_conversation("body", title=f"Lookup {tag}")
    resp = client.get(f"/advisor/search/conversations/{conv_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == f"Lookup {tag}"


def test_conversation_lookup_404():
    resp = client.get("/advisor/search/conversations/does-not-exist")
    assert resp.status_code == 404


def test_object_lookup():
    tag = unique_id()
    conv_id = import_conversation(f"Decidimos usar {tag}. Aprobado por todos.")
    extract(conv_id)
    object_id = client.get(f"/extraction/conversations/{conv_id}/objects").json()[0]["id"]

    resp = client.get(f"/advisor/search/objects/{object_id}")
    assert resp.status_code == 200
    assert resp.json()["conversation_id"] == conv_id


def test_object_lookup_404():
    resp = client.get("/advisor/search/objects/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Graph navigation: a search result's graph_node_id must resolve
# ---------------------------------------------------------------------------


def test_search_result_graph_node_id_resolves_on_knowledge_graph_api():
    tag = unique_id()
    conv_id = import_conversation(f"Decidimos usar {tag}. Aprobado por todos.")
    extract(conv_id)

    results = client.get(f"/advisor/search?q={tag}&type=Decision").json()["results"]
    node_id = results[0]["graph_node_id"]

    resp = client.get(f"/conversation-graph/nodes/{node_id}")
    assert resp.status_code == 200
    assert resp.json()["node"]["label"] == results[0]["name"]


def test_conversation_result_graph_node_id_resolves():
    tag = unique_id()
    conv_id = import_conversation("body", title=f"GraphNav {tag}")

    results = client.get(f"/advisor/search?q={tag}&type=Conversation").json()["results"]
    node_id = results[0]["graph_node_id"]
    assert node_id == f"conversation:{conv_id}"

    resp = client.get(f"/conversation-graph/nodes/{node_id}")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Zero regressions: existing Epic 2 Advisor endpoints untouched
# ---------------------------------------------------------------------------


def test_existing_advisor_endpoints_unaffected():
    assert client.get("/advisor/recommendations").status_code == 200
    assert client.get("/advisor/daily-brief").status_code == 200


def test_other_existing_endpoints_unaffected():
    assert client.get("/health").status_code == 200
    assert client.get("/import/history").status_code == 200
    assert client.get("/extraction/metrics").status_code == 200
    assert client.get("/conversation-graph").status_code == 200
