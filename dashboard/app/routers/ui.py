"""Server-rendered UI routes for the ROLE OS Dashboard.

This router only serves the HTML page and a couple of small, additive JSON
endpoints (`/ui/recent`, `/ui/timeline`) used by the page's own JavaScript.
It does not modify or wrap the existing public API endpoints defined in
`health.py`, `projects.py`, `search.py`, and `knowledge.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates

from app.config import Settings, get_settings
from app.db import DatabaseUnavailableError, recent_cards, timeline
from app.models import KnowledgeCard, TimelineEntry

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory=str(get_settings().templates_dir))


@router.get("/", include_in_schema=False)
def dashboard_page(request: Request, settings: Settings = Depends(get_settings)):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"app_name": settings.app_name, "app_version": settings.app_version},
    )


@router.get("/ui/recent", response_model=list[KnowledgeCard])
def ui_recent(
    limit: int = Query(10, ge=1, le=100),
    settings: Settings = Depends(get_settings),
) -> list[KnowledgeCard]:
    try:
        cards = recent_cards(settings, limit=limit)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [KnowledgeCard(**item) for item in cards]


@router.get("/ui/timeline", response_model=list[TimelineEntry])
def ui_timeline(
    limit: int = Query(200, ge=1, le=1000),
    settings: Settings = Depends(get_settings),
) -> list[TimelineEntry]:
    try:
        entries = timeline(settings, limit=limit)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [TimelineEntry(**item) for item in entries]
