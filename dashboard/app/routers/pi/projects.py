"""Project endpoints: /pi/projects (create/list/get/update/delete) plus
conversation and related-project links.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.projects import db
from app.projects.models import (
    ConversationLink,
    Project,
    ProjectCreate,
    ProjectSummary,
    ProjectUpdate,
    RelatedProjectLink,
)

router = APIRouter(prefix="/pi/projects", tags=["project-intelligence"])


def _get_or_404(project_id: str, settings: Settings) -> dict:
    project = db.get_project(project_id, settings)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    workspace: str | None = Query(None),
    status: str | None = Query(None),
    tag: str | None = Query(None),
    priority: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> list[ProjectSummary]:
    projects = db.list_projects(workspace=workspace, status=status, tag=tag, priority=priority, settings=settings)
    return [ProjectSummary(**p) for p in projects]


@router.post("", response_model=Project, status_code=201)
def create_project(payload: ProjectCreate, settings: Settings = Depends(get_settings)) -> Project:
    created = db.create_project(
        name=payload.name,
        workspace=payload.workspace,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        tags=payload.tags,
        owner=payload.owner,
        settings=settings,
    )
    return Project(**created)


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str, settings: Settings = Depends(get_settings)) -> Project:
    return Project(**_get_or_404(project_id, settings))


@router.patch("/{project_id}", response_model=Project)
def update_project(project_id: str, payload: ProjectUpdate, settings: Settings = Depends(get_settings)) -> Project:
    _get_or_404(project_id, settings)
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = db.update_project(project_id, patch, settings)
    return Project(**updated)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, settings: Settings = Depends(get_settings)) -> None:
    _get_or_404(project_id, settings)
    db.delete_project(project_id, settings)


@router.get("/{project_id}/conversations", response_model=list[str])
def list_conversations(project_id: str, settings: Settings = Depends(get_settings)) -> list[str]:
    project = _get_or_404(project_id, settings)
    return project["conversations"]


@router.post("/{project_id}/conversations", status_code=201)
def link_conversation(project_id: str, payload: ConversationLink, settings: Settings = Depends(get_settings)) -> dict:
    _get_or_404(project_id, settings)
    result = db.link_conversation(project_id, payload.conversation_id, settings)
    return result


@router.delete("/{project_id}/conversations/{conversation_id}", status_code=204)
def unlink_conversation(project_id: str, conversation_id: str, settings: Settings = Depends(get_settings)) -> None:
    _get_or_404(project_id, settings)
    if not db.unlink_conversation(project_id, conversation_id, settings):
        raise HTTPException(status_code=404, detail="Conversation not linked to this project")


@router.get("/{project_id}/related_projects", response_model=list[str])
def list_related_projects(project_id: str, settings: Settings = Depends(get_settings)) -> list[str]:
    project = _get_or_404(project_id, settings)
    return project["related_projects"]


@router.post("/{project_id}/related_projects", status_code=201)
def link_related_project(
    project_id: str, payload: RelatedProjectLink, settings: Settings = Depends(get_settings)
) -> dict:
    _get_or_404(project_id, settings)
    _get_or_404(payload.project_id, settings)
    return db.link_related_project(project_id, payload.project_id, settings)


@router.delete("/{project_id}/related_projects/{related_project_id}", status_code=204)
def unlink_related_project(
    project_id: str, related_project_id: str, settings: Settings = Depends(get_settings)
) -> None:
    _get_or_404(project_id, settings)
    if not db.unlink_related_project(project_id, related_project_id, settings):
        raise HTTPException(status_code=404, detail="Related project link not found")
