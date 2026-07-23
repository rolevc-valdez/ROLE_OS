"""Data structures for the AI Advisor domain.

Two layers of "recommendation" exist on purpose:

- `RecommendationCandidate` — an internal, plain dataclass a rule function
  returns. It has no id/created_at/dismissed/completed yet; those are
  assigned by the engine at persistence time.
- `Recommendation` — the full, persisted, API-facing Pydantic model.

`RuleContext` bundles everything a rule might need about a project (its
dependencies, dependents, capabilities, linked conversation dates, and the
full project/capability universe for cross-project comparisons like
capability-reuse detection) so every rule function has an identical,
simple signature: `evaluate(project, context) -> list[RecommendationCandidate]`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

RECOMMENDATION_TYPES = (
    "continue_project",
    "unblock_dependency",
    "finish_deliverable",
    "review_decision",
    "resolve_todo",
    "reuse_capability",
    "update_stale_project",
    "review_risk",
)


@dataclass
class RuleContext:
    """Everything a rule needs about a project, beyond the project dict itself."""

    dependencies: list[dict] = field(default_factory=list)  # projects this one depends on
    dependents: list[dict] = field(default_factory=list)  # projects that depend on this one
    capabilities_provided: list[dict] = field(default_factory=list)
    capabilities_consumed: list[dict] = field(default_factory=list)
    all_capabilities: list[dict] = field(default_factory=list)  # every capability, any project
    conversation_dates: list[str] = field(default_factory=list)
    health: dict | None = None  # {"score": int, "breakdown": {...}} from the health engine
    now: datetime | None = None


@dataclass
class RecommendationCandidate:
    """What a rule produces before the engine turns it into a persisted Recommendation."""

    project_id: str
    workspace: str
    title: str
    summary: str
    recommendation_type: str
    priority_score: int
    confidence_score: int
    reason: str
    evidence: list[str]
    suggested_action: str
    estimated_effort: str
    impact: str
    ttl_days: int = 7

    def dedupe_key(self) -> str:
        return f"{self.project_id}:{self.recommendation_type}"


class Recommendation(BaseModel):
    """Full, persisted Advisor Recommendation."""

    id: str
    project_id: str
    workspace: str
    title: str
    summary: str
    recommendation_type: str
    priority_score: int
    confidence_score: int
    reason: str
    evidence: list[str]
    suggested_action: str
    estimated_effort: str
    impact: str
    created_at: str
    expires_at: str
    dismissed: bool
    completed: bool

    # "ignore" (not "allow"): internal storage details like dedupe_key must
    # not leak into the API response — the fields above are the complete,
    # documented contract.
    model_config = ConfigDict(extra="ignore")


class DailyBriefItem(BaseModel):
    project_id: str
    project_name: str
    headline: str
    explanation: str
    recommendation_id: str | None = None


class DailyBrief(BaseModel):
    generated_at: str
    greeting: str
    top_recommended_projects: list[DailyBriefItem] = Field(default_factory=list)
    critical_risks: list[DailyBriefItem] = Field(default_factory=list)
    blocked_projects: list[DailyBriefItem] = Field(default_factory=list)
    near_completion: list[DailyBriefItem] = Field(default_factory=list)
    stale_high_priority: list[DailyBriefItem] = Field(default_factory=list)
    capability_opportunities: list[DailyBriefItem] = Field(default_factory=list)
