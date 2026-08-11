"""Execution Target selection (hotfix, following real-world Resume Work
dogfooding on ROLE Commerce Factory).

Resume Work always opened claude.ai, even for a local software repository
that a browser-based conversation cannot inspect. This is not a Project
Memory problem -- the context package was already correct -- it is an
*execution-environment* problem: implementation/debugging/testing/release
work on a code-bearing project belongs in Claude Code, running inside the
project's own local root, not in a web tab with no filesystem access.

No new AI engine, no LLM classification, no embeddings -- this is a
deterministic decision over fields the Discovery Engine
(`app.discovery.classifier`) and Session Intent
(`app.project_memory.session_intent`) already compute.
"""

from __future__ import annotations

import re
from typing import Any

CLAUDE_CODE = "claude_code"
CLAUDE_WEB = "claude_web"
CHATGPT_WEB = "chatgpt_web"
EXTERNAL = "external"
USER_CHOICE = "user_choice"

# `app.discovery.classifier`'s own five real classifications (plus
# "Non-project"/"Unknown", neither of which is code-bearing). "Mixed
# Project" and "Brand / Asset Project" can both contain real source code
# (asset pipelines, build scripts) so they count as code-bearing too --
# `git_is_repo` is the deciding signal for those, checked separately.
_CODE_CLASSIFICATIONS = {"Software Project", "Website"}
_MAYBE_CODE_CLASSIFICATIONS = {"Mixed Project", "Brand / Asset Project"}

# Requested-action verbs the brief names explicitly (§2): implementation,
# debugging, testing, build, release, refactor, repository inspection,
# code review. Matched as whole words against the lower-cased requested
# action text -- deliberately a fixed word list, not a model call.
_CODE_ACTION_KEYWORDS = (
    "implement",
    "debug",
    "test",
    "build",
    "release",
    "refactor",
    "repository",
    "repo",
    "code review",
    "review the code",
    "review code",
    "deploy",
    "migrate",
    "wire",
    "commit",
    "reconcile",
    "resolve",
    "ship",
    "fix",
    "bug",
)
_CODE_ACTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _CODE_ACTION_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _is_code_bearing_project(classification: str | None, git_is_repo: bool | None) -> bool:
    if classification in _CODE_CLASSIFICATIONS:
        return True
    if classification in _MAYBE_CODE_CLASSIFICATIONS and git_is_repo:
        return True
    return bool(git_is_repo)


def is_code_action(requested_action: str | None) -> bool:
    """Exposed separately so callers (and tests) can reason about the
    action half of the rule on its own."""
    if not requested_action:
        return False
    return bool(_CODE_ACTION_RE.search(requested_action))


def classify_execution_target(
    *,
    root_path: str | None,
    classification: str | None,
    git_is_repo: bool | None,
    requested_action: str | None,
) -> dict[str, Any]:
    """The brief's own deterministic rule (§2/§3). Returns a dict, never a
    bare string, so the reason travels with the decision all the way to
    the UI (§8: "Reason: This session requires access to the local
    software repository.").

    `root_path` must be the project's canonical local root -- callers
    never fabricate or guess one; `None`/missing disqualifies Claude Code
    outright regardless of classification or action.
    """
    has_local_root = bool(root_path and root_path.strip())
    code_bearing = has_local_root and _is_code_bearing_project(classification, git_is_repo)
    code_action = is_code_action(requested_action)

    if code_bearing and code_action:
        return {
            "execution_target": CLAUDE_CODE,
            "reason": "This session requires access to the local software repository.",
            "working_directory": root_path,
            "recommended_assistant": None,
            "available_assistants": [CLAUDE_CODE],
        }

    if code_bearing:
        # Ambiguous: it's a real repository, but the requested action
        # reads as conversational/planning (or nothing trustworthy was
        # derived at all) -- offer a choice rather than forcing Claude
        # Code on every visit to a code project (§11: "do not force every
        # Resume Work into Claude Code").
        return {
            "execution_target": USER_CHOICE,
            "reason": (
                "This is a local software repository, but the requested action does not "
                "clearly require implementation work -- choose where to continue."
            ),
            "working_directory": root_path,
            "recommended_assistant": CLAUDE_CODE,
            "available_assistants": [CLAUDE_CODE, CLAUDE_WEB, CHATGPT_WEB],
        }

    return {
        "execution_target": CLAUDE_WEB,
        "reason": "This session is conversational/planning work -- a web assistant is sufficient.",
        "working_directory": None,
        "recommended_assistant": CLAUDE_WEB,
        "available_assistants": [CLAUDE_WEB, CHATGPT_WEB],
    }
