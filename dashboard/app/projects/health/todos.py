"""Open-TODO-count signal: fewer open to-dos means a healthier project."""

from __future__ import annotations

from typing import Any


def score_open_todos(todos: list[dict[str, Any]]) -> int:
    """Score 0-100: higher means fewer open (non-"done") to-do items."""
    open_count = sum(1 for t in todos if (t.get("status") or "open") != "done")
    if open_count == 0:
        return 100
    if open_count <= 2:
        return 80
    if open_count <= 5:
        return 60
    if open_count <= 10:
        return 35
    return 15
