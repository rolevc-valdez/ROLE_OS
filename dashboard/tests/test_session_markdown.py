"""Unit tests for the Daily Session domain's pure text generation
(app.session.markdown): the Claude prompt and the Obsidian daily record.
"""

from __future__ import annotations

from app.session.markdown import build_claude_prompt, build_daily_markdown, daily_markdown_filename


def test_build_claude_prompt_matches_required_structure():
    prompt = build_claude_prompt(
        mode="BUILD",
        project_name="ROLE OS",
        objective="Ship the dashboard MVP",
        expected_result="A working local dashboard",
    )
    assert prompt.startswith("Initialize using SYSTEM.md.")
    assert "ROLE OS Session" in prompt
    assert "Mode:\nBUILD" in prompt
    assert "Project:\nROLE OS" in prompt
    assert "Today's Objective:\nShip the dashboard MVP" in prompt
    assert "Expected Result:\nA working local dashboard" in prompt
    assert "1. Summarize current project status." in prompt
    assert "5. Wait for approval before making destructive or architectural changes." in prompt


def test_build_claude_prompt_never_calls_any_external_api():
    # Purely a documentation-of-intent test: the function takes only plain
    # strings and returns a plain string, so there is no network call to
    # accidentally introduce as this file evolves.
    import inspect

    from app.session import markdown as markdown_module

    source = inspect.getsource(markdown_module)
    for forbidden in ("requests.", "httpx.", "openai", "anthropic", "http://", "https://"):
        assert forbidden not in source


def _session(**overrides):
    payload = {
        "date": "2026-07-30",
        "project_name": "ROLE OS",
        "mode": "BUILD",
        "objective": "Ship the dashboard MVP",
        "expected_result": "A working local dashboard",
        "completed_work": "Built the session domain and UI",
        "decisions": "Own SQLite store per domain",
        "blockers": "None",
        "next_step": "Write tests",
        "status": "completed",
    }
    payload.update(overrides)
    return payload


def test_build_daily_markdown_matches_required_structure():
    md = build_daily_markdown(_session())
    assert md.startswith("# 2026-07-30")
    assert "## Project\nROLE OS" in md
    assert "## Mode\nBUILD" in md
    assert "## Objective\nShip the dashboard MVP" in md
    assert "## Expected Result\nA working local dashboard" in md
    assert "## Completed\nBuilt the session domain and UI" in md
    assert "## Decisions\nOwn SQLite store per domain" in md
    assert "## Blockers\nNone" in md
    assert "## Next Step\nWrite tests" in md
    assert "## Status\nCompleted" in md


def test_build_daily_markdown_handles_empty_optional_fields():
    md = build_daily_markdown(
        _session(completed_work="", decisions="", blockers="", next_step="", status="active")
    )
    assert "(none recorded)" in md
    assert "## Status\nActive" in md


def test_daily_markdown_filename_is_obsidian_daily_note_style():
    assert daily_markdown_filename(_session(date="2026-07-30")) == "2026-07-30.md"
