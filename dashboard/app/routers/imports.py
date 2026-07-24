"""ChatGPT conversation import endpoints: /import/chatgpt, /import/history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import Settings, get_settings
from app.imports import db
from app.imports import service
from app.imports.models import ImportedConversation, ImportRun
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


@router.get("/conversations", response_model=list[ImportedConversation])
def list_imported_conversations(settings: Settings = Depends(get_settings)) -> list[ImportedConversation]:
    return [ImportedConversation(**c) for c in db.list_conversations(settings=settings)]
