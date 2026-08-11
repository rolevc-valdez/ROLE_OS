"""Project Ecosystem API (Sprint C8) -- namespaced under `/project-
ecosystem`. One endpoint returning a project's already-shaped ecosystem
view -- see `app.project_ecosystem.service.get_project_ecosystem` for what
it composes and why no new relationship-detection engine exists here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.project_ecosystem.service import get_project_ecosystem

router = APIRouter(prefix="/project-ecosystem", tags=["project-ecosystem"])


@router.get("/{project_id}")
def get_ecosystem(project_id: str, settings: Settings = Depends(get_settings)) -> dict:
    ecosystem = get_project_ecosystem(project_id, settings=settings)
    if ecosystem is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return ecosystem
