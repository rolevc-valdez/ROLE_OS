"""The one Resume Prompt builder. Project Memory owns the prompt -- the AI
Session never does; `session`/`session_selection_reason` here are only
included as the "Conversation:" section (where to continue, and why that
conversation was picked), never as a source for any other section.

Every prompt begins with exactly these eight sections, in this order --
`Conversation:` is deliberately not from the session's own snapshot/title
data (that would put the AI Session back in charge of the prompt); it
only ever names *which* conversation to continue in and why.

Hotfix (following real-world Resume Work validation): a fresh Claude
conversation given only the original seven sections still had to ask
"What is this project?" before "Current Objective"/"Pending Work"/"Next
Action" meant anything to it -- none of those sections ever actually says
what the project IS. `Project Summary` (bounded to 150 words, see
`app.project_memory.summary`) now answers that question first, directly
after the project's name and before anything asking "what should we do."

Second hotfix (following further real-world dogfooding): even with full
project identity and memory, Claude still asked "what do you want to do
with it?" -- context alone is not an instruction. The prompt now ends
with a Session Intent block (see `app.project_memory.session_intent`):
Session Intent, Requested Action, Expected Deliverable, Completion
Criteria, Relevant Context, and a fixed Execution Instructions checklist.
`memory["session_intent"]` is only ever `None` when the no-action guard
already caught it upstream (`app.workspace.resume` refuses to call this
function at all in that case) -- but this function stays honest even if
called directly with `session_intent` missing, rather than assuming that
never happens.

Third hotfix (following real-world dogfooding of a *fresh* Claude web
conversation): "Relevant Resources" used to be a bare list of absolute
Windows paths, with an instruction to "read" them. A browser-based Claude
conversation has no filesystem access, so it correctly refused --
"I can't reach that file path." Local paths are provenance metadata only
now; the actual file content Claude needs is embedded directly, as bounded
excerpts, in the "Relevant Context" block below (see
`app.project_memory.context_package`). The Execution Instructions never
tell Claude to go read anything local.

Fourth hotfix (Execution Target): the third hotfix's "no filesystem
access" framing is only true for a web assistant -- Claude Code runs
*inside* the project's own local root (see `app.workspace.
execution_target`/`app.workspace.launcher`), so telling it the same "you
do not have direct access" line would be actively wrong. `execution_
target` (one of `app.workspace.execution_target`'s constants; `None`
treated the same as the web case) now selects between two Execution
Instructions blocks: the existing filesystem-less one for a web assistant,
and a Claude Code variant that tells it to inspect the repository
directly and verify the supplied context against it, never claiming it
lacks local access.
"""

from __future__ import annotations

from typing import Any

# Deliberately the literal value of `app.workspace.execution_target.
# CLAUDE_CODE`, not imported -- this module must stay a pure, dependency-
# free string builder (see `test_prompt_never_calls_any_external_api`),
# never importing another `app` package just to read one constant.
_CLAUDE_CODE_TARGET = "claude_code"

_NONE_RECORDED = "None recorded."

_WEB_EXECUTION_INSTRUCTIONS = (
    "Execution Instructions:\n"
    "- Do not ask which project or thread this is.\n"
    "- Use the embedded excerpts above as the authoritative working context.\n"
    "- The local paths shown are provenance references only -- you do not have "
    "direct access to them; do not claim to read them.\n"
    "- Do not ask the user to upload or paste a file whose excerpt is already "
    "embedded above.\n"
    "- If essential information is still absent, identify the exact missing "
    "content rather than asking what the project is.\n"
    "- Execute the Requested Action when the embedded context is sufficient.\n"
    "- Preserve existing architecture and decisions.\n"
    "- Do not invent repository state or file contents.\n"
    "- When finished, report files changed, tests performed, result, and next action."
)

