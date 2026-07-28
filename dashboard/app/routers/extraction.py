"""Knowledge Extraction endpoints (Sprint 4), namespaced under /extraction.

Rule-based extraction only -- no AI/LLM call, no summarization, no graph,
no advisor, no recommendations. Extracts and persists Project, Person,
Task, Decision, Idea, Document, and Asset objects from imported
conversations; nothing else.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.extraction import db, service
from app.extraction.models import OBJECT_TYPES, ExtractedObject, ExtractionCounts, ExtractionRun

router = APIRouter(prefix="/extraction", tags=["extraction"])


@router.post("/conversations/{conversation_id}/run", response_model=ExtractionRun, status_code=201)
def run_extraction(conversation_id: str, settings: Settings = Depends(get_settings)) -> ExtractionRun:
    """Run (or re-run) extraction for one conversation. Safe to call
    repeatedly -- see `service.run_extraction` for the dedup/re-run
    semantics."""
    try:
        result = service.run_extraction(conversation_id, settings)
    except service.ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExtractionRun(**result)


@router.get("/conversations/{conversation_id}/objects", response_model=list[ExtractedObject])
def list_extracted_objects(
    conversation_id: str,
    object_type: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> list[ExtractedObject]:
    if object_type is not None and object_type not in OBJECT_TYPES:
        raise HTTPException(status_code=400, detail=f"object_type must be one of {OBJECT_TYPES}")
    return [ExtractedObject(**o) for o in db.list_objects(conversation_id, object_type, settings=settings)]


@router.delete("/objects/{object_id}", status_code=204)
def delete_extracted_object(object_id: str, settings: Settings = Depends(get_settings)) -> None:
    if db.get_object(object_id, settings=settings) is None:
        raise HTTPException(status_code=404, detail=f"Extracted object '{object_id}' not found")
    db.delete_object(object_id, settings=settings)


@router.get("/metrics", response_model=ExtractionCounts)
def extraction_metrics(settings: Settings = Depends(get_settings)) -> ExtractionCounts:
    counts = db.counts_by_type(settings=settings)
    return ExtractionCounts(
        project=counts.get("Project", 0),
        person=counts.get("Person", 0),
        task=counts.get("Task", 0),
        decision=counts.get("Decision", 0),
        idea=counts.get("Idea", 0),
        document=counts.get("Document", 0),
        asset=counts.get("Asset", 0),
    )


@router.get("/recent", response_model=list[ExtractedObject])
def recent_extracted_objects(
    limit: int = Query(10, ge=1, le=100), settings: Settings = Depends(get_settings)
) -> list[ExtractedObject]:
    """Most recently extracted objects across every conversation, newest
    first. Added for the Dashboard's Recent Activity (Sprint 7); reuses
    the existing `search_objects()` query unfiltered."""
    return [ExtractedObject(**o) for o in db.search_objects(limit=limit, settings=settings)]


@router.get("/runs", response_model=list[ExtractionRun])
def list_extraction_runs(
    limit: int = Query(50, ge=1, le=200), settings: Settings = Depends(get_settings)
) -> list[ExtractionRun]:
    """Most recent extraction runs across every conversation, newest
    first -- the extraction-domain analogue of `GET /import/history`.
    Added for the Dashboard's "last extraction" status (Sprint 7)."""
    return [ExtractionRun(**r) for r in db.list_recent_runs(limit=limit, settings=settings)]
