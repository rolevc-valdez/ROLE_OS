"""ProjectContext API (Sprint C1: Consolidation) -- namespaced under
`/project-context`. Additive only: no existing endpoint's response shape
changes. See `app/project_context/builder.py` for what this replaces.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.project_context.builder import build_project_context, build_project_contexts_for_workspace
from app.project_context.models import ProjectContext

router = APIRouter(prefix="/project-context", tags=["project-context"])


@router.get("", response_model=list[ProjectContext])
def list_project_contexts(adopted_only: bool = True):
    return build_project_contexts_for_workspace(adopted_only=adopted_only)


@router.get("/{identifier}", response_model=ProjectContext)
def get_project_context(identifier: str):
    """`identifier` may be either a Workspace discovery item id or a
    canonical/PI Project id -- tried in that order, since both are
    opaque, unstructured hash/uuid strings and there is no way to tell
    them apart by shape alone."""
    context = build_project_context(item_id=identifier)
    if context is None:
        context = build_project_context(project_id=identifier)
    if context is None:
        raise HTTPException(status_code=404, detail="no project found for this identifier")
    return context
