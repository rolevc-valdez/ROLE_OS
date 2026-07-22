"""Project listing endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.db import DatabaseUnavailableError, list_projects
from app.models import ProjectSummary

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectSummary])
def get_projects(settings: Settings = Depends(get_settings)) -> list[ProjectSummary]:
    try:
        projects = list_projects(settings)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [ProjectSummary(**item) for item in projects]
