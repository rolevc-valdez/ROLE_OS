"""Unit tests for the import orchestration service (Sprint B1).

Exercises app.imports.service.run_import directly (not through the API),
against the isolated temp imports DB set up in conftest.py.
"""

from __future__ import annotations

import json
import uuid

import pytest
from app.imports.parser import InvalidExportError
from app.imports.service import run_import


def unique_id() -> str:
    return f"conv-{uuid.uuid4().hex[:8]}"


def conversation(conv_id: str, text: str = "Hello there", **overrides) -> dict:
    base = {
        "id": conv_id,
        "title": f"Conversation {conv_id}",
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
        },
    }
    base.update(overrides)
    return base


def export_bytes(conversations: list) -> bytes:
    return json.dumps(conversations).encode("utf-8")


def test_valid_import_reports_imported_count():
    cid = unique_id()
    result = run_import(export_bytes([conversation(cid)]), "export.json")
    assert result["status"] == "completed"
    assert result["total_found"] == 1
    assert result["imported"] == 1
    assert result["updated"] == 0
    assert result["skipped"] == 0
    assert result["invalid"] == 0
    assert result["errors"] == []


def test_malformed_json_raises_invalid_export_error():
    with pytest.raises(InvalidExportError):
        run_import(b"{not json", "export.json")


def test_partially_invalid_records_do_not_crash_import():
    cid = unique_id()
    conversations = [conversation(cid), "garbage-record", {"mapping": {}}]
    result = run_import(export_bytes(conversations), "export.json")
    assert result["total_found"] == 3
    assert result["imported"] == 1
    assert result["invalid"] == 2
    assert len(result["errors"]) == 2
    for err in result["errors"]:
        assert "reason" in err and "index" in err


def test_duplicate_import_is_skipped_not_duplicated():
    cid = unique_id()
    payload = export_bytes([conversation(cid)])
    first = run_import(payload, "export.json")
    second = run_import(payload, "export.json")

    assert first["imported"] == 1
    assert second["imported"] == 0
    assert second["skipped"] == 1
    assert second["updated"] == 0


def test_reimport_with_changed_content_is_reported_as_updated():
    cid = unique_id()
    first_payload = export_bytes([conversation(cid, text="Original text")])
    second_payload = export_bytes([conversation(cid, text="Original text", update_time=1700099999)])

    first = run_import(first_payload, "export.json")
    second = run_import(second_payload, "export-v2.json")

    assert first["imported"] == 1
    assert second["updated"] == 1
    assert second["imported"] == 0
    assert second["skipped"] == 0


def test_missing_external_id_falls_back_to_content_fingerprint():
    conv = conversation(unique_id())
    conv["id"] = None
    result = run_import(export_bytes([conv]), "export.json")
    assert result["imported"] == 1
    assert result["invalid"] == 0

    # Re-importing the exact same content-only record must dedupe too.
    result2 = run_import(export_bytes([conv]), "export.json")
    assert result2["skipped"] == 1
    assert result2["imported"] == 0
