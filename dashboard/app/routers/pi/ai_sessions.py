"""AI Sessions API (ROLE OS v1.4 "Context Engine"), nested under the
existing /pi/projects/{id} prefix.

Replaces the v1.3 AI Workspace single-record-per-project model with a
collection: a project can have any number of AI Sessions, one per
assistant conversation, each optionally carrying a chain of Session
Snapshots (accomplishments / blockers / pending work / next prompt /
decisions / summary) that the Resume Engine turns into a one-click
"continue where I left off" prompt. A project's Timeline is the
snapshots + session starts across all its sessions, in order.

Routes:
    GET    /pi/projects/{id}/ai-sessions                       list (filterable: assistant, status, favorite)
    POST   /pi/projects/{id}/ai-sessions                        create
    GET    /pi/projects/{id}/ai-sessions/{session_id}            get
    PATCH  /pi/projects/{id}/ai-sessions/{session_id}             update
    DELETE /pi/projects/{id}/ai-sessions/{session_id}              delete (cascades its snapshots)
    POST   /pi/projects/{id}/ai-sessions/{session_id}/set-current   mark current for its (project, assistant) pair
    POST   /pi/projects/{id}/ai-sessions/{session_id}/open            saved conversation_url, or the assistant's homepage
    POST   /pi/projects/{id}/ai-sessions/{session_id}/snapshots        record a Session Snapshot
    GET    /pi/projects/{id}/ai-sessions/{session_id}/snapshots         list snapshots, most recent first
    GET    /pi/projects/{id}/ai-sessions/{session_id}/resume             Resume Engine: prompt + where to open it
    GET    /pi/projects/{id}/timeline                                    Project Timeline (all sessions + snapshots, in order)

This module does not modify, call, or depend on `/launcher/*` (v1.2) or
`/pi/projects/{id}/ai-workspace*` (v1.3) in any way -- both remain fully
functional and untouched; v1.3 data is copied into this collection once,
at upgrade time, by the `0001_ai_sessions_from_ai_workspace` migration
in `app.projects.db`. No browser automation: every endpoint here returns
data only; opening a URL and copying a prompt both happen client-side.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.project_memory import prompt as project_memory_prompt
from app.project_memory import service as project_memory_service
from app.projects import db
from app.projects.models import (
    AISession,
    AISessionCreate,
    AISessionOpenResult,
    AISessionResumeResult,
    AISessionSnapshot,
    AISessionSnapshotCreate,
    AISessionUpdate,
    ProjectTimelineEntry,
)
from app.services import resume as resume_service

router = APIRouter(prefix="/pi/projects", tags=["project-intelligence"])


def _get_project_or_404(project_id: str, settings: Settings) -> dict:
    project = db.get_project(project_id, settings)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


def _get_session_or_404(project_id: str, session_id: str, settings: Settings) -> dict:
    session = db.get_ai_session(session_id, settings)
    if not session or session["project_id"] != project_id:
        raise HTTPException(
            status_code=404,
            detail=f"AI Session '{session_id}' not found for project '{project_id}'",
        )
    return session


# Sprint 5: this used to be a private helper defined here; it now lives in
# `app.services.resume.resolve_conversation_url` (identical logic) so
# `app.workspace.resume`'s "Resume Work" flow can call the exact same
# resolution without duplicating the assistant-homepage table. Both call
# sites below (`/open`, `/resume`) are otherwise unchanged.
_resolve_open = resume_service.resolve_conversation_url


@router.get("/{project_id}/ai-sessions", response_model=list[AISession])
def list_ai_sessions(
    project_id: str,
    assistant: str | None = Query(None),
    status: str | None = Query(None),
    favorite: bool | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> list[AISession]:
    _get_project_or_404(project_id, settings)
    sessions = db.list_ai_sessions(
        project_id, assistant=assistant, status=status, favorite=favorite, settings=settings
    )
    return [AISession(**s) for s in sessions]


@router.post("/{project_id}/ai-sessions", response_model=AISession, status_code=201)
def create_ai_session(
    project_id: str, payload: AISessionCreate, settings: Settings = Depends(get_settings)
) -> AISession:
    _get_project_or_404(project_id, settings)
    if payload.assistant not in db.VALID_ASSISTANTS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown assistant '{payload.assistant}'. Expected one of: {', '.join(db.VALID_ASSISTANTS)}",
        )
    created = db.create_ai_session(
        project_id,
        assistant=payload.assistant,
        title=payload.title,
        conversation_url=payload.conversation_url,
        role=payload.role,
        preferred_model=payload.preferred_model,
        notes=payload.notes,
        settings=settings,
    )
    return AISession(**created)


@router.get("/{project_id}/ai-sessions/{session_id}", response_model=AISession)
def get_ai_session(
    project_id: str, session_id: str, settings: Settings = Depends(get_settings)
) -> AISession:
    return AISession(**_get_session_or_404(project_id, session_id, settings))


@router.patch("/{project_id}/ai-sessions/{session_id}", response_model=AISession)
def update_ai_session(
    project_id: str,
    session_id: str,
    payload: AISessionUpdate,
    settings: Settings = Depends(get_settings),
) -> AISession:
    _get_session_or_404(project_id, session_id, settings)
    if payload.status is not None and payload.status not in db.VALID_AI_SESSION_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown status '{payload.status}'. Expected one of: {', '.join(db.VALID_AI_SESSION_STATUSES)}",
        )
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = db.update_ai_session(session_id, patch, settings=settings)
    return AISession(**updated)


@router.delete("/{project_id}/ai-sessions/{session_id}", status_code=204)
def delete_ai_session(
    project_id: str, session_id: str, settings: Settings = Depends(get_settings)
) -> None:
    _get_session_or_404(project_id, session_id, settings)
    db.delete_ai_session(session_id, settings=settings)


@router.post("/{project_id}/ai-sessions/{session_id}/set-current", response_model=AISession)
def set_ai_session_current(
    project_id: str, session_id: str, settings: Settings = Depends(get_settings)
) -> AISession:
    _get_session_or_404(project_id, session_id, settings)
    updated = db.set_ai_session_current(session_id, settings=settings)
    return AISession(**updated)


@router.post("/{project_id}/ai-sessions/{session_id}/open", response_model=AISessionOpenResult)
def open_ai_session(
    project_id: str, session_id: str, settings: Settings = Depends(get_settings)
) -> AISessionOpenResult:
    session = _get_session_or_404(project_id, session_id, settings)
    url, used_saved, message = _resolve_open(session)
    db.touch_ai_session_last_used(session_id, settings=settings)
    return AISessionOpenResult(
        session_id=session_id, url=url, used_saved_conversation=used_saved, message=message
    )


@router.post(
    "/{project_id}/ai-sessions/{session_id}/snapshots",
    response_model=AISessionSnapshot,
    status_code=201,
)
def create_snapshot(
    project_id: str,
    session_id: str,
    payload: AISessionSnapshotCreate,
    settings: Settings = Depends(get_settings),
) -> AISessionSnapshot:
    _get_session_or_404(project_id, session_id, settings)
    snapshot = db.create_ai_session_snapshot(
        session_id,
        accomplishments=payload.accomplishments,
        blockers=payload.blockers,
        pending_work=payload.pending_work,
        next_prompt=payload.next_prompt,
        decisions=payload.decisions,
        summary=payload.summary,
        settings=settings,
    )
    return AISessionSnapshot(**snapshot)


@router.get(
    "/{project_id}/ai-sessions/{session_id}/snapshots", response_model=list[AISessionSnapshot]
)
def list_snapshots(
    project_id: str, session_id: str, settings: Settings = Depends(get_settings)
) -> list[AISessionSnapshot]:
    _get_session_or_404(project_id, session_id, settings)
    return [
        AISessionSnapshot(**s) for s in db.list_ai_session_snapshots(session_id, settings=settings)
    ]


@router.get("/{project_id}/ai-sessions/{session_id}/resume", response_model=AISessionResumeResult)
def resume_ai_session(
    project_id: str, session_id: str, settings: Settings = Depends(get_settings)
) -> AISessionResumeResult:
    """Sprint C7.1: resumes this *specific, explicitly-chosen* session --
    unlike Resume Work's own "pick the best session" flow
    (`app.workspace.resume`), the caller already decided which
    conversation. The prompt itself, though, still comes from Project
    Memory, never from the session/snapshot alone -- "AI Session never
    owns the prompt" applies here too. Skips the Operational Intelligence
    lookup (`include_operational_recommendation=False`) the same way
    `preview_resume_state` does: this is a low-level, potentially
    frequently-called per-session action (e.g. one per row in a Cockpit
    session list), not the one primary Resume Work button, so it stays
    cheap rather than paying a whole-workspace Operational Intelligence
    pass on every call."""
    session = _get_session_or_404(project_id, session_id, settings)
    memory = project_memory_service.build_project_memory(
        project_id,
        settings=settings,
        include_operational_recommendation=False,
        include_related_projects=False,
    )
    prompt = project_memory_prompt.build_resume_prompt(
        memory, session=session, session_selection_reason="explicitly selected"
    )
    url, used_saved, _ = _resolve_open(session)
    db.touch_ai_session_last_used(session_id, settings=settings)
    return AISessionResumeResult(
        session_id=session_id, prompt=prompt, url=url, used_saved_conversation=used_saved
    )


@router.get("/{project_id}/memory")
def get_project_memory(project_id: str, settings: Settings = Depends(get_settings)) -> dict:
    """Sprint C7.1: Project Memory -- the source of truth Cockpit's
    primary card (and Resume Work's prompt) both read from. AI Sessions
    remain visible below it, but only as a secondary, transport-level
    section; the project itself, not any one session, is what's being
    resumed. Sprint C8: includes a small, bounded Related Projects section
    (`include_related_projects=True`) -- still skips the Operational
    Intelligence lookup (`include_operational_recommendation=False`) the
    same as `preview_resume_state`, since that one specifically re-triggers
    a whole-workspace Epic 2 Advisor refresh; Related Projects doesn't.
    Wrapped in `request_scope()` so the Ecosystem Engine's shared-assets
    detector (a filesystem asset walk) is never repeated within this one
    request."""
    from app.assets.service import request_scope

    _get_project_or_404(project_id, settings)
    with request_scope():
        memory = project_memory_service.build_project_memory(
            project_id,
            settings=settings,
            include_operational_recommendation=False,
            include_related_projects=True,
        )
    if memory is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return memory


@router.get("/{project_id}/timeline", response_model=list[ProjectTimelineEntry])
def get_project_timeline(
    project_id: str, settings: Settings = Depends(get_settings)
) -> list[ProjectTimelineEntry]:
    _get_project_or_404(project_id, settings)
    return [
        ProjectTimelineEntry(**e) for e in db.list_project_timeline(project_id, settings=settings)
    ]
