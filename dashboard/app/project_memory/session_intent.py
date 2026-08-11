"""Session Intent (hotfix, following real-world Resume Work dogfooding).

Project Memory already answers "what is this project?" (Project
Summary), "what's its current phase?" (Current Objective), and "where
did we leave off?" (Pending Work/Next Action) -- real-world validation
showed that even with all of that, Claude still asked "what do you want
to do with it?" because none of those sections is an *instruction*. This
module derives one, deterministically, from existing evidence only, in a
fixed priority order, and rejects anything that is really just a status/
phase description wearing an action's clothes.

No new domain: every source here is a canonical field this codebase
already computes (Daily Session, AI Session Snapshot, Next Action,
Executive Decision, Operational Intelligence) or a bounded file read
using the exact same helpers `summary.py`/`service.py` already use.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_MAX_READ_BYTES = 20_000

# The brief's own named examples of an invalid "action" -- a phase/status
# description, not an instruction -- plus a couple of equally-generic
# Operational Intelligence titles that fail the same test. Checked before
# the verb requirement below so an exact filler phrase is never rescued
# by incidentally containing an allowed verb (e.g. "Review project
# status" contains "review" but is still rejected here).
_INVALID_ACTION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"deliverables?\s+(still\s+)?match", re.IGNORECASE),
    re.compile(r"\bphase\b.{0,25}\bactive\b", re.IGNORECASE),
    re.compile(r"^continue this project$", re.IGNORECASE),
    re.compile(r"^review( the)? project( status)?$", re.IGNORECASE),
    re.compile(r"^keep the momentum going$", re.IGNORECASE),
    re.compile(r"^make progress$", re.IGNORECASE),
    re.compile(r"^continue working$", re.IGNORECASE),
)

# A candidate must contain at least one of these imperative verbs to
# count as an instruction. Deliberately excludes bare "continue"/
# "keep"/"review" as stand-alone triggers -- those are exactly the words
# that produce filler ("continue this project", "keep the momentum
# going") rather than a real instruction; "review" is still allowed when
# it's part of a longer, specific phrase that survives the reject-list
# above (e.g. "Review recent commits for consistency").
_ACTION_VERBS = (
    "implement",
    "fix",
    "update",
    "create",
    "write",
    "add",
    "remove",
    "refactor",
    "test",
    "reconcile",
    "produce",
    "resolve",
    "wire",
    "build",
    "complete",
    "finish",
    "document",
    "migrate",
    "deploy",
    "rescan",
    "import",
    "confirm",
    "commit",
    "stash",
    "consider",
    "verify",
    "review",
    "ship",
    "launch",
)
_ACTION_VERB_RE = re.compile(r"\b(" + "|".join(_ACTION_VERBS) + r")\b", re.IGNORECASE)


def is_valid_requested_action(text: str | None) -> bool:
    """The brief's own contract: never treat a phase/status row, or
    generic filler, as an action. Explainable and deterministic -- no
    hidden heuristic, just this reject-list plus a required-verb check,
    both readable top to bottom."""
    if not text or not text.strip():
        return False
    stripped = text.strip()
    for pattern in _INVALID_ACTION_PATTERNS:
        if pattern.search(stripped):
            return False
    return bool(_ACTION_VERB_RE.search(stripped))


def _find_case_insensitive(root: Path, name: str) -> Path | None:
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower() == name.lower():
                return entry
    except OSError:
        pass
    return None


def _read_text(path: Path) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(_MAX_READ_BYTES)
    except OSError:
        return None


_UNCHECKED_ITEM_RE = re.compile(r"^\s*[-*]\s*\[ \]\s*(.+)$", re.MULTILINE)


def _first_unchecked_item(root_path: str | None, filename: str) -> tuple[str, str] | None:
    """Tiers 7/8 (ROADMAP/TODO): the first unchecked checklist item --
    deliberately narrower than `discovery.next_action`'s own ROADMAP/TODO
    handling (which also accepts a heading's plain body text as a last
    resort), since a fallback this late must be a real, concrete,
    checkable item or nothing at all."""
    if not root_path:
        return None
    root = Path(root_path)
    if not root.is_dir():
        return None
    path = _find_case_insensitive(root, filename)
    if not path:
        return None
    text = _read_text(path)
    if not text:
        return None
    match = _UNCHECKED_ITEM_RE.search(text)
    if not match:
        return None
    return match.group(1).strip(), str(path)


def _daily_session_objective(
    display_name: str, settings: Any, *, active_only: bool
) -> tuple[str, str] | None:
    """Tier 1 (active) / tier 2 (any recorded session for this project,
    matched by display name -- `app.session`'s own `sessions`/
    `registry_projects` tables key by a separate, hand-seeded slug, not
    the canonical project id, so name matching is the only real join
    available; the same convention `service._current_objective` already
    established)."""
    from app.session import db as session_db

    name_lower = (display_name or "").strip().lower()
    if not name_lower:
        return None

    active = session_db.get_active_session(settings)
    if active_only:
        if (
            active
            and (active.get("project_name") or "").strip().lower() == name_lower
            and active.get("objective")
        ):
            return active["objective"], "active_daily_session"
        return None

    active_id = (active or {}).get("id")
    for session in session_db.list_sessions(limit=30, settings=settings):
        if session.get("id") == active_id:
            continue
        if (session.get("project_name") or "").strip().lower() == name_lower and session.get(
            "objective"
        ):
            return session["objective"], "daily_session_history"
    return None


def _executive_decision_action(context: dict[str, Any], settings: Any) -> tuple[str, str] | None:
    """Tier 5: Executive Decision's own Today's Plan -- only when this
    project is the one it actually recommended (its plan is meaningless
    for any other project)."""
    from app.executive_decision import get_executive_decision

    result = get_executive_decision(settings=settings)
    decision = result["decision"]
    recommended = decision.get("recommended_project")
    if not recommended or recommended.get("canonical_project_id") != context.get("id"):
        return None
    plan = decision.get("today_plan") or []
    if not plan or not plan[0].get("action"):
        return None
    return plan[0]["action"], "executive_decision.today_plan"


def resolve_requested_action(
    context: dict[str, Any],
    settings: Any,
    *,
    recommendation: dict[str, Any] | None,
    next_action_output: dict[str, Any],
    user_objective: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """The brief's own 8-tier priority chain, each candidate validated
    with `is_valid_requested_action` before being accepted -- an invalid
    candidate at any tier falls through to the next one, never gets used
    anyway. Returns `(requested_action, source)`, `(None, None)` if
    nothing in the entire chain is trustworthy (the no-action guard's
    signal to stop)."""
    if user_objective and (user_objective.get("requested_action") or "").strip():
        return user_objective["requested_action"].strip(), "user_provided"

    display_name = context.get("display_name") or ""
    root_path = context.get("root_path")
    snapshot = context.get("latest_snapshot") or {}

    candidates: list[tuple[str | None, str | None]] = []
    candidates.append(
        _daily_session_objective(display_name, settings, active_only=True) or (None, None)
    )
    candidates.append(
        _daily_session_objective(display_name, settings, active_only=False) or (None, None)
    )
    candidates.append((snapshot.get("next_prompt"), "latest_snapshot.next_prompt"))
    candidates.append(
        (
            next_action_output.get("text"),
            f"next_action ({next_action_output.get('source', 'unknown')})",
        )
    )
    candidates.append(_executive_decision_action(context, settings) or (None, None))
    candidates.append(
        (
            recommendation.get("suggested_action") if recommendation else None,
            "operational_intelligence.suggested_action",
        )
    )
    candidates.append(_first_unchecked_item(root_path, "ROADMAP.md") or (None, None))
    candidates.append(_first_unchecked_item(root_path, "TODO.md") or (None, None))

    for text, source in candidates:
        if is_valid_requested_action(text):
            return text, source
    return None, None


def resolve_expected_deliverable(
    context: dict[str, Any],
    requested_action: str,
    settings: Any,
    *,
    user_objective: dict[str, Any] | None = None,
) -> str:
    """A verifiable result, never vague filler. Prefers Executive
    Decision's own `expected_result` (Sprint C10, already tied to the
    same requested action) when this project is the one it recommended;
    otherwise a plain, honest template grounded only in the requested
    action itself -- never invented specifics no evidence supports."""
    if user_objective and (user_objective.get("expected_deliverable") or "").strip():
        return user_objective["expected_deliverable"].strip()

    from app.executive_decision import get_executive_decision

    result = get_executive_decision(settings=settings)
    decision = result["decision"]
    recommended = decision.get("recommended_project")
    if (
        recommended
        and recommended.get("canonical_project_id") == context.get("id")
        and decision.get("expected_result")
    ):
        return decision["expected_result"]

    return f"{requested_action}, completed and reflected in the repository."


def resolve_completion_criteria(
    expected_deliverable: str,
    context: dict[str, Any],
    settings: Any,
    *,
    user_objective: dict[str, Any] | None = None,
) -> str:
    if user_objective and (user_objective.get("completion_criteria") or "").strip():
        return user_objective["completion_criteria"].strip()

    from app.executive_decision import get_executive_decision

    result = get_executive_decision(settings=settings)
    decision = result["decision"]
    recommended = decision.get("recommended_project")
    checkpoint = None
    if recommended and recommended.get("canonical_project_id") == context.get("id"):
        plan = decision.get("today_plan") or []
        if plan:
            checkpoint = plan[0].get("next_checkpoint")
    checkpoint = checkpoint or "a new Session Snapshot recording the change"
    return f"Verified via {checkpoint}."


def resolve_session_intent_summary(context: dict[str, Any], requested_action: str) -> str:
    name = context.get("display_name") or "This project"
    return f"Continue work on {name}: {requested_action}"


def resolve_context_package(
    context: dict[str, Any], requested_action: str, requested_action_source: str | None
) -> dict[str, Any]:
    """Hotfix (following real-world Resume Work validation): a bounded
    list of absolute paths is provenance, not context -- a browser-based
    Claude conversation cannot read them. Delegates to
    `app.project_memory.context_package.build_context_package`, which
    reads the adopted project's own supported text files itself and
    returns bounded, redacted, deterministic excerpts of their real
    content."""
    from app.project_memory.context_package import build_context_package

    return build_context_package(
        context.get("root_path"), requested_action, requested_action_source
    )


def build_session_intent(
    context: dict[str, Any],
    settings: Any,
    *,
    recommendation: dict[str, Any] | None,
    next_action_output: dict[str, Any],
    user_objective: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """The one Session Intent builder. Returns `None` when no tier in
    `resolve_requested_action`'s priority chain produced a trustworthy
    instruction -- the caller (`app.workspace.resume.resume_work`) must
    treat that as the no-action guard: never fabricate "Continue this
    project" here, never silently proceed."""
    requested_action, source = resolve_requested_action(
        context,
        settings,
        recommendation=recommendation,
        next_action_output=next_action_output,
        user_objective=user_objective,
    )
    if not requested_action:
        return None

    expected_deliverable = resolve_expected_deliverable(
        context, requested_action, settings, user_objective=user_objective
    )
    completion_criteria = resolve_completion_criteria(
        expected_deliverable, context, settings, user_objective=user_objective
    )
    context_package = resolve_context_package(context, requested_action, source)
    return {
        "session_intent": resolve_session_intent_summary(context, requested_action),
        "requested_action": requested_action,
        "requested_action_source": source,
        "expected_deliverable": expected_deliverable,
        "completion_criteria": completion_criteria,
        "relevant_resources": context_package["resources"],
        "context_sufficient": context_package["context_sufficient"],
        "missing_context": context_package["missing_context"],
        "embedded_resource_count": context_package["embedded_resource_count"],
        "embedded_character_count": context_package["embedded_character_count"],
    }
