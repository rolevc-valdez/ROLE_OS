"""Health Score endpoints.

    GET  /pi/projects/{id}/health          recompute (live) and persist this project's score
    POST /pi/health/recalculate            recompute and persist every project's score

Conversation recency is pulled from the existing knowledge database (the
same one Milestone 1's `/knowledge/{id}` reads from) for the linked
conversation ids on each project — a thin, read-only integration between
the two domains that doesn't touch the knowledge API at all.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app import db as knowledge_db
from app.config import Settings, get_settings
from app.projects import db as projects_db
from app.projects.health import compute_health_score
from app.projects.models import HealthScoreResponse

router = APIRouter(prefix="/pi", tags=["project-intelligence"])


def _conversation_dates(conversation_ids: list[str], settings: Settings) -> list[str]:
    dates: list[str] = []
    for conversation_id in conversation_ids:
        try:
            card = knowledge_db.get_card(conversation_id, settings)
        except knowledge_db.DatabaseUnavailableError:
            break  # knowledge DB not configured/available; degrade to no signal
        if card and card.get("updated"):
            dates.append(card["updated"])
    return dates


def _score_and_persist(project: dict, settings: Settings) -> dict:
    dates = _conversation_dates(project.get("conversations", []), settings)
    result = compute_health_score(project, conversation_dates=dates)
    projects_db.set_health_score(project["id"], result["score"], settings)
    return result


@router.get("/projects/{project_id}/health", response_model=HealthScoreResponse)
def get_project_health(project_id: str, settings: Settings = Depends(get_settings)) -> HealthScoreResponse:
    project = projects_db.get_project(project_id, settings)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    result = _score_and_persist(project, settings)
    return HealthScoreResponse(project_id=project_id, score=result["score"], breakdown=result["breakdown"])


@router.post("/health/recalculate")
def recalculate_all(settings: Settings = Depends(get_settings)) -> dict:
    projects = projects_db.list_projects(settings=settings)
    updated = 0
    for project in projects:
        full = projects_db.get_project(project["id"], settings)
        _score_and_persist(full, settings)
        updated += 1
    return {"updated": updated}
