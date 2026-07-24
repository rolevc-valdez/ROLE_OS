#!/usr/bin/env python3
"""CLI for the ChatGPT conversation importer (Sprint B1).

Calls the same `app.imports.service.run_import` the `/import/chatgpt` API
route calls, so the CLI and API can never drift. Does not modify any
backend code or schema.

Usage:
    python scripts/import_chatgpt.py <path-to-conversations.json>
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_ROOT = REPO_ROOT / "dashboard"
sys.path.insert(0, str(DASHBOARD_ROOT))

from app.imports.parser import InvalidExportError  # noqa: E402
from app.imports.service import run_import  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_chatgpt.py <path-to-conversations.json>")
        raise SystemExit(2)

    source = Path(sys.argv[1])
    if not source.is_file():
        print(f"File not found: {source}")
        raise SystemExit(1)

    print(f"Processing: {source}")
    raw = source.read_bytes()

    try:
        result = run_import(raw, source.name)
    except InvalidExportError as exc:
        print(f"Import failed: {exc}")
        raise SystemExit(1) from exc

    print(f"Total found: {result['total_found']}")
    print(f"Imported:    {result['imported']}")
    print(f"Updated:     {result['updated']}")
    print(f"Skipped:     {result['skipped']}")
    print(f"Invalid:     {result['invalid']}")
    print(f"Status:      {result['status']}")
    if result["errors"]:
        print("Errors:")
        for err in result["errors"]:
            print(f"  - record #{err['index']}: {err['reason']}")


if __name__ == "__main__":
    main()
