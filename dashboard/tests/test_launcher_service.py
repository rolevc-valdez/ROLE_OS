"""Unit tests for the AI Launcher service (app.services.launcher): pure
prompt assembly and tool-to-URL resolution. No AI/LLM call, no clipboard,
no browser -- this module only returns text and URLs.
"""

from __future__ import annotations

import pytest
from app.services.launcher import build_launch_prompt, resolve_launch_urls


def _session(**overrides):
    payload = {
        "mode": "BUILD",
        "project_name": "ROLE OS",
        "objective": "Ship the AI Launcher",
    }
    payload.update(overrides)
    return payload


def test_resolve_launch_urls_claude():
    assert resolve_launch_urls("claude") == ["https://claude.ai"]


def test_resolve_launch_urls_chatgpt():
    assert resolve_launch_urls("chatgpt") == ["https://chatgpt.com"]


def test_resolve_launch_urls_both():
    urls = resolve_launch_urls("both")
    assert "https://claude.ai" in urls
    assert "https://chatgpt.com" in urls
    assert len(urls) == 2


def test_resolve_launch_urls_unknown_tool_raises():
    with pytest.raises(ValueError, match="Unknown AI tool"):
        resolve_launch_urls("bing")


def test_build_launch_prompt_matches_required_structure():
    prompt = build_launch_prompt(
        session=_session(),
        registry_project={"milestone": "Ship v1.2", "next_action": "Wire the UI"},
        decisions=[
            {"id": "D-001", "date": "2026-07-30", "decision": "Do the thing.", "status": "Accepted"}
        ],
    )
    assert prompt.startswith("Initialize using SYSTEM.md.")
    assert "Mode:\nBUILD" in prompt
    assert "Project:\nROLE OS" in prompt
    assert "Today's Objective:\nShip the AI Launcher" in prompt
    assert "Pending Tasks:\n- Current milestone: Ship v1.2\n- Next action: Wire the UI" in prompt
    assert "Recent Decisions:\n- D-001 (2026-07-30): Do the thing." in prompt
    assert "1. Summarize current project status." in prompt
    assert "5. Wait for approval before making destructive or architectural changes." in prompt


def test_build_launch_prompt_no_linked_project():
    prompt = build_launch_prompt(session=_session(), registry_project=None, decisions=[])
    assert "Pending Tasks:\n(none recorded -- session has no linked project)" in prompt
    assert "Recent Decisions:\n(none available)" in prompt


def test_build_launch_prompt_linked_project_with_no_milestone_or_action():
    prompt = build_launch_prompt(
        session=_session(), registry_project={"milestone": "", "next_action": ""}, decisions=[]
    )
    assert "Pending Tasks:\n(none recorded)" in prompt


def test_build_launch_prompt_never_calls_any_external_api():
    # Checks actual imports, not the docstring's prose (which legitimately
    # names these tools to explain that this module does NOT use them).
    import ast
    import inspect

    from app.services import launcher as launcher_module

    tree = ast.parse(inspect.getsource(launcher_module))
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported_modules <= {"__future__", "typing"}
