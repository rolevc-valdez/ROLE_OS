"""Full-text-ish search endpoint over knowledge cards."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.db import DatabaseUnavailableError, search_cards
from app.models import KnowledgeCard

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[KnowledgeCard])
def search(
    q: str = Query(..., min_length=1, description="Search term matched against title, summary, and card content"),
    limit: int = Query(50, ge=1, le=200),
    settings: Settings = Depends(get_settings),
) -> list[KnowledgeCard]:
    try:
        results = search_cards(q, settings, limit=limit)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [KnowledgeCard(**item) for item in results]
