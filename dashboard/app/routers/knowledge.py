"""Single knowledge card lookup endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.db import DatabaseUnavailableError, get_card
from app.models import KnowledgeCard

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/{card_id}", response_model=KnowledgeCard)
def get_knowledge_card(card_id: str, settings: Settings = Depends(get_settings)) -> KnowledgeCard:
    try:
        card = get_card(card_id, settings)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if card is None:
        raise HTTPException(status_code=404, detail=f"Knowledge card '{card_id}' not found")
    return KnowledgeCard(**card)
