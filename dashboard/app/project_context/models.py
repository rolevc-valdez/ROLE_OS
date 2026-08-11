"""Pydantic response shape for `GET /project-context/*` (Sprint C1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdvisorSummaryItem(BaseModel):
    """One recommendation, normalized to a single shape regardless of
    which engine produced it (Epic 2's Advisor over manually-entered PI
    data, or the Workspace Advisor's evidence-over-discovery rules) --
    the two engines' native shapes disagree on field names
    (`priority`/`priority_score`, `confidence`/`confidence_score`,
    `recommendation`/`title`) purely by accident of when each was built,
    not because the underlying concept differs."""

    title: str
    reason: str
    evidence: list[str] = Field(default_factory=list)
    priority: int
    confidence: float
    action_link: str | None = None
    source: str  # "advisor" (Epic 2) | "workspace_advisor"


class ProjectContext(BaseModel):
    """Everything a UI screen needs to render one project. One builder
    (`app.project_context.builder.build_project_context`) produces this;
    no page should reconstruct any part of it independently.

    Sprint C1B (Rewiring): extended to a superset of every project-oriented
    screen's needs (Home, Projects, Workspace, Cockpit, Advisor, Assets) --
    see `docs/architecture` for the field-by-field mapping from each
    screen's old, independently-assembled shape into this one.
    """

    id: str
    canonical_id: str
    discovery_item_id: str | None = None
    project_id: str | None = None
    display_name: str
    root_path: str | None = None
    workspace: str

    status: str | None = None
    health: str | None = None  # "healthy" | "warning" | "critical" | None
    health_score: int | None = None
    # "discovery" (app.discovery.health, 8 signals) | "project_intelligence"
    # (app.projects.health, 6 signals) | None -- these are two distinct,
    # differently-weighted scoring algorithms for two different questions;
    # this field names which one produced `health_score` rather than
    # letting two unlabeled scores masquerade as one concept.
    health_score_source: str | None = None
    confidence: float | None = None
    move_risk: str | None = None
    classification: str | None = None
    technology_stack: list[str] = Field(default_factory=list)
    business_value: str | None = None

    git: dict[str, Any] = Field(default_factory=dict)
    commits: list[dict[str, Any]] = Field(default_factory=list)
    latest_activity: str | None = None
    latest_snapshot: dict[str, Any] | None = None
    latest_ai_session: dict[str, Any] | None = None
    next_action: dict[str, Any] | None = None

    advisor_summary: list[AdvisorSummaryItem] = Field(default_factory=list)

    assets_count: int = 0
    documents_count: int = 0
    documentation_status: str | None = None
    test_status: str | None = None
    knowledge_count: int = 0

    # Timeline = AI Sessions + Snapshots. Recent Activity = git + filesystem
    # + adoption + AI sessions/snapshots + assets. Two distinct datasets --
    # see `builder._assemble`'s docstring note. `recent_activity` is only
    # populated for a single-project fetch (cost knob); empty on list pages.
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    recent_activity: list[dict[str, Any]] = Field(default_factory=list)

    resume_state: dict[str, Any] = Field(default_factory=dict)
    data_freshness: dict[str, Any] = Field(default_factory=dict)

    # Provenance, additive -- lets a caller that already knows "this is a
    # discovered item" or "this is a purely manual project" branch without
    # re-deriving it from field presence/absence.
    item_id: str | None = None
    is_discovered: bool = False
    is_adopted: bool = False

    model_config = ConfigDict(extra="allow")
