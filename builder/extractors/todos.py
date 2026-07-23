"""Open TODOs extractor.

Pulls lines that read as outstanding/pending work items from the
conversation body.
"""

from __future__ import annotations

from ._util import pick

TODO_PATTERNS = [
    r"\bpendiente",
    r"\bfalta",
    r"\bto-?do\b",
    r"siguiente",
    r"despu[eé]s",
]


def extract_todos(lines: list[str], limit: int = 10) -> list[str]:
    """Return lines that read as open/outstanding to-do items."""
    return pick(lines, TODO_PATTERNS, limit)
