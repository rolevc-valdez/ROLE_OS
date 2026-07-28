"""Advisor Search API (Sprint 6), namespaced under /advisor/search.

A separate router from `routers/advisor.py` (the Epic 2 recommendation
engine's router, left completely untouched) so this sprint's endpoints
are purely additive with zero risk to the existing `/advisor/*` routes,
while still living under the same `/advisor` prefix conceptually -- this
is the Advisor's search capability, not a different feature.

Keyword/partial-match search only -- no NLP, no embeddings, no semantic
search, no AI/LLM call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.advisor import search as search_module
from app.advisor.search_models import RESULT_TYPES, SearchResponse, SearchResult
from app.config import Settings, get_settings

router = APIRouter(prefix="/advisor/search", tags=["advisor"])


@router.get("", response_model=SearchResponse)
def search_knowledge(
    q: str | None = Query(None, description="Keyword to search for (partial match); omit to list all of a type"),
    type: str | None = Query(None, description=f"Restrict to one of {RESULT_TYPES}"),
    limit: int | None = Query(None, ge=1, le=500, description="Defaults to Settings.search_result_limit (Sprint 8)"),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    if type is not None and type not in RESULT_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {RESULT_TYPES}")
    effective_limit = limit if limit is not None else settings.search_result_limit
    results = search_module.search(q=q, result_type=type, limit=effective_limit, settings=settings)
    return SearchResponse(results=[SearchResult(**r) for r in results], total=len(results))


@router.get("/objects/{object_id}", response_model=SearchResult)
def get_object(object_id: str, settings: Settings = Depends(get_settings)) -> SearchResult:
    result = search_module.get_object_result(object_id, settings=settings)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Object '{object_id}' not found")
    return SearchResult(**result)


@router.get("/conversations/{conversation_id}", response_model=SearchResult)
def get_conversation(conversation_id: str, settings: Settings = Depends(get_settings)) -> SearchResult:
    result = search_module.get_conversation_result(conversation_id, settings=settings)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    return SearchResult(**result)
