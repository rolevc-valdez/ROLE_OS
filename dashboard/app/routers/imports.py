"""ChatGPT conversation import + Conversation Explorer (Sprint B1.5)
endpoints, namespaced under /import.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from app.config import Settings, get_settings
from app.imports import db
from app.imports import service
from app.imports.models import (
    ConversationDetail,
    ConversationListResponse,
    ExplorerMetrics,
    ImportedConversation,
    ImportFacets,
    ImportRun,
)
from app.imports.parser import InvalidExportError

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/chatgpt", response_model=ImportRun, status_code=201)
async def import_chatgpt(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> ImportRun:
    raw = await file.read()
    try:
        result = service.run_import(raw, file.filename or "upload.json", settings)
    except InvalidExportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ImportRun(**result)


@router.get("/history", response_model=list[ImportRun])
def import_history(settings: Settings = Depends(get_settings)) -> list[ImportRun]:
    return [ImportRun(**run) for run in db.list_runs(settings=settings)]


@router.get("/facets", response_model=ImportFacets)
def import_facets(settings: Settings = Depends(get_settings)) -> ImportFacets:
    """Distinct source/status values actually present, so the Explorer's
    filter dropdowns are built from real data instead of a hard-coded list —
    a new provider (Claude, Gemini, Gmail, ...) shows up automatically the
    first time a conversation from it is imported."""
    return ImportFacets(**db.list_facets(settings=settings))


@router.get("/metrics", response_model=ExplorerMetrics)
def import_metrics(settings: Settings = Depends(get_settings)) -> ExplorerMetrics:
    """Explorer dashboard metrics. Only `imported_conversations` reflects a
    real, implemented feature; every other figure is intentionally 0 — this
    sprint adds no extraction, project matching, or knowledge graph linking
    for imported conversations, so there is nothing real to report yet."""
    return ExplorerMetrics(
        imported_conversations=db.count_conversations(settings=settings),
        pending_processing=0,
        processed=0,
        knowledge_objects=0,
        projects=0,
        decisions=0,
        assets=0,
    )


@router.get("/conversations", response_model=ConversationListResponse)
def list_imported_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    sort_by: str = Query("imported_at"),
    sort_dir: str = Query("desc"),
    q: str | None = Query(None),
    source: str | None = Query(None),
    status: str | None = Query(None),
    imported_after: str | None = Query(None),
    imported_before: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> ConversationListResponse:
    items, total = db.list_conversations_page(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        q=q,
        source=source,
        status=status,
        imported_after=imported_after,
        imported_before=imported_before,
        settings=settings,
    )
    return ConversationListResponse(
        items=[ImportedConversation(**c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


def _get_conversation_or_404(conversation_id: str, settings: Settings) -> dict:
    record = db.get_conversation(conversation_id, settings=settings)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found")
    return record


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_imported_conversation(conversation_id: str, settings: Settings = Depends(get_settings)) -> ConversationDetail:
    return ConversationDetail(**_get_conversation_or_404(conversation_id, settings))


@router.get("/conversations/{conversation_id}/export")
def export_imported_conversation(conversation_id: str, settings: Settings = Depends(get_settings)) -> Response:
    record = _get_conversation_or_404(conversation_id, settings)
    payload = json.dumps(record, ensure_ascii=False, indent=2)
    filename = f"{conversation_id}.json"
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_imported_conversation(conversation_id: str, settings: Settings = Depends(get_settings)) -> None:
    _get_conversation_or_404(conversation_id, settings)
    db.delete_conversation(conversation_id, settings=settings)
