"""Advisor API: explainable, deterministic recommendations.

Namespaced under `/advisor`, entirely additive — it introduces no changes
to any existing route (Milestone 1's knowledge API, Milestone 2's UI
endpoints, or Epic 1's `/pi/*` Project Intelligence API).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.advisor import engine
from app.advisor.models import DailyBrief, Recommendation
from app.config import Settings, get_settings

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.get("/recommendations", response_model=list[Recommendation])
def list_recommendations(
    workspace: str | None = Query(None),
    project_id: str | None = Query(None),
    recommendation_type: str | None = Query(None),
    minimum_priority_score: int | None = Query(None, ge=0, le=100),
    include_dismissed: bool = Query(False),
    settings: Settings = Depends(get_settings),
) -> list[Recommendation]:
    recs = engine.get_recommendations(
        workspace=workspace,
        project_id=project_id,
        recommendation_type=recommendation_type,
        minimum_priority_score=minimum_priority_score,
        include_dismissed=include_dismissed,
        settings=settings,
    )
    return [Recommendation(**r) for r in recs]


@router.get("/recommendations/{recommendation_id}", response_model=Recommendation)
def get_recommendation(recommendation_id: str, settings: Settings = Depends(get_settings)) -> Recommendation:
    rec = engine.get_recommendation(recommendation_id, settings)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found")
    return Recommendation(**rec)


@router.get("/daily-brief", response_model=DailyBrief)
def daily_brief(
    workspace: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> DailyBrief:
    brief = engine.generate_daily_brief(workspace=workspace, settings=settings)
    return DailyBrief(**brief)


@router.post("/recommendations/{recommendation_id}/dismiss", response_model=Recommendation)
def dismiss_recommendation(recommendation_id: str, settings: Settings = Depends(get_settings)) -> Recommendation:
    rec = engine.dismiss_recommendation(recommendation_id, settings)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found")
    return Recommendation(**rec)


@router.post("/recommendations/{recommendation_id}/complete", response_model=Recommendation)
def complete_recommendation(recommendation_id: str, settings: Settings = Depends(get_settings)) -> Recommendation:
    rec = engine.complete_recommendation(recommendation_id, settings)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Recommendation '{recommendation_id}' not found")
    return Recommendation(**rec)
