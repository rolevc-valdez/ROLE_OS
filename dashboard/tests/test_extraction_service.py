"""Unit tests for the extraction orchestration service (Sprint 4):
extraction, persistence, duplicate prevention, and re-run behavior.

Exercises app.extraction.service.run_extraction directly against real
imported conversations (via app.imports.service.run_import), using the
isolated temp imports/extraction DBs set up in conftest.py.
"""

from __future__ import annotations

import json
import uuid

import pytest
from app.extraction import db as extraction_db
from app.extraction.service import ConversationNotFoundError, run_extraction
from app.imports.service import run_import


def unique_id() -> str:
    return f"conv-{uuid.uuid4().hex[:8]}"


def import_one(text: str, conv_id: str | None = None) -> str:
    """Import a single-message conversation and return its internal id."""
    conv_id = conv_id or unique_id()
    payload = json.dumps(
        [
            {
                "id": conv_id,
                "title": f"Extraction test {conv_id}",
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
    result = run_import(payload, "export.json")
    assert result["imported"] == 1

    from app.imports import db as imports_db

    matches = [c for c in imports_db.list_conversations(limit=500) if c["external_id"] == conv_id]
    return matches[0]["id"]


def test_run_extraction_persists_objects_for_every_matched_type():
    text = (
        "Necesitamos definir el proyecto de expansion antes del viernes.\n"
        "Maria Gonzalez va a liderar el equipo.\n"
        "Decidimos usar Claude para el pipeline. Aprobado por todos.\n"
        "Se me ocurre una idea: podriamos automatizar el reporte semanal.\n"
        "Todavia esta pendiente revisar el presupuesto.\n"
        "Adjunto budget_report.pdf y logo_final.png"
    )
    conv_id = import_one(text)

    result = run_extraction(conv_id)
    assert result["status"] == "completed"
    assert result["conversation_id"] == conv_id
    assert result["total_found"] > 0
    assert result["created"] == result["total_found"]
    assert result["updated"] == 0
    assert result["unchanged"] == 0

    objects = extraction_db.list_objects(conv_id)
    types_found = {o["object_type"] for o in objects}
    assert types_found == {"Project", "Person", "Task", "Decision", "Idea", "Document", "Asset"}
    for o in objects:
        assert o["conversation_id"] == conv_id
        assert o["source"] == "chatgpt"
        assert 0 < o["confidence"] <= 1
        assert o["created_at"]
        assert o["updated_at"]
        assert o["extraction_run_id"] == result["id"]


def test_run_extraction_unknown_conversation_raises():
    with pytest.raises(ConversationNotFoundError):
        run_extraction("not-a-real-conversation-id")


def test_rerun_extraction_does_not_duplicate_objects():
    conv_id = import_one("Decidimos usar Claude para el pipeline. Aprobado por todos.")

    first = run_extraction(conv_id)
    second = run_extraction(conv_id)

    assert second["created"] == 0
    assert second["unchanged"] == first["total_found"]

    objects = extraction_db.list_objects(conv_id)
    assert len(objects) == first["total_found"]  # no duplicate rows


def test_rerun_extraction_reruns_are_idempotent_across_many_calls():
    conv_id = import_one("Todavia esta pendiente revisar el presupuesto con John Smith.")
    run_extraction(conv_id)
    run_extraction(conv_id)
    run_extraction(conv_id)

    objects = extraction_db.list_objects(conv_id)
    fingerprints = {o["fingerprint"] for o in objects}
    assert len(fingerprints) == len(objects)  # every fingerprint unique


def test_extraction_with_no_matches_still_records_a_run():
    conv_id = import_one("just a plain message with nothing extractable in it")
    result = run_extraction(conv_id)
    assert result["status"] == "completed"
    assert result["total_found"] == 0
    assert extraction_db.list_objects(conv_id) == []


def test_delete_object_then_rerun_recreates_it():
    conv_id = import_one("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    run_extraction(conv_id)
    objects = extraction_db.list_objects(conv_id)
    assert len(objects) == 1
    extraction_db.delete_object(objects[0]["id"])
    assert extraction_db.list_objects(conv_id) == []

    rerun = run_extraction(conv_id)
    assert rerun["created"] == 1
    assert len(extraction_db.list_objects(conv_id)) == 1


def test_counts_by_type_reflects_persisted_objects():
    conv_id = import_one("Decidimos usar Claude para el pipeline. Aprobado por todos.")
    before = extraction_db.counts_by_type().get("Decision", 0)
    run_extraction(conv_id)
    after = extraction_db.counts_by_type().get("Decision", 0)
    assert after == before + 1
