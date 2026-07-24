"""Repo-level smoke test for the ChatGPT import CLI (Sprint B1).

Runs scripts/import_chatgpt.py end-to-end against the bundled sample
ChatGPT export, using an isolated imports DB so it never touches the
committed sample database. Complements the API/service tests under
dashboard/tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "import_chatgpt.py"
SAMPLE_EXPORT = REPO_ROOT / "samples" / "chatgpt_export_example" / "conversations-test.json"


def _run(tmp_path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["ROLE_OS_IMPORTS_DB_PATH"] = str(tmp_path / "role_os_imports.db")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(SAMPLE_EXPORT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_imports_sample_export(tmp_path):
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Total found: 1" in result.stdout
    assert "Imported:    1" in result.stdout
    assert "Status:      completed" in result.stdout


def test_cli_reimport_is_skipped_not_duplicated(tmp_path):
    first = _run(tmp_path)
    assert first.returncode == 0
    second = _run(tmp_path)
    assert second.returncode == 0
    assert "Imported:    0" in second.stdout
    assert "Skipped:     1" in second.stdout


def test_cli_missing_file_reports_error(tmp_path):
    env = os.environ.copy()
    env["ROLE_OS_IMPORTS_DB_PATH"] = str(tmp_path / "role_os_imports.db")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "does-not-exist.json")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode != 0
    assert "not found" in result.stdout.lower()
