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
    # Sprint 5 (Project Unification): set only when this Project is the
    # canonical identity for an adopted Workspace/Discovery item -- see
    # app.workspace.identity. None for a purely manually-created Project.
    discovery_item_id: str | None = None

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
    discovery_item_id: str | None = None

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
# AI Workspace (v1.3)
# ---------------------------------------------------------------------------


class AIWorkspace(BaseModel):
    project_id: str
    claude_url: str
    chatgpt_url: str
    gemini_url: str
    role: str
    preferred_model: str
    last_opened_at: str | None
    created_at: str
    updated_at: str


class AIWorkspaceSave(BaseModel):
    claude_url: str | None = None
    chatgpt_url: str | None = None
    gemini_url: str | None = None
    role: str | None = None
    preferred_model: str | None = None


class AIWorkspaceOpenRequest(BaseModel):
    tool: str  # "claude" | "chatgpt" | "both"


class AIWorkspaceOpenResultItem(BaseModel):
    tool: str
    url: str
    used_saved_conversation: bool


class AIWorkspaceOpenResponse(BaseModel):
    project_id: str
    results: list[AIWorkspaceOpenResultItem]
    any_missing: bool
    last_opened_at: str | None


# ---------------------------------------------------------------------------
# AI Sessions + Session Snapshots + Resume Engine + Timeline (v1.4 Context Engine)
# ---------------------------------------------------------------------------


class AISessionCreate(BaseModel):
    assistant: str
    title: str = ""
    conversation_url: str = ""
    role: str = ""
    preferred_model: str = ""
    notes: str = ""


class AISessionUpdate(BaseModel):
    title: str | None = None
    conversation_url: str | None = None
    role: str | None = None
    preferred_model: str | None = None
    status: str | None = None
    favorite: bool | None = None
    notes: str | None = None


class AISession(BaseModel):
    id: str
    project_id: str
    title: str
    assistant: str
    conversation_url: str
    role: str
    preferred_model: str
    started_at: str
    last_used_at: str | None
    status: str
    favorite: bool
    current: bool
    notes: str
    created_at: str
    updated_at: str


class AISessionOpenResult(BaseModel):
    session_id: str
    url: str | None
    used_saved_conversation: bool
    message: str | None = None


class AISessionSnapshotCreate(BaseModel):
    accomplishments: str = ""
    blockers: str = ""
    pending_work: str = ""
    next_prompt: str = ""
    decisions: str = ""
    summary: str = ""


class AISessionSnapshot(BaseModel):
    id: str
    session_id: str
    accomplishments: str
    blockers: str
    pending_work: str
    next_prompt: str
    decisions: str
    summary: str
    created_at: str


class AISessionResumeResult(BaseModel):
    session_id: str
    prompt: str
    url: str | None
    used_saved_conversation: bool


class ProjectTimelineEntry(BaseModel):
    type: str  # "session_started" | "snapshot"
    timestamp: str
    session_id: str
    session_title: str
    assistant: str
    excerpt: str


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthScoreResponse(BaseModel):
    project_id: str
    score: int
    breakdown: dict[str, int]


# ---------------------------------------------------------------------------
# Project Identity Reconciliation (Sprint C2.1)
# ---------------------------------------------------------------------------


class DuplicateCandidateProjectRef(BaseModel):
    id: str
    name: str
    workspace: str | None = None


class DuplicateCandidate(BaseModel):
    """Read-only evidence for one candidate duplicate pair -- see
    `app.workspace.reconciliation.find_duplicate_candidates`. Never
    implies a merge should or will happen automatically."""

    project_a: DuplicateCandidateProjectRef
    project_b: DuplicateCandidateProjectRef
    evidence: list[str]
    confidence: int
    exact_name_match: bool
    root_path_match: bool
    git_remote_match: bool
    same_workspace: bool
    one_discovery_linked: bool
    suggested_survivor_id: str | None = None


class MergeProjectsRequest(BaseModel):
    surviving_id: str
    duplicate_id: str
    # Required and must be exactly `true` -- there is no default that
    # allows an accidental/automatic merge (§3 of the brief: "never
    # perform a destructive automatic merge").
    confirm: bool = False


class MergeProjectsResult(BaseModel):
    project: Project
    duplicate_id: str
    migrated: dict[str, int]
    moved_discovery_item_id: str | None = None
    collection_fields_merged: list[str]
