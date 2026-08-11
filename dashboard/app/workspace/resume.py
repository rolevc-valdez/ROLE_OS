"""Resume Work (Sprint 5 §3; redesigned Sprint C7.1): the single primary
action every Project page exposes.

Real-world validation exposed a product flaw in the original design:
Resume Work resumed an *AI Session* -- if the session/snapshot were thin,
the copied prompt was too, and the assistant had to ask what the project
even was. The corrected flow:

    Project -> Project Memory -> Resume Prompt -> locate best AI Session
    -> open conversation -> copy prompt

Project Memory (`app.project_memory`) is the source of truth for the
prompt; the AI Session is only ever the transport (where the conversation
happens to live). If no session exists yet, one is created automatically,
named `<Project Name> -- <Objective>` (never "Resume Work"/"Untitled"/
"Session 1" -- see `app.project_memory.naming`), and associated to the
project -- "starting a session must require zero manual creation" still
holds, it just no longer means the session drives the prompt.
"""

from __future__ import annotations

from typing import Any

from app.assets.service import request_scope
from app.config import Settings, get_settings
from app.project_memory.naming import needs_retitle, session_title_for
from app.project_memory.prompt import build_resume_prompt
from app.project_memory.service import build_project_memory
from app.project_memory.session_selection import select_best_session
from app.projects import db as projects_db
from app.services import resume as resume_service
from app.workspace.execution_target import classify_execution_target

DEFAULT_ASSISTANT = "claude"


def _resolve_execution_target(memory: dict[str, Any]) -> dict[str, Any]:
    """Hotfix (Resume Work Execution Target): derived from fields Project
    Memory already carries -- no second lookup, no new domain. See
    `app.workspace.execution_target` for the deterministic rule."""
    session_intent = memory.get("session_intent") or {}
    return classify_execution_target(
        root_path=memory.get("root_path"),
        classification=memory.get("classification"),
        git_is_repo=(memory.get("git") or {}).get("is_repo"),
        requested_action=session_intent.get("requested_action"),
    )


