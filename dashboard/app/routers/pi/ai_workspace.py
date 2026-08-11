"""AI Workspace endpoints (ROLE OS v1.3): a per-project panel storing a
saved Claude/ChatGPT/Gemini conversation URL, a role, a preferred model,
and when it was last opened.

Routes:
    GET  /pi/projects/{id}/ai-workspace         current saved workspace (empty defaults if never saved)
    PUT  /pi/projects/{id}/ai-workspace         Save Conversation
    POST /pi/projects/{id}/ai-workspace/open    Open Claude / Open ChatGPT / Open Both

Reuses the existing Project Intelligence database (`role_os_projects.db`)
-- one new table, no new SQLite file, no new persisted store outside what
Project Intelligence already owns. Does not call, modify, or depend on
`/launcher/*` (the Daily Session's AI Launcher, v1.2) in any way -- a
separate feature, over separate data, with separate endpoints, per this
task's explicit "do not modify existing launcher endpoints" requirement.
No browser automation: this router only ever returns which URL to open;
opening it happens client-side (`window.open`), same as the v1.2 launcher.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.projects import db
from app.projects.models import (
    AIWorkspace,
    AIWorkspaceOpenRequest,
    AIWorkspaceOpenResponse,
    AIWorkspaceOpenResultItem,
    AIWorkspaceSave,
)

router = APIRouter(prefix="/pi/projects", tags=["project-intelligence"])

_HOMEPAGES = {"claude": "https://claude.ai", "chatgpt": "https://chatgpt.com"}
_TOOLS_FOR = {"claude": ["claude"], "chatgpt": ["chatgpt"], "both": ["claude", "chatgpt"]}


def _get_project_or_404(project_id: str, settings: Settings) -> dict:
    project = db.get_project(project_id, settings)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


def _empty_workspace(project_id: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "claude_url": "",
        "chatgpt_url": "",
        "gemini_url": "",
        "role": "",
        "preferred_model": "",
        "last_opened_at": None,
        "created_at": "",
        "updated_at": "",
    }


@router.get("/{project_id}/ai-workspace", response_model=AIWorkspace)
def get_ai_workspace(project_id: str, settings: Settings = Depends(get_settings)) -> AIWorkspace:
    _get_project_or_404(project_id, settings)
    workspace = db.get_ai_workspace(project_id, settings)
    return AIWorkspace(**(workspace or _empty_workspace(project_id)))


@router.put("/{project_id}/ai-workspace", response_model=AIWorkspace)
def save_ai_workspace(
    project_id: str, payload: AIWorkspaceSave, settings: Settings = Depends(get_settings)
) -> AIWorkspace:
    _get_project_or_404(project_id, settings)
    saved = db.save_ai_workspace(
        project_id,
        claude_url=payload.claude_url,
        chatgpt_url=payload.chatgpt_url,
        gemini_url=payload.gemini_url,
        role=payload.role,
        preferred_model=payload.preferred_model,
        settings=settings,
    )
    return AIWorkspace(**saved)


@router.post("/{project_id}/ai-workspace/open", response_model=AIWorkspaceOpenResponse)
def open_ai_workspace(
    project_id: str, payload: AIWorkspaceOpenRequest, settings: Settings = Depends(get_settings)
) -> AIWorkspaceOpenResponse:
    _get_project_or_404(project_id, settings)

    try:
        tools = _TOOLS_FOR[payload.tool]
    except KeyError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown tool '{payload.tool}'. Expected one of: claude, chatgpt, both",
        ) from None

    workspace = db.get_ai_workspace(project_id, settings) or _empty_workspace(project_id)

    results: list[AIWorkspaceOpenResultItem] = []
    any_missing = False
    for tool in tools:
        saved_url = (workspace.get(f"{tool}_url") or "").strip()
        if saved_url:
            results.append(
                AIWorkspaceOpenResultItem(tool=tool, url=saved_url, used_saved_conversation=True)
            )
        else:
            results.append(
                AIWorkspaceOpenResultItem(
                    tool=tool, url=_HOMEPAGES[tool], used_saved_conversation=False
                )
            )
            any_missing = True

    updated = db.touch_ai_workspace_last_opened(project_id, settings)

    return AIWorkspaceOpenResponse(
        project_id=project_id,
        results=results,
        any_missing=any_missing,
        last_opened_at=updated["last_opened_at"],
    )
