"""Integration tests for the Conversation Explorer (Sprint B1.5): browsing,
searching, filtering, sorting, and paginating imported conversations, plus
conversation detail, metadata, JSON export, delete, facets, and metrics.

Uses the shared TestClient/app instance (same pattern as test_import_api.py)
against the isolated temp imports DB set up in conftest.py.
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def unique_id() -> str:
    return f"conv-{uuid.uuid4().hex[:8]}"


def conversation(conv_id: str | None, title: str, text: str, **overrides) -> dict:
    base = {
        "id": conv_id,
        "title": title,
        "create_time": 1700000000,
        "update_time": 1700003600,
        "mapping": {
            "n1": {
                "message": {
                    "author": {"role": "user"},
                    "create_time": 1700000000,
                    "content": {"parts": [text]},
                }
            },
            "n2": {
                "message": {
                    "author": {"role": "assistant"},
                    "create_time": 1700000100,
                    "content": {"parts": ["Acknowledged."]},
                }
            },
        },
    }
    base.update(overrides)
    return base


def upload(conversations: list, filename: str = "export.json"):
    payload = json.dumps(conversations).encode("utf-8")
    resp = client.post("/import/chatgpt", files={"file": (filename, payload, "application/json")})
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# List / pagination / sort
# ---------------------------------------------------------------------------


def test_list_returns_paginated_envelope():
    tag = unique_id()
    upload([conversation(f"{tag}-a", f"Alpha {tag}", "hello"), conversation(f"{tag}-b", f"Beta {tag}", "world")])

    resp = client.get(f"/import/conversations?q={tag}&page=1&page_size=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert len(body["items"]) == 1


def test_pagination_second_page_returns_remaining_item():
    tag = unique_id()
    upload([conversation(f"{tag}-a", f"Alpha {tag}", "hello"), conversation(f"{tag}-b", f"Beta {tag}", "world")])

    page1 = client.get(f"/import/conversations?q={tag}&page=1&page_size=1").json()
    page2 = client.get(f"/import/conversations?q={tag}&page=2&page_size=1").json()
    ids_seen = {page1["items"][0]["id"], page2["items"][0]["id"]}
    assert len(ids_seen) == 2


def test_sort_by_title_ascending():
    tag = unique_id()
    upload([conversation(f"{tag}-z", f"Zeta {tag}", "x"), conversation(f"{tag}-a", f"Alpha {tag}", "y")])

    resp = client.get(f"/import/conversations?q={tag}&sort_by=title&sort_dir=asc")
    titles = [c["title"] for c in resp.json()["items"]]
    assert titles == sorted(titles)


def test_sort_by_message_count():
    resp = client.get("/import/conversations?sort_by=message_count&sort_dir=desc&page_size=5")
    assert resp.status_code == 200
    counts = [c["message_count"] for c in resp.json()["items"]]
    assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_search_by_title():
    tag = unique_id()
    upload([conversation(tag, f"Findable title {tag}", "irrelevant body text")])
    resp = client.get(f"/import/conversations?q={tag}")
    assert any(c["external_id"] == tag for c in resp.json()["items"])


def test_search_by_conversation_text():
    tag = unique_id()
    marker = f"needle-{uuid.uuid4().hex[:8]}"
    upload([conversation(tag, "Untagged title", f"contains {marker} inside the message body")])
    resp = client.get(f"/import/conversations?q={marker}")
    assert any(c["external_id"] == tag for c in resp.json()["items"])


def test_search_by_conversation_id():
    tag = unique_id()
    upload([conversation(tag, "Some title", "some text")])
    resp = client.get(f"/import/conversations?q={tag}")
    assert any(c["external_id"] == tag for c in resp.json()["items"])


def test_search_by_source():
    resp = client.get("/import/conversations?q=chatgpt&page_size=1")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_filter_by_source():
    tag = unique_id()
    upload([conversation(tag, f"Sourced {tag}", "body")])
    resp = client.get(f"/import/conversations?q={tag}&source=chatgpt")
    assert all(c["source"] == "chatgpt" for c in resp.json()["items"])
    assert resp.json()["total"] == 1


def test_filter_by_source_excludes_other_sources():
    tag = unique_id()
    upload([conversation(tag, f"Sourced {tag}", "body")])
    resp = client.get(f"/import/conversations?q={tag}&source=claude")
    assert resp.json()["total"] == 0


def test_filter_by_status():
    tag = unique_id()
    upload([conversation(tag, f"Status {tag}", "body")])
    resp = client.get(f"/import/conversations?q={tag}&status=imported")
    assert resp.json()["total"] == 1


def test_filter_by_imported_after_excludes_older_than_future_cutoff():
    tag = unique_id()
    upload([conversation(tag, f"Cutoff {tag}", "body")])
    future = "2999-01-01T00:00:00+00:00"
    resp = client.get(f"/import/conversations?q={tag}&imported_after={future}")
    assert resp.json()["total"] == 0


def test_filter_by_imported_after_includes_recent():
    tag = unique_id()
    upload([conversation(tag, f"Recent {tag}", "body")])
    past = "2000-01-01T00:00:00+00:00"
    resp = client.get(f"/import/conversations?q={tag}&imported_after={past}")
    assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# Detail / metadata
# ---------------------------------------------------------------------------


def test_conversation_detail_includes_content_and_metadata():
    tag = unique_id()
    run = upload([conversation(tag, f"Detail {tag}", "the message body")])
    list_resp = client.get(f"/import/conversations?q={tag}").json()
    conv_id = list_resp["items"][0]["id"]

    resp = client.get(f"/import/conversations/{conv_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == f"Detail {tag}"
    assert body["fingerprint"] == f"id:{tag}"
    assert body["import_run_id"] == run["id"]
    assert len(body["content"]) == 2
    assert body["content"][0]["role"] == "user"
    assert body["content"][0]["text"] == "the message body"


def test_conversation_detail_404_for_unknown_id():
    resp = client.get("/import/conversations/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


def test_export_json_returns_download_headers():
    tag = unique_id()
    upload([conversation(tag, f"Export {tag}", "body")])
    conv_id = client.get(f"/import/conversations?q={tag}").json()["items"][0]["id"]

    resp = client.get(f"/import/conversations/{conv_id}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert "attachment" in resp.headers["content-disposition"]
    body = json.loads(resp.content)
    assert body["id"] == conv_id
    assert body["content"][0]["text"] == "body"


def test_export_json_404_for_unknown_id():
    resp = client.get("/import/conversations/does-not-exist/export")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_conversation_then_404():
    tag = unique_id()
    upload([conversation(tag, f"Delete {tag}", "body")])
    conv_id = client.get(f"/import/conversations?q={tag}").json()["items"][0]["id"]

    resp = client.delete(f"/import/conversations/{conv_id}")
    assert resp.status_code == 204

    resp = client.get(f"/import/conversations/{conv_id}")
    assert resp.status_code == 404


def test_delete_unknown_conversation_404():
    resp = client.delete("/import/conversations/does-not-exist")
    assert resp.status_code == 404


def test_deleted_conversation_does_not_reappear_in_list():
    tag = unique_id()
    upload([conversation(tag, f"Gone {tag}", "body")])
    conv_id = client.get(f"/import/conversations?q={tag}").json()["items"][0]["id"]
    client.delete(f"/import/conversations/{conv_id}")

    resp = client.get(f"/import/conversations?q={tag}")
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Facets / metrics
# ---------------------------------------------------------------------------


def test_facets_include_chatgpt_source_and_imported_status():
    upload([conversation(unique_id(), "Facet check", "body")])
    resp = client.get("/import/facets")
    assert resp.status_code == 200
    body = resp.json()
    assert "chatgpt" in body["sources"]
    assert "imported" in body["statuses"]


def test_metrics_reports_real_conversation_count_and_zero_for_unimplemented():
    before = client.get("/import/metrics").json()["imported_conversations"]
    upload([conversation(unique_id(), "Metrics check", "body")])
    after = client.get("/import/metrics")
    assert after.status_code == 200
    body = after.json()
    assert body["imported_conversations"] == before + 1
    assert body["pending_processing"] == 0
    assert body["processed"] == 0
    assert body["knowledge_objects"] == 0
    assert body["projects"] == 0
    assert body["decisions"] == 0
    assert body["assets"] == 0


# ---------------------------------------------------------------------------
# Zero regressions on existing importer behavior
# ---------------------------------------------------------------------------


def test_import_and_history_endpoints_still_work():
    tag = unique_id()
    upload([conversation(tag, f"Regression {tag}", "body")])
    assert client.get("/import/history").status_code == 200
    assert client.get("/health").status_code == 200
