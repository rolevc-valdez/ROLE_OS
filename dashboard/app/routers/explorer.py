"""Explorer 2.0 API (Sprint C3) -- namespaced under `/explorer`. Additive
only; the existing Conversation Explorer endpoints under `/import/*` are
untouched (this is a separate, broader search surface, not a replacement
for that specific ChatGPT-conversation browser).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.explorer.service import RESULT_TYPES, project_hub, search

router = APIRouter(prefix="/explorer", tags=["explorer"])


@router.get("/search")
def explorer_search(
    q: str = Query("", description="Search query; empty returns a bounded browse of everything"),
    types: list[str] | None = Query(None, description="Restrict to these result types"),
):
    if types:
        unknown = [t for t in types if t not in RESULT_TYPES]
        if unknown:
            raise HTTPException(status_code=400, detail=f"unknown result type(s): {unknown}")
    return search(q, types=types)


@router.get("/project/{project_id}")
def explorer_project_hub(project_id: str):
    hub = project_hub(project_id)
    if hub is None:
        raise HTTPException(status_code=404, detail="project not found")
    return hub
