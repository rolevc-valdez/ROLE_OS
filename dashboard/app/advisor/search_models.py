"""Pydantic response schemas for Advisor Search (Sprint 6).

New, additive files inside the existing `app/advisor/` package -- the
Epic 2 recommendation engine's own files (`db.py`, `engine.py`,
`models.py`, `narrative.py`, `rules/`, `scoring.py`) are untouched.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ResultType = Literal["Conversation", "Project", "Person", "Task", "Decision", "Idea", "Document", "Asset"]

RESULT_TYPES: tuple[ResultType, ...] = (
    "Conversation", "Project", "Person", "Task", "Decision", "Idea", "Document", "Asset",
)


class SearchResult(BaseModel):
    object_type: ResultType
    name: str
    conversation_id: str | None
    conversation_title: str | None
    date: str | None
    confidence: float | None
    graph_node_id: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int
