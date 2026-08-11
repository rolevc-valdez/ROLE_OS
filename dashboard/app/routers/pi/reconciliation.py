"""Project Identity Reconciliation API (Sprint C2.1) -- namespaced under
`/pi/projects/reconciliation`. Additive only.

`GET .../candidates` is read-only -- it only ever reports evidence, never
merges anything. `POST .../merge` is the one and only way a merge
executes, and it requires `confirm: true` explicitly (§3/§4 of the
brief: never a destructive automatic merge; ambiguous matches always go
through this same explicit Review/Merge action, just with a human deciding
which id is which after reading `GET .../candidates`' evidence).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.projects.db import MergeError
from app.projects.models import DuplicateCandidate, MergeProjectsRequest, MergeProjectsResult
from app.workspace import reconciliation

router = APIRouter(prefix="/pi/projects/reconciliation", tags=["project-intelligence"])


@router.get("/candidates", response_model=list[DuplicateCandidate])
def get_duplicate_candidates(
    settings: Settings = Depends(get_settings),
) -> list[DuplicateCandidate]:
    candidates = reconciliation.find_duplicate_candidates(settings=settings)
    return [DuplicateCandidate(**c) for c in candidates]


@router.post("/merge", response_model=MergeProjectsResult)
def merge_projects(
    payload: MergeProjectsRequest, settings: Settings = Depends(get_settings)
) -> MergeProjectsResult:
    if not payload.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm must be true -- merges are never performed automatically",
        )
    try:
        result = reconciliation.merge_projects(
            payload.surviving_id, payload.duplicate_id, settings=settings
        )
    except MergeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MergeProjectsResult(**result)
