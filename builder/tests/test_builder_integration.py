"""End-to-end regression test for Milestone 3: running builder.py must
produce enriched knowledge cards (vendors, files, related_conversations)
and persist them to SQLite automatically, while keeping the existing CLI
and output layout unchanged.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

BUILDER_DIR = Path(__file__).resolve().parents[1]

CONVERSATIONS = [
    {
        "id": "conv-1",
        "title": "ROLE Master Factory planning",
        "create_time": 1700000000,
        "update_time": 1700003600,
        "mapping": {
            "n1": {
                "message": {
                    "author": {"role": "user"},
                    "create_time": 1700000000,
                    "content": {"parts": ["Quiero definir el plan para ROLE Master Factory. Adjunto plan.pdf."]},
                }
            },
            "n2": {
                "message": {
                    "author": {"role": "assistant"},
                    "create_time": 1700000100,
                    "content": {"parts": ["Decidimos usar Claude para el pipeline. Aprobado."]},
                }
            },
        },
    },
    {
        "id": "conv-2",
        "title": "ROLE Master Factory follow-up",
        "create_time": 1700100000,
        "update_time": 1700103600,
        "mapping": {
            "n1": {
                "message": {
                    "author": {"role": "user"},
                    "create_time": 1700100000,
                    "content": {"parts": ["Seguimiento del plan con Microsoft."]},
                }
            },
            "n2": {
                "message": {
                    "author": {"role": "assistant"},
                    "create_time": 1700100100,
                    "content": {"parts": ["El entregable final quedo listo para revision."]},
                }
            },
        },
    },
]


def _run_builder(tmp_path: Path) -> dict:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    (export_dir / "conversations-test.json").write_text(json.dumps(CONVERSATIONS), encoding="utf-8")

    output = tmp_path / "ROLE_KNOWLEDGE_OS"
    result = subprocess.run(
        [sys.executable, "builder.py", str(export_dir), str(output), "--clean"],
        cwd=BUILDER_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout.strip())
    return {"payload": payload, "output": output}


def test_builder_enriches_cards_with_milestone3_fields(tmp_path):
    ctx = _run_builder(tmp_path)
    output: Path = ctx["output"]

    cards_dir = output / "04_KNOWLEDGE" / "KNOWLEDGE_CARDS"
    card_files = sorted(cards_dir.glob("*.json"))
    assert len(card_files) == 2

    cards = {json.loads(f.read_text())["conversation_id"]: json.loads(f.read_text()) for f in card_files}

    conv1 = cards["conv-1"]
    assert conv1["files"] == ["plan.pdf"]
    assert conv1["decisions"]
    assert conv1["related_conversations"] == ["conv-2"]

    conv2 = cards["conv-2"]
    assert conv2["vendors"] == ["Microsoft"]
    assert conv2["deliverables"]
    assert conv2["related_conversations"] == ["conv-1"]


def test_builder_writes_vendors_index(tmp_path):
    ctx = _run_builder(tmp_path)
    output: Path = ctx["output"]
    vendors = json.loads((output / "04_KNOWLEDGE" / "VENDORS.json").read_text())
    assert vendors.get("Microsoft") == ["conv-2"]


def test_builder_updates_sqlite_with_enriched_fields(tmp_path):
    ctx = _run_builder(tmp_path)
    output: Path = ctx["output"]
    db_path = output / "00_SYSTEM" / "role_os.db"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT conversation_id, card_json FROM knowledge_cards").fetchall()
    finally:
        conn.close()

    by_id = {row[0]: json.loads(row[1]) for row in rows}
    assert by_id["conv-1"]["related_conversations"] == ["conv-2"]
    assert by_id["conv-2"]["vendors"] == ["Microsoft"]


def test_builder_cli_and_output_layout_unchanged(tmp_path):
    """Milestone 3 must not break the existing CLI contract or output layout."""
    ctx = _run_builder(tmp_path)
    output: Path = ctx["output"]

    assert ctx["payload"]["status"] == "ok"
    assert ctx["payload"]["conversations"] == 2

    assert (output / "00_SYSTEM" / "MASTER_INDEX.md").exists()
    assert (output / "00_SYSTEM" / "role_os.db").exists()
    assert (output / "01_PROJECTS" / "ROLE_MASTER_FACTORY" / "README.md").exists()
    assert (output / "04_KNOWLEDGE" / "PROJECTS.json").exists()
    assert (output / "04_KNOWLEDGE" / "PEOPLE.json").exists()
    assert (output / "04_KNOWLEDGE" / "APPLICATIONS.json").exists()
    assert (output / "04_KNOWLEDGE" / "TAGS.json").exists()
    assert (output / "04_KNOWLEDGE" / "TIMELINE.json").exists()
    assert (output / "README.md").exists()
