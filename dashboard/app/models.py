"""Pydantic response models for the ROLE OS Dashboard API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database_connected: bool


class ProjectSummary(BaseModel):
    project: str
    count: int


class KnowledgeCard(BaseModel):
    conversation_id: str
    title: str
    project: str
    category: str
    status: str
    date: str
    updated: str
    summary: str

    model_config = ConfigDict(extra="allow")
