"""Pydantic request/response schemas for the Workspace Adoption API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RescanRequest(BaseModel):
    root: str | None = None
    max_depth: int = 2


class AdoptRequest(BaseModel):
    priority: str = "medium"
    business_value: str = "medium"
    status: str = "active"
    tags: list[str] = Field(default_factory=list)


class OverlayUpdate(BaseModel):
    priority: str | None = None
    business_value: str | None = None
    status: str | None = None
    tags: list[str] | None = None


class NoteCreate(BaseModel):
    text: str


class OverrideRequest(BaseModel):
    """§8: user boundary override -- "treat as top-level project" or
    "attach to parent project". ("ignore" is the existing /ignore
    endpoint, not a third action here.)"""

    action: str  # "top_level" | "attach_to_parent"
    parent_id: str | None = None


class WorkspaceSummary(BaseModel):
    root: str | None
    last_scan: str | None
    projects_found: int
    projects_adopted: int
    projects_ignored: int

    model_config = ConfigDict(extra="allow")


class WorkspaceItem(BaseModel):
    """A discovered folder merged with its (possibly default) overlay."""

    id: str
    name: str
    root_path: str
    parent_path: str | None
    depth: int
    classification: str
    git_is_repo: bool
    git_branch: str | None
    git_last_commit_date: str | None
    git_is_dirty: bool | None
    health_score: int | None
    confidence_score: float
    move_risk: str
    maturity: str
    commercial_readiness: str
    recommendation: str
    last_modified: str | None

    adopted: bool
    ignored: bool
    priority: str
    business_value: str
    status: str
    tags: list[str]
    notes: list[dict]
    adopted_at: str | None

    # Sprint 3: project-boundary / hierarchy (§1 of the brief). Computed by
    # the Discovery Engine; never altered by a user override.
    item_kind: str = "unknown"
    parent_item_id: str | None = None
    project_root_id: str | None = None
    hierarchy_depth: int = 0
    is_top_level_project: bool = False
    is_nested_repository: bool = False
    is_internal_folder: bool = False
    is_excluded: bool = False
    exclusion_reason: str | None = None
    boundary_confidence: float = 0.0
    boundary_evidence: list[str] = Field(default_factory=list)

    # §8/§9: user boundary override, and the resulting effective grouping
    # (identical to the computed fields above unless an override is set).
    override_action: str | None = None
    override_parent_id: str | None = None
    effective_is_top_level_project: bool = False
    effective_parent_item_id: str | None = None

    # Sprint 5 (Project Unification): the bridge to this item's canonical
    # ROLE OS Project id -- None until the item is adopted (see
    # app.workspace.identity). AI Sessions/Timeline/Resume Work all key
    # off this, never off `id` (the discovery-item hash).
    canonical_project_id: str | None = None

    model_config = ConfigDict(extra="allow")


class UserObjective(BaseModel):
    """Hotfix (Session Intent no-action guard): the user's own answer,
    once ROLE OS could not derive a trustworthy `requested_action` from
    existing evidence. `expected_deliverable`/`completion_criteria` are
    optional -- Session Intent will still derive a grounded default for
    either one that's left blank."""

    requested_action: str
    expected_deliverable: str | None = None
    completion_criteria: str | None = None


class ResumeWorkRequest(BaseModel):
    user_objective: UserObjective | None = None


class ResumeWorkResult(BaseModel):
    """§3: the one primary action a Project page exposes. Returns data
    only -- copying the prompt, opening `url`, and navigating to the
    Cockpit all happen client-side, same as every other AI Session
    endpoint in this codebase.

    Hotfix (Session Intent no-action guard): when ROLE OS cannot derive a
    trustworthy `requested_action` from existing evidence,
    `requires_user_objective=True` is returned instead of every other
    field below -- no session is created, no prompt is built, nothing is
    touched. The frontend must prompt the user for an objective and
    re-call this endpoint with `user_objective` set."""

    item_id: str
    project_id: str
    requires_user_objective: bool = False
    project_name: str | None = None
    session_id: str | None = None
    is_new_session: bool | None = None
    prompt: str | None = None
    url: str | None = None
    used_saved_conversation: bool | None = None
    message: str | None = None
    # Sprint C7.1: why this particular AI Session was chosen to continue in
    # (latest active / pinned / preferred / newest / newly created) -- see
    # `app.project_memory.session_selection`. Never a silent decision.
    session_selection_reason: str | None = None
    # Context Sufficiency Guard (hotfix §7): whether the embedded Context
    # Package has enough real file content for a fresh, filesystem-less
    # Claude conversation to act. When `False`, no session/prompt/url is
    # built -- the frontend must show `missing_context` instead of opening
    # Claude automatically.
    context_sufficient: bool | None = None
    missing_context: list[str] | None = None
    embedded_resource_count: int | None = None
    embedded_character_count: int | None = None
    # Hotfix (Resume Work Execution Target): which environment this
    # session should resume in -- see `app.workspace.execution_target`.
    # `execution_target="user_choice"` means the frontend must let the
    # user pick from `available_assistants`, defaulting the UI to
    # `recommended_assistant`; every other value is the single, already-
    # decided target and its `working_directory` (only ever set for
    # `claude_code`).
    execution_target: str | None = None
    execution_target_reason: str | None = None
    working_directory: str | None = None
    recommended_assistant: str | None = None
    available_assistants: list[str] | None = None


class LaunchClaudeCodeRequest(BaseModel):
    """Hotfix §7: the Windows one-click launcher. `prompt` is the exact
    Resume Prompt already returned by `resume-work` -- the frontend never
    re-derives it, just hands back what it already has so the launcher
    can copy it to the clipboard. Deliberately no `working_directory`
    field here -- the launcher always re-resolves the project root
    itself, server-side, from the adopted item's own canonical root (see
    `app.workspace.service.launch_claude_code_for_item`), never from a
    client-supplied path (§7: "validated project root, adopted/canonical
    project only")."""

    prompt: str


class LaunchClaudeCodeResult(BaseModel):
    launched: bool
    working_directory: str
    # Second hotfix (launcher correctness): the exact resolved local CLI
    # path actually launched -- `None` whenever `launched` is `False`
    # (CLI not found, excluded folder, launch error). Never the bare
    # `"claude"` name; see `app.workspace.launcher.resolve_claude_cli_path`.
    executable: str | None = None
    cli_available: bool
    prompt_copied: bool
    message: str
    # Server-side proof of what the working directory actually contains
    # (§5's deterministic half of "runtime proof") -- `None` only when the
    # launch was refused before a root was even resolved (should not
    # normally happen once `working_directory` is set).
    directory_diagnostics: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")
