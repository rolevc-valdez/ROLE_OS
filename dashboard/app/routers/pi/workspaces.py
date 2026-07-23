"""Workspace endpoints: /pi/workspaces."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.projects import db
from app.projects.models import Workspace, WorkspaceCreate

router = APIRouter(prefix="/pi/workspaces", tags=["project-intelligence"])


@router.get("", response_model=list[Workspace])
def list_workspaces(settings: Settings = Depends(get_settings)) -> list[Workspace]:
    return [Workspace(**w) for w in db.list_workspaces(settings)]


@router.post("", response_model=Workspace, status_code=201)
def create_workspace(payload: WorkspaceCreate, settings: Settings = Depends(get_settings)) -> Workspace:
    existing = db.get_workspace_by_name(payload.name, settings)
    if existing:
        raise HTTPException(status_code=409, detail=f"Workspace '{payload.name}' already exists")
    created = db.create_workspace(payload.name, payload.description, settings)
    return Workspace(**created)


@router.get("/{workspace_id}", response_model=Workspace)
def get_workspace(workspace_id: str, settings: Settings = Depends(get_settings)) -> Workspace:
    workspace = db.get_workspace(workspace_id, settings)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    projects = db.list_projects(settings=settings)
    workspace["project_count"] = sum(1 for p in projects if p["workspace"] == workspace["name"])
    return Workspace(**workspace)
