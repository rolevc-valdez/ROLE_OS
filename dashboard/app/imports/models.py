"""Pydantic request/response schemas for the ChatGPT conversation importer
and the Conversation Explorer (Sprint B1.5)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImportError(BaseModel):
    index: int
    reason: str


class ImportSummary(BaseModel):
    status: str
    source_filename: str
    source_fingerprint: str
    total_found: int
    imported: int
    updated: int
    skipped: int
    invalid: int
    errors: list[ImportError] = Field(default_factory=list)
    started_at: str
    completed_at: str


class ImportRun(ImportSummary):
    id: str


class ImportedConversation(BaseModel):
    id: str
    source: str
    external_id: str | None
    fingerprint: str
    title: str
    created_at: str | None
    updated_at: str | None
    message_count: int
    roles: list[str]
    imported_at: str
    last_seen_at: str
    source_file: str
    source_fingerprint: str
    status: str
    import_run_id: str | None


class ConversationMessage(BaseModel):
    role: str
    text: str
    created_at: str | None


class ConversationDetail(ImportedConversation):
    content: list[ConversationMessage]


class ConversationListResponse(BaseModel):
    items: list[ImportedConversation]
    total: int
    page: int
    page_size: int


class ImportFacets(BaseModel):
    sources: list[str]
    statuses: list[str]


class ExplorerMetrics(BaseModel):
    imported_conversations: int
    pending_processing: int
    processed: int
    knowledge_objects: int
    projects: int
    decisions: int
    assets: int
