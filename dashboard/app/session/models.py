"""Pydantic request/response schemas for the Daily Session API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Operation modes
# ---------------------------------------------------------------------------


class Mode(BaseModel):
    id: str
    name: str
    purpose: str
    ai_behavior: str
    resources: list[str]


# ---------------------------------------------------------------------------
# Project registry
# ---------------------------------------------------------------------------


class RegistryProject(BaseModel):
    id: str
    name: str
    status: str
    reference: str
    milestone: str
    next_action: str
    is_authoritative: bool
    user_edited: bool
    is_default: bool
    created_at: str
    updated_at: str

    model_config = ConfigDict(extra="allow")


class RegistryProjectUpdate(BaseModel):
    status: str | None = None
    reference: str | None = None
    milestone: str | None = None
    next_action: str | None = None


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class SessionStart(BaseModel):
    date: str
    project_id: str | None = None
    project_name: str
    mode: str
    objective: str
    expected_result: str
    notes: str = ""


class SessionComplete(BaseModel):
    completed_work: str
    decisions: str = ""
    blockers: str = ""
    next_step: str = ""


class Session(BaseModel):
    id: str
    date: str
    project_id: str | None
    project_name: str
    mode: str
    objective: str
    expected_result: str
    notes: str
    status: str
    completed_work: str
    decisions: str
    blockers: str
    next_step: str
    created_at: str
    updated_at: str
    completed_at: str | None


# ---------------------------------------------------------------------------
# Generated artifacts
# ---------------------------------------------------------------------------


class ClaudePrompt(BaseModel):
    prompt: str


class DailyMarkdown(BaseModel):
    filename: str
    markdown: str


class SaveToVaultResult(BaseModel):
    saved: bool
    path: str | None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Recent ecosystem decisions
# ---------------------------------------------------------------------------


class RecentDecision(BaseModel):
    id: str
    date: str
    decision: str
    status: str


class RecentDecisionsResponse(BaseModel):
    decisions: list[RecentDecision]
    source: str  # "ecosystem" or "fallback"
    note: str
