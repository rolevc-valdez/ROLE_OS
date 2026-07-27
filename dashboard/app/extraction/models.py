"""Pydantic request/response schemas for Knowledge Extraction (Sprint 4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ObjectType = Literal["Project", "Person", "Task", "Decision", "Idea", "Document", "Asset"]

OBJECT_TYPES: tuple[ObjectType, ...] = ("Project", "Person", "Task", "Decision", "Idea", "Document", "Asset")


class ExtractedObject(BaseModel):
    id: str
    conversation_id: str
    object_type: ObjectType
    title: str
    source: str
    confidence: float
    fingerprint: str
    extraction_run_id: str
    created_at: str
    updated_at: str


class ExtractionRun(BaseModel):
    id: str
    conversation_id: str
    status: str
    total_found: int
    created: int
    updated: int
    unchanged: int
    counts_by_type: dict[str, int] = Field(default_factory=dict)
    started_at: str
    completed_at: str


class ExtractionCounts(BaseModel):
    """Object counts by type, used for both /extraction/metrics and the
    Explorer dashboard metrics strip."""

    project: int = 0
    person: int = 0
    task: int = 0
    decision: int = 0
    idea: int = 0
    document: int = 0
    asset: int = 0

    @property
    def total(self) -> int:
        return self.project + self.person + self.task + self.decision + self.idea + self.document + self.asset