_CLAUDE_CODE_EXECUTION_INSTRUCTIONS = (
    "Execution Instructions:\n"
    "- You are running inside the project's local repository. Verify the supplied "
    "context against the actual repository before making changes.\n"
    "- Do not ask which project or thread this is.\n"
    "- The embedded excerpts above are a bounded summary, not the full repository -- "
    "inspect source files, tests, configuration, and Git state directly rather than "
    "asking the user to upload or paste them.\n"
    "- If essential information is still absent after inspecting the repository, "
    "identify the exact missing content rather than asking what the project is.\n"
    "- Execute the Requested Action when the repository confirms enough context.\n"
    "- Preserve existing architecture and decisions.\n"
    "- Do not invent repository state or file contents.\n"
    "- When finished, report files changed, tests performed, result, and next action."
)


def _render_resource(index: int, resource: dict[str, Any]) -> str:
    lines = [
        f"[Resource {index}]",
        f"Name: {resource.get('resource_name')}",
        f"Path: {resource.get('relative_path')}",
    ]
    if resource.get("selected_heading"):
        lines.append(f"Section: {resource['selected_heading']}")
    lines.append(f"Reason: {resource.get('excerpt_reason') or 'Relevant to the requested action.'}")
    if resource.get("sensitive_content_redacted"):
        lines.append("Note: sensitive content was redacted from this excerpt.")
    if resource.get("omitted_character_count"):
        lines.append(f"Note: {resource['omitted_character_count']} additional characters omitted.")
    lines.append("Excerpt:")
    lines.append(resource.get("excerpt") or "")
    return "\n".join(lines)


def build_resume_prompt(
    memory: dict[str, Any],
    *,
    session: dict[str, Any] | None = None,
    session_selection_reason: str | None = None,
    execution_target: str | None = None,
) -> str:
    next_action = memory.get("next_action") or {}
    recommendation = memory.get("operational_recommendation")

    if recommendation:
        operational_line = (
            f"{recommendation['recommendation']} -- {recommendation['reason']} "
            f"(Benefit: {recommendation['expected_benefit']})"
        )
    else:
        operational_line = "No active recommendation for this project right now."

    if session:
        title = session.get("title") or "(untitled session)"
        assistant = session.get("assistant") or "unknown assistant"
        conversation_line = f"{title} ({assistant})"
        if session_selection_reason:
            conversation_line += f" -- selected: {session_selection_reason}"
    else:
        conversation_line = "New conversation -- no prior AI session exists for this project yet."

    project_summary = memory.get("project_summary") or {}

    sections = [
        f"Project:\n{memory['project_name']}",
        f"Project Summary:\n{project_summary.get('text') or _NONE_RECORDED}",
        f"Current Objective:\n{memory['current_objective']}",
        f"Where We Left Off:\n{memory['where_we_left_off']}",
        f"Pending Work:\n{memory.get('pending_work') or _NONE_RECORDED}",
        f"Next Action:\n{next_action.get('text') or _NONE_RECORDED}",
        f"Operational Recommendation:\n{operational_line}",
        f"Conversation:\n{conversation_line}",
    ]

    session_intent = memory.get("session_intent")
    if session_intent:
        resources = session_intent.get("relevant_resources") or []
        if resources:
            resources_block = "\n\n".join(
                _render_resource(i, r) for i, r in enumerate(resources, start=1)
            )
        else:
            resources_block = "None recorded."
        sections.append(f"Session Intent:\n{session_intent['session_intent']}")
        sections.append(f"Requested Action:\n{session_intent['requested_action']}")
        sections.append(f"Expected Deliverable:\n{session_intent['expected_deliverable']}")
        sections.append(f"Completion Criteria:\n{session_intent['completion_criteria']}")
        sections.append(f"Relevant Context:\n{resources_block}")
        sections.append(
            _CLAUDE_CODE_EXECUTION_INSTRUCTIONS
            if execution_target == _CLAUDE_CODE_TARGET
            else _WEB_EXECUTION_INSTRUCTIONS
        )

    return "\n\n".join(sections)
