"""Tests for the deterministic Next Action extractor (Sprint 4 §3):
priority order (AI session > NEXT_ACTION.md > TODO > ROADMAP > README Next
Steps > CHANGELOG unreleased > latest git commit), and the "nothing found"
case never inventing a value.
"""

from __future__ import annotations

from pathlib import Path

from app.discovery.next_action import extract_next_action


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ai_session_hint_wins_over_everything(tmp_path: Path):
    _write(tmp_path / "NEXT_ACTION.md", "should not be used")
    result = extract_next_action(tmp_path, ai_session_next_prompt="Continue the auth flow")
    assert result.source == "ai_session"
    assert result.text == "Continue the auth flow"
    assert result.confidence == 0.95


def test_ai_session_pending_work_used_when_no_next_prompt(tmp_path: Path):
    result = extract_next_action(tmp_path, ai_session_pending_work="Finish the migration")
    assert result.source == "ai_session"
    assert result.text == "Finish the migration"


def test_next_action_file_wins_over_todo(tmp_path: Path):
    _write(tmp_path / "NEXT_ACTION.md", "# Next\nFinish the login flow\n")
    _write(tmp_path / "TODO.md", "- [ ] something else\n")
    result = extract_next_action(tmp_path)
    assert result.source == "NEXT_ACTION.md"
    assert "Finish the login flow" in result.text
    assert result.source_path.endswith("NEXT_ACTION.md")


def test_todo_file_used_when_no_next_action_file(tmp_path: Path):
    _write(tmp_path / "TODO.md", "- [ ] Ship the release notes\n- [ ] cleanup\n")
    result = extract_next_action(tmp_path)
    assert result.source == "TODO.md"
    assert result.text == "Ship the release notes"


def test_todo_section_in_readme_used_when_no_todo_file(tmp_path: Path):
    _write(tmp_path / "README.md", "# Proj\n\n## TODO\n- [ ] Write docs\n\n## Other\nstuff\n")
    result = extract_next_action(tmp_path)
    assert result.source == "TODO section"
    assert "Write docs" in result.text


def test_roadmap_current_milestone_used_when_nothing_above(tmp_path: Path):
    _write(tmp_path / "ROADMAP.md", "# Roadmap\n\n## Milestone 2\n- [ ] Build the API\n")
    result = extract_next_action(tmp_path)
    assert result.source == "ROADMAP.md"
    assert "Build the API" in result.text


def test_readme_next_steps_used_when_nothing_above(tmp_path: Path):
    _write(tmp_path / "README.md", "# Proj\n\n## Next Steps\nDeploy to prod.\n\n## Other\n")
    result = extract_next_action(tmp_path)
    assert result.source == "README Next Steps"
    assert "Deploy to prod." in result.text


def test_changelog_unreleased_used_when_nothing_above(tmp_path: Path):
    _write(
        tmp_path / "CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n- Add feature X\n\n## 1.0.0\n"
    )
    result = extract_next_action(tmp_path)
    assert result.source == "CHANGELOG unreleased"
    assert "Add feature X" in result.text


def test_latest_commit_used_as_final_fallback(tmp_path: Path):
    result = extract_next_action(
        tmp_path, last_commit_message="Fix bug in parser", last_commit_date="2026-01-01"
    )
    assert result.source == "latest git commit"
    assert "Fix bug in parser" in result.text
    assert result.confidence == 0.3


def test_nothing_found_returns_none_not_invented(tmp_path: Path):
    result = extract_next_action(tmp_path)
    assert result.text is None
    assert result.source == "none"
    assert result.confidence == 0.0


def test_priority_order_full_stack(tmp_path: Path):
    """All seven signals present at once -- AI session must still win."""
    _write(tmp_path / "TODO.md", "- [ ] todo item\n")
    _write(tmp_path / "ROADMAP.md", "# R\n\n## M1\n- [ ] roadmap item\n")
    _write(tmp_path / "README.md", "# P\n\n## Next Steps\nreadme next steps\n")
    _write(tmp_path / "CHANGELOG.md", "# C\n\n## [Unreleased]\n- changelog item\n")
    result = extract_next_action(
        tmp_path,
        ai_session_next_prompt="AI session wins",
        last_commit_message="commit wins last",
    )
    assert result.text == "AI session wins"

    # Remove the AI hint: NEXT_ACTION.md doesn't exist, so TODO.md is next.
    result2 = extract_next_action(tmp_path, last_commit_message="commit wins last")
    assert result2.source == "TODO.md"


def test_read_only_no_filesystem_modification(tmp_path: Path):
    import os

    _write(tmp_path / "NEXT_ACTION.md", "do the thing\n")

    def snapshot():
        snap = set()
        for dirpath, _dirs, files in os.walk(tmp_path):
            for name in files:
                fp = Path(dirpath) / name
                st = fp.stat()
                snap.add((str(fp), st.st_mtime, st.st_size))
        return snap

    before = snapshot()
    extract_next_action(tmp_path)
    after = snapshot()
    assert before == after


def test_real_path_with_spaces_and_parentheses(tmp_path: Path):
    root = tmp_path / "My Drive (test@example.com)" / "1 - IA PROJECTS" / "my-app"
    _write(root / "NEXT_ACTION.md", "Ship the thing\n")
    result = extract_next_action(root)
    assert result.text == "Ship the thing"
