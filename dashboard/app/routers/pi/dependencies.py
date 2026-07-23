"""Dependency endpoints: projects may depend on one another.

Routes:
    GET    /pi/projects/{id}/dependencies    what this project depends on
    POST   /pi/projects/{id}/dependencies    add a dependency
    DELETE /pi/projects/{id}/dependencies/{dependency_id}
    GET    /pi/projects/{id}/dependents      reverse lookup: who depends on this project
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.projects import db
from app.projects.models import Dependency, DependencyCreate

router = APIRouter(prefix="/pi/projects", tags=["project-intelligence"])


@router.get("/{project_id}/dependencies")
def list_dependencies(project_id: str, settings: Settings = Depends(get_settings)) -> list[dict]:
    if not db.get_project(project_id, settings):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return db.list_dependencies(project_id, settings)


@router.post("/{project_id}/dependencies", response_model=Dependency, status_code=201)
def create_dependency(
    project_id: str, payload: DependencyCreate, settings: Settings = Depends(get_settings)
) -> Dependency:
    created = db.create_dependency(project_id, payload.depends_on_project_id, payload.note, settings)
    if not created:
        raise HTTPException(
            status_code=400,
            detail="Both projects must exist and a project cannot depend on itself",
        )
    return Dependency(**created)


@router.delete("/{project_id}/dependencies/{dependency_id}", status_code=204)
def delete_dependency(project_id: str, dependency_id: str, settings: Settings = Depends(get_settings)) -> None:
    if not db.delete_dependency(dependency_id, settings):
        raise HTTPException(status_code=404, detail=f"Dependency '{dependency_id}' not found")


@router.get("/{project_id}/dependents")
def list_dependents(project_id: str, settings: Settings = Depends(get_settings)) -> list[dict]:
    if not db.get_project(project_id, settings):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return db.list_dependents(project_id, settings)
