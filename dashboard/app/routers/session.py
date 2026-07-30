"""Daily Session API (ROLE OS Dashboard MVP), namespaced under /session.

Additive only, following the same pattern as every other domain router in
this app (`/pi`, `/advisor`, `/settings`, ...): a dedicated router, a
dedicated SQLite-backed domain module (`app.session`), and zero changes to
any existing endpoint's contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.config import Settings, get_settings
from app.session import db, markdown
from app.session.decisions_adapter import read_recent_decisions
from app.session.models import (
    ClaudePrompt,
    DailyMarkdown,
    Mode,
    RecentDecisionsResponse,
    RegistryProject,
    RegistryProjectUpdate,
    SaveToVaultResult,
    Session,
    SessionComplete,
    SessionStart,
)
from app.session.modes import list_modes

router = APIRouter(prefix="/session", tags=["session"])


def _get_session_or_404(session_id: str, settings: Settings) -> dict:
    session = db.get_session(session_id, settings)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


# ---------------------------------------------------------------------------
# Operation modes (source of truth: app/session/modes.py)
# ---------------------------------------------------------------------------


@router.get("/modes", response_model=list[Mode])
def get_modes() -> list[Mode]:
    return [Mode(**m) for m in list_modes()]


# ---------------------------------------------------------------------------
# Project registry
# ---------------------------------------------------------------------------


@router.get("/registry", response_model=list[RegistryProject])
def get_registry(settings: Settings = Depends(get_settings)) -> list[RegistryProject]:
    return [RegistryProject(**p) for p in db.list_registry_projects(settings)]


@router.patch("/registry/{project_id}", response_model=RegistryProject)
def update_registry(
    project_id: str, payload: RegistryProjectUpdate, settings: Settings = Depends(get_settings)
) -> RegistryProject:
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = db.update_registry_project(project_id, patch, settings)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Registry project '{project_id}' not found")
    return RegistryProject(**updated)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@router.get("/current", response_model=Session | None)
def get_current_session(settings: Settings = Depends(get_settings)) -> Session | None:
    active = db.get_active_session(settings)
    return Session(**active) if active else None


@router.get("/recent", response_model=list[Session])
def get_recent_sessions(
    limit: int = 10, settings: Settings = Depends(get_settings)
) -> list[Session]:
    return [Session(**s) for s in db.list_sessions(limit=limit, settings=settings)]


@router.get("/{session_id}", response_model=Session)
def get_session(session_id: str, settings: Settings = Depends(get_settings)) -> Session:
    return Session(**_get_session_or_404(session_id, settings))


@router.post("/start", response_model=Session, status_code=201)
def start_session(payload: SessionStart, settings: Settings = Depends(get_settings)) -> Session:
    for field_name, value in (
        ("project_name", payload.project_name),
        ("mode", payload.mode),
        ("objective", payload.objective),
        ("expected_result", payload.expected_result),
        ("date", payload.date),
    ):
        if not value or not value.strip():
            raise HTTPException(status_code=422, detail=f"'{field_name}' is required")

    try:
        created = db.start_session(
            date=payload.date,
            project_id=payload.project_id,
            project_name=payload.project_name,
            mode=payload.mode,
            objective=payload.objective,
            expected_result=payload.expected_result,
            notes=payload.notes,
            settings=settings,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Session(**created)


@router.post("/{session_id}/complete", response_model=Session)
def complete_session(
    session_id: str, payload: SessionComplete, settings: Settings = Depends(get_settings)
) -> Session:
    _get_session_or_404(session_id, settings)
    updated = db.complete_session(
        session_id,
        completed_work=payload.completed_work,
        decisions=payload.decisions,
        blockers=payload.blockers,
        next_step=payload.next_step,
        settings=settings,
    )
    return Session(**updated)


# ---------------------------------------------------------------------------
# Generated artifacts
# ---------------------------------------------------------------------------


@router.get("/{session_id}/prompt", response_model=ClaudePrompt)
def get_claude_prompt(session_id: str, settings: Settings = Depends(get_settings)) -> ClaudePrompt:
    session = _get_session_or_404(session_id, settings)
    prompt = markdown.build_claude_prompt(
        mode=session["mode"],
        project_name=session["project_name"],
        objective=session["objective"],
        expected_result=session["expected_result"],
    )
    return ClaudePrompt(prompt=prompt)


@router.get("/{session_id}/markdown", response_model=DailyMarkdown)
def get_daily_markdown(
    session_id: str, settings: Settings = Depends(get_settings)
) -> DailyMarkdown:
    session = _get_session_or_404(session_id, settings)
    return DailyMarkdown(
        filename=markdown.daily_markdown_filename(session),
        markdown=markdown.build_daily_markdown(session),
    )


@router.get("/{session_id}/markdown/download")
def download_daily_markdown(
    session_id: str, settings: Settings = Depends(get_settings)
) -> Response:
    session = _get_session_or_404(session_id, settings)
    body = markdown.build_daily_markdown(session)
    filename = markdown.daily_markdown_filename(session)
    return Response(
        content=body,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/vault/config")
def get_vault_config(settings: Settings = Depends(get_settings)) -> dict:
    directory = settings.obsidian_daily_notes_dir
    return {
        "configured": bool(directory),
        "directory": directory or None,
    }


@router.post("/{session_id}/save-to-vault", response_model=SaveToVaultResult)
def save_to_vault(session_id: str, settings: Settings = Depends(get_settings)) -> SaveToVaultResult:
    """Optionally writes the generated Markdown record directly into the
    configured Obsidian Daily Notes folder. Never guesses or hardcodes a
    vault path -- only acts when `ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR` is set
    and points at an existing directory; otherwise reports why it didn't
    write anything instead of failing the request.
    """
    session = _get_session_or_404(session_id, settings)
    directory = settings.obsidian_daily_notes_dir

    if not directory:
        return SaveToVaultResult(
            saved=False, path=None, reason="ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR is not configured"
        )

    from pathlib import Path

    target_dir = Path(directory)
    if not target_dir.is_dir():
        return SaveToVaultResult(
            saved=False, path=str(target_dir), reason="Configured directory does not exist"
        )

    target_path = target_dir / markdown.daily_markdown_filename(session)
    try:
        target_path.write_text(markdown.build_daily_markdown(session), encoding="utf-8")
    except OSError as exc:
        return SaveToVaultResult(saved=False, path=str(target_path), reason=str(exc))

    return SaveToVaultResult(saved=True, path=str(target_path))


# ---------------------------------------------------------------------------
# Recent ecosystem decisions
# ---------------------------------------------------------------------------


@router.get("/decisions/recent", response_model=RecentDecisionsResponse)
def get_recent_decisions(
    limit: int = 5, settings: Settings = Depends(get_settings)
) -> RecentDecisionsResponse:
    return RecentDecisionsResponse(**read_recent_decisions(limit=limit, settings=settings))
