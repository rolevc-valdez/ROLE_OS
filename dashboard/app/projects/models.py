"""Pydantic request/response schemas for the Project Intelligence API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------


class WorkspaceCreate(BaseModel):
    name: str
    description: str = ""


class Workspace(BaseModel):
    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    project_count: int = 0

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str
    workspace: str
    description: str = ""
    status: str = "active"
    priority: str = "medium"
    tags: list[str] = Field(default_factory=list)
    owner: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    workspace: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    tags: list[str] | None = None
    owner: str | None = None


class Project(BaseModel):
    id: str
    workspace_id: str
    workspace: str
    name: str
    description: str
    status: str
    health_score: int
    priority: str
    tags: list[str]
    owner: str
    notes: list[dict] = Field(default_factory=list)
    decisions: list[dict] = Field(default_factory=list)
    todos: list[dict] = Field(default_factory=list)
    deliverables: list[dict] = Field(default_factory=list)
    assets: list[dict] = Field(default_factory=list)
    prompts: list[dict] = Field(default_factory=list)
    conversations: list[str] = Field(default_factory=list)
    related_projects: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str

    model_config = ConfigDict(extra="allow")


class ProjectSummary(BaseModel):
    """Light-weight project representation used in list views."""

    id: str
    workspace: str
    name: str
    description: str
    status: str
    health_score: int
    priority: str
    tags: list[str]
    owner: str
    updated_at: str

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Collections (notes, decisions, todos, deliverables, assets, prompts)
# ---------------------------------------------------------------------------


class CollectionItemCreate(BaseModel):
    """Generic collection item input.

    `text` covers notes/decisions/todos/deliverables/prompts; `name`/`url`
    cover assets. `status` is meaningful for decisions ("resolved" |
    "pending"), todos ("open" | "done"), and deliverables ("planned" |
    "delivered").
    """

    text: str | None = None
    name: str | None = None
    url: str | None = None
    status: str | None = None


class CollectionItemUpdate(BaseModel):
    text: str | None = None
    name: str | None = None
    url: str | None = None
    status: str | None = None


class CollectionItem(BaseModel):
    id: str
    created_at: str

    model_config = ConfigDict(extra="allow")


class ConversationLink(BaseModel):
    conversation_id: str


class RelatedProjectLink(BaseModel):
    project_id: str


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


class CapabilityCreate(BaseModel):
    name: str
    description: str = ""
    category: str = ""


class Capability(BaseModel):
    id: str
    project_id: str
    name: str
    description: str
    category: str
    created_at: str

    model_config = ConfigDict(extra="allow")


class CapabilityConsumeRequest(BaseModel):
    consumer_project_id: str


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class DependencyCreate(BaseModel):
    depends_on_project_id: str
    note: str = ""


class Dependency(BaseModel):
    id: str
    project_id: str
    depends_on_project_id: str
    note: str
    created_at: str

    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthScoreResponse(BaseModel):
    project_id: str
    score: int
    breakdown: dict[str, int]
