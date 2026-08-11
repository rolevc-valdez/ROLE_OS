"""AI Launcher API (ROLE OS v1.2), namespaced under /launcher.

Additive only. Requires an active Daily Session (see `app.session`) --
there is no project/mode/objective to build a prompt from otherwise.
Performs no OS-level automation: returns the assembled prompt and the
target URL(s) for the caller (the dashboard's own JS) to copy to the
clipboard and open, client-side.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.services import launcher as launcher_service
from app.session import db as session_db
from app.session.decisions_adapter import read_recent_decisions

router = APIRouter(prefix="/launcher", tags=["launcher"])


class LaunchStart(BaseModel):
    tool: str  # "claude" | "chatgpt" | "both"


class LaunchResult(BaseModel):
    session_id: str
    tool: str
    prompt: str
    urls: list[str]


@router.post("/start", response_model=LaunchResult)
def start_launch(payload: LaunchStart, settings: Settings = Depends(get_settings)) -> LaunchResult:
    session = session_db.get_active_session(settings)
    if not session:
        raise HTTPException(
            status_code=409,
            detail="No active session. Start a session (Start My Day) before launching an AI tool.",
        )

    try:
        urls = launcher_service.resolve_launch_urls(payload.tool)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    registry_project = None
    if session.get("project_id"):
        registry_project = session_db.get_registry_project(session["project_id"], settings)

    decisions_result = read_recent_decisions(limit=3, settings=settings)

    prompt = launcher_service.build_launch_prompt(
        session=session,
        registry_project=registry_project,
        decisions=decisions_result["decisions"],
    )

    return LaunchResult(session_id=session["id"], tool=payload.tool, prompt=prompt, urls=urls)