def resume_work(
    canonical_project_id: str,
    settings: Settings | None = None,
    *,
    user_objective: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """`user_objective` (optional `{requested_action, expected_deliverable,
    completion_criteria}`) is the no-action guard's own answer -- pass it
    once the user has supplied one via the Cockpit prompt. Without it, if
    Session Intent's own priority chain (see `app.project_memory.
    session_intent`) cannot derive a trustworthy instruction, this
    function refuses to create a session, touch any existing one, or
    build a prompt at all -- it returns `requires_user_objective: True`
    instead. Never silently falls back to "Continue this project"."""
    settings = settings or get_settings()
    project = projects_db.get_project(canonical_project_id, settings)
    if project is None:
        return None

    # Sprint C8: Project Memory's Related Projects section runs the
    # Ecosystem Engine's shared-assets detector (a filesystem asset walk,
    # same one Dashboard/Mission Control already share one walk for per
    # request) -- `request_scope()` keeps this one Resume Work click to a
    # single walk per adopted project, not a repeat of an already-run one.
    with request_scope():
        memory = build_project_memory(
            canonical_project_id, settings=settings, user_objective=user_objective
        )

    session_intent = memory.get("session_intent")
    if session_intent is None:
        return {
            "project_id": canonical_project_id,
            "requires_user_objective": True,
            "project_name": memory["project_name"],
            "message": (
                "ROLE OS could not derive a trustworthy next action for "
                f"{memory['project_name']} from existing evidence -- what do you want "
                "to accomplish in this work session?"
            ),
        }

    # Context Sufficiency Guard (hotfix §7): a fresh Claude web conversation
    # has no filesystem access -- if the Context Package embedded zero
    # resources, sending it anyway just reproduces "I can't reach that file
    # path." Refuse to open/copy a prompt that knowingly requires
    # inaccessible local content; surface exactly what's missing instead.
    if not session_intent.get("context_sufficient", True):
        return {
            "project_id": canonical_project_id,
            "requires_user_objective": False,
            "context_sufficient": False,
            "missing_context": session_intent.get("missing_context") or [],
            "embedded_resource_count": session_intent.get("embedded_resource_count", 0),
            "embedded_character_count": session_intent.get("embedded_character_count", 0),
            "project_name": memory["project_name"],
            "message": (
                f"ROLE OS could not gather enough local project context for "
                f"{memory['project_name']} to hand off to a fresh conversation -- "
                "select additional project files or provide more detail."
            ),
        }

    sessions = projects_db.list_ai_sessions(canonical_project_id, settings=settings)
    session, selection_reason = select_best_session(sessions)
    is_new_session = False

    if session is None:
        title = session_title_for(memory["project_name"], memory["current_objective"])
        session = projects_db.create_ai_session(
            canonical_project_id,
            assistant=DEFAULT_ASSISTANT,
            title=title,
            settings=settings,
        )
        is_new_session = True
        selection_reason = "no existing session -- created a new one"
    elif needs_retitle(session.get("title")):
        # Self-heals a session created under the old session-centric flow
        # (literally titled "Resume Work") into the new naming convention
        # the moment it's next resumed -- never left permanently mis-named.
        new_title = session_title_for(memory["project_name"], memory["current_objective"])
        session = projects_db.update_ai_session(
            session["id"], {"title": new_title}, settings=settings
        )

    execution_target = _resolve_execution_target(memory)

    projects_db.set_ai_session_current(session["id"], settings=settings)
    prompt = build_resume_prompt(
        memory,
        session=session,
        session_selection_reason=selection_reason,
        execution_target=execution_target["execution_target"],
    )
    url, used_saved_conversation, message = resume_service.resolve_conversation_url(session)
    projects_db.touch_ai_session_last_used(session["id"], settings=settings)

    return {
        "project_id": canonical_project_id,
        "requires_user_objective": False,
        "context_sufficient": True,
        "missing_context": session_intent.get("missing_context") or [],
        "embedded_resource_count": session_intent.get("embedded_resource_count", 0),
        "embedded_character_count": session_intent.get("embedded_character_count", 0),
        "session_id": session["id"],
        "is_new_session": is_new_session,
        "prompt": prompt,
        "url": url,
        "used_saved_conversation": used_saved_conversation,
        "message": message,
        "session_selection_reason": selection_reason,
        "execution_target": execution_target["execution_target"],
        "execution_target_reason": execution_target["reason"],
        "working_directory": execution_target["working_directory"],
        "recommended_assistant": execution_target["recommended_assistant"],
        "available_assistants": execution_target["available_assistants"],
    }


def preview_resume_state(
    canonical_project_id: str | None, settings: Settings | None = None
) -> dict[str, Any]:
    """A read-only preview of exactly what `resume_work` above would do,
    without doing any of it -- no session creation, no retitle, no
    `set_ai_session_current`, no `touch_ai_session_last_used`.

    This exists because `ProjectContext` is built on every Home/Projects/
    Workspace page load (and by tests, and by anything else that asks "what
    is this project's state"), so it must stay cheap: Project Memory is
    still built (so the preview prompt is real), but *without* the
    Operational Intelligence lookup (`include_operational_recommendation=
    False`) -- that's a whole-workspace pass, appropriate for an actual
    Resume Work click, not for every page load. Returns "Not yet defined"
    (`None`) fields, honestly, for a project with no canonical identity yet.
    """
    settings = settings or get_settings()
    if not canonical_project_id:
        return {
            "available": False,
            "session_id": None,
            "is_new_session_needed": None,
            "has_snapshot": False,
            "prompt": None,
            "url": None,
            "message": "Not yet defined -- project has no canonical identity yet (adopt it first)",
        }

    project = projects_db.get_project(canonical_project_id, settings)
    if project is None:
        return {
            "available": False,
            "session_id": None,
            "is_new_session_needed": None,
            "has_snapshot": False,
            "prompt": None,
            "url": None,
            "message": "Not yet defined -- no such project",
        }

    memory = build_project_memory(
        canonical_project_id,
        settings=settings,
        include_operational_recommendation=False,
        include_related_projects=False,
    )
    sessions = projects_db.list_ai_sessions(canonical_project_id, settings=settings)
    session, selection_reason = select_best_session(sessions)
    execution_target = _resolve_execution_target(memory)

    prompt = build_resume_prompt(
        memory,
        session=session,
        session_selection_reason=selection_reason if session else None,
        execution_target=execution_target["execution_target"],
    )
    url, message = None, None
    if session:
        url, _used_saved_conversation, message = resume_service.resolve_conversation_url(session)
    else:
        message = "Resuming will start a new AI Session -- none exists yet"

    return {
        "available": True,
        "session_id": session["id"] if session else None,
        "is_new_session_needed": session is None,
        "has_snapshot": memory.get("latest_snapshot") is not None,
        "prompt": prompt,
        "url": url,
        "message": message,
        "execution_target": execution_target["execution_target"],
        "execution_target_reason": execution_target["reason"],
        "working_directory": execution_target["working_directory"],
        "recommended_assistant": execution_target["recommended_assistant"],
        "available_assistants": execution_target["available_assistants"],
    }
