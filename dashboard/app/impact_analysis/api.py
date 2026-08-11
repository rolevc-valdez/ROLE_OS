"""Impact Analysis API (Sprint C9) -- namespaced under `/impact-analysis`.
One endpoint returning a project's already-shaped `ImpactReport` -- see
`app.impact_analysis.service.get_impact_analysis` for what it composes and
why no new relationship-detection engine exists here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.impact_analysis.service import get_impact_analysis

router = APIRouter(prefix="/impact-analysis", tags=["impact-analysis"])


@router.get("/{project_id}")
def get_impact(project_id: str, settings: Settings = Depends(get_settings)) -> dict:
    report = get_impact_analysis(project_id, settings=settings)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return report
