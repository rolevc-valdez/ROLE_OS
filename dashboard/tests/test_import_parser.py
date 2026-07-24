"""Unit tests for the ChatGPT export parser (Sprint B1)."""

from __future__ import annotations

import json

import pytest
from app.imports.parser import InvalidExportError, iter_normalized, normalize_conversation, parse_export_bytes


def conversation(**overrides) -> dict:
    base = {
        "id": "conv-1",
        "title": "Planning session",
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
            "n2": {
                "message": {
                    "author": {"role": "assistant"},
                    "create_time": 1700000100,
                    "content": {"parts": ["Hi! How can I help?"]},
                }
            },
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# File-level parsing
# ---------------------------------------------------------------------------


def test_parse_export_bytes_valid_list():
    raw = json.dumps([conversation()]).encode("utf-8")
    result = parse_export_bytes(raw)
    assert isinstance(result, list)
    assert len(result) == 1


def test_parse_export_bytes_rejects_malformed_json():
    raw = b"{not valid json"
    with pytest.raises(InvalidExportError):
        parse_export_bytes(raw)


def test_parse_export_bytes_rejects_non_list_top_level():
    raw = json.dumps({"id": "not-a-list"}).encode("utf-8")
    with pytest.raises(InvalidExportError):
        parse_export_bytes(raw)


def test_parse_export_bytes_rejects_non_utf8():
    with pytest.raises(InvalidExportError):
        parse_export_bytes(b"\xff\xfe\x00\x01")


# ---------------------------------------------------------------------------
# Per-record normalization
# ---------------------------------------------------------------------------


def test_normalize_conversation_valid():
    record = normalize_conversation(conversation())
    assert record["external_id"] == "conv-1"
    assert record["fingerprint"] == "id:conv-1"
    assert record["title"] == "Planning session"
    assert record["message_count"] == 2
    assert record["roles"] == ["assistant", "user"]
    assert record["created_at"] is not None
    assert record["updated_at"] is not None


def test_normalize_conversation_rejects_non_object():
    with pytest.raises(ValueError):
        normalize_conversation("not a conversation")


def test_normalize_conversation_rejects_malformed_mapping():
    with pytest.raises(ValueError):
        normalize_conversation(conversation(mapping="not a mapping"))


def test_normalize_conversation_rejects_empty_junk_record():
    with pytest.raises(ValueError):
        normalize_conversation({"mapping": {}})


def test_normalize_conversation_missing_external_id_uses_fingerprint_fallback():
    record = normalize_conversation(conversation(id=None))
    assert record["external_id"] is None
    assert record["fingerprint"].startswith("hash:")


def test_normalize_conversation_missing_external_id_is_deterministic():
    a = normalize_conversation(conversation(id=None))
    b = normalize_conversation(conversation(id=None))
    assert a["fingerprint"] == b["fingerprint"]


def test_normalize_conversation_ignores_empty_messages():
    conv = conversation()
    conv["mapping"]["n3"] = {"message": {"author": {"role": "user"}, "content": {"parts": [""]}}}
    record = normalize_conversation(conv)
    assert record["message_count"] == 2


# ---------------------------------------------------------------------------
# Batch iteration: invalid records must not stop the whole import
# ---------------------------------------------------------------------------


def test_iter_normalized_skips_invalid_records_without_raising():
    conversations = [conversation(id="good-1"), "garbage", conversation(id="good-2", mapping="broken")]
    results = list(iter_normalized(conversations))
    assert len(results) == 3

    idx0, record0, error0 = results[0]
    assert record0 is not None and error0 is None

    idx1, record1, error1 = results[1]
    assert record1 is None and error1 is not None

    idx2, record2, error2 = results[2]
    assert record2 is None and error2 is not None
