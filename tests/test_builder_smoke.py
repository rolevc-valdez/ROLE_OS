"""Repo-level integration smoke test for the ROLE OS Builder.

Runs builder.py end-to-end against the bundled sample ChatGPT export and
checks that the expected SQLite database and knowledge structure are
produced. Complements the unit-style API tests under dashboard/tests.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_DIR = REPO_ROOT / "builder"
SAMPLE_EXPORT = REPO_ROOT / "samples" / "chatgpt_export_example"


def test_builder_runs_end_to_end(tmp_path):
    output = tmp_path / "ROLE_KNOWLEDGE_OS"
    result = subprocess.run(
        [sys.executable, "builder.py", str(SAMPLE_EXPORT), str(output), "--clean"],
        cwd=BUILDER_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout.strip())
    assert payload["status"] == "ok"
    assert payload["conversations"] >= 1

    db_path = output / "00_SYSTEM" / "role_os.db"
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT COUNT(*) FROM knowledge_cards").fetchone()
        assert rows[0] == payload["conversations"]
    finally:
        conn.close()

    assert (output / "00_SYSTEM" / "MASTER_INDEX.md").exists()
    assert (output / "04_KNOWLEDGE" / "PROJECTS.json").exists()
