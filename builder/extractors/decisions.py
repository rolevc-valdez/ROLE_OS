"""Decisions and deliverables extractor.

Both are "outcome" statements pulled from the conversation body using
keyword-pattern matching over sentence-like line fragments — decisions are
things that were agreed/settled, deliverables are things that were produced
or finalized.
"""

from __future__ import annotations

from ._util import pick

DECISION_PATTERNS = [
    r"\bdecid",
    r"\baprob",
    r"quedamos",
    r"vamos a usar",
    r"se define",
    r"\bfinal\b",
]

DELIVERABLE_PATTERNS = [
    r"entregable",
    r"archivo final",
    r"listo para",
    r"generad",
    r"cread",
    r"completad",
]


def extract_decisions(lines: list[str], limit: int = 10) -> list[str]:
    """Return lines that read as decisions or agreements reached in the conversation."""
    return pick(lines, DECISION_PATTERNS, limit)


def extract_deliverables(lines: list[str], limit: int = 10) -> list[str]:
    """Return lines that read as deliverables produced during the conversation."""
    return pick(lines, DELIVERABLE_PATTERNS, limit)
