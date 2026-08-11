"""Tests for `app.workspace.execution_target` (hotfix: Resume Work
Execution Target). Pure, deterministic classification -- no DB, no
filesystem, no LLM call."""

from __future__ import annotations

from app.workspace.execution_target import (
    CHATGPT_WEB,
    CLAUDE_CODE,
    CLAUDE_WEB,
    USER_CHOICE,
    classify_execution_target,
    is_code_action,
)


def test_software_project_with_implementation_action_goes_to_claude_code():
    result = classify_execution_target(
        root_path="C:/Projects/ROLE Commerce Factory",
        classification="Software Project",
        git_is_repo=True,
        requested_action="Implement the missing payment adapter tests",
    )
    assert result["execution_target"] == CLAUDE_CODE
    assert result["working_directory"] == "C:/Projects/ROLE Commerce Factory"
    assert "local software repository" in result["reason"]


def test_website_project_with_debug_action_goes_to_claude_code():
    result = classify_execution_target(
        root_path="C:/Projects/RoleValdez.com",
        classification="Website",
        git_is_repo=True,
        requested_action="Debug the broken checkout redirect",
    )
    assert result["execution_target"] == CLAUDE_CODE


def test_strategy_task_on_documentation_project_goes_to_web_assistant():
    result = classify_execution_target(
        root_path="C:/Projects/role-ecosystem",
        classification="Documentation Project",
        git_is_repo=False,
        requested_action="Brainstorm the Q3 positioning narrative",
    )
    assert result["execution_target"] == CLAUDE_WEB
    assert result["working_directory"] is None
    assert CHATGPT_WEB in result["available_assistants"]


def test_missing_local_root_never_selects_claude_code():
    """A manually-created Project Intelligence record with no filesystem
    root cannot be handed to Claude Code no matter what the action says."""
    result = classify_execution_target(
        root_path=None,
        classification="Software Project",
        git_is_repo=None,
        requested_action="Implement the release checklist",
    )
    assert result["execution_target"] == CLAUDE_WEB


def test_non_software_project_stays_on_web_even_for_code_shaped_verbs():
    result = classify_execution_target(
        root_path="C:/Projects/brand-assets",
        classification="Brand / Asset Project",
        git_is_repo=False,
        requested_action="Refresh the logo pack",
    )
    assert result["execution_target"] == CLAUDE_WEB


def test_code_repository_with_ambiguous_action_offers_user_choice():
    result = classify_execution_target(
        root_path="C:/Projects/ROLE_OS",
        classification="Software Project",
        git_is_repo=True,
        requested_action="Continue this project",
    )
    assert result["execution_target"] == USER_CHOICE
    assert result["recommended_assistant"] == CLAUDE_CODE
    assert CLAUDE_CODE in result["available_assistants"]
    assert CLAUDE_WEB in result["available_assistants"]


def test_code_repository_with_no_requested_action_offers_user_choice():
    result = classify_execution_target(
        root_path="C:/Projects/ROLE_OS",
        classification="Software Project",
        git_is_repo=True,
        requested_action=None,
    )
    assert result["execution_target"] == USER_CHOICE


def test_git_repo_without_a_software_classification_still_counts_as_code_bearing():
    """A "Mixed Project" that happens to be a real git repository -- move
    risk in the other direction (never claude_web-only just because the
    Discovery Engine's classifier landed on a vaguer bucket) matters more
    than the classification label itself."""
    result = classify_execution_target(
        root_path="C:/Projects/role-mixed",
        classification="Mixed Project",
        git_is_repo=True,
        requested_action="Fix the failing build script",
    )
    assert result["execution_target"] == CLAUDE_CODE


def test_is_code_action_helper_matches_the_briefs_named_verbs():
    for action in [
        "Implement the adapter",
        "Debug the crash on startup",
        "Write and run the test suite",
        "Build the release artifact",
        "Prepare release notes",
        "Refactor the pricing module",
        "Inspect the repository for stale branches",
        "Do a code review of the PR",
    ]:
        assert is_code_action(action), action


def test_is_code_action_helper_rejects_conversational_phrasing():
    for action in [None, "", "Brainstorm marketing angles", "Discuss pricing strategy"]:
        assert not is_code_action(action)
