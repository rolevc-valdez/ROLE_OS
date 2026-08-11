"""Tests for `app.workspace.launcher` (hotfix §4/§7, corrected by a second
hotfix after real dogfooding: launching a bare `"claude"` token through a
nested `cmd /c start ... cmd /k claude` could resolve to the wrong
executable and/or lose the working directory to a terminal profile's own
default directory). All process-spawning is mocked -- these tests verify
the safety contract (validated root, resolved executable, no shell string
built from caller input, cwd carries the path, direct console creation
with no `start`/nested-shell hand-off, never a silent web fallback) and
the degrade-gracefully paths, not that a real terminal actually opens."""

from __future__ import annotations

import subprocess

import pytest
from app.workspace import launcher


@pytest.fixture(autouse=True)
def windows(monkeypatch):
    monkeypatch.setattr(launcher.platform, "system", lambda: "Windows")


def test_launch_rejects_missing_root_path():
    with pytest.raises(launcher.LauncherError):
        launcher.launch_claude_code(None, "prompt text")


def test_launch_rejects_root_path_not_on_disk(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(launcher.LauncherError):
        launcher.launch_claude_code(str(missing), "prompt text")


def test_launch_rejects_off_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher.platform, "system", lambda: "Linux")
    with pytest.raises(launcher.LauncherError):
        launcher.launch_claude_code(str(tmp_path), "prompt text")


def test_launch_resolves_and_launches_the_exact_local_executable_directly(
    monkeypatch, tmp_path
):
    """The core correctness fix: the resolved executable path is launched
    directly (no nested `cmd /c start ... claude` re-resolving the bare
    name itself), and the console is created with `cwd` set on the exact
    process we spawn -- no `start`/default-terminal-application hand-off
    that could substitute a different working directory. Paths with
    spaces and parentheses must work: the variable path is passed only
    via `cwd`, never concatenated into the argument list."""
    root = tmp_path / "1 - IA PROJECTS (ROLE Commerce Factory)"
    root.mkdir()
    resolved = "C:/Users/rolev/AppData/Roaming/npm/claude.CMD"
    monkeypatch.setattr(launcher, "resolve_claude_cli_path", lambda: resolved)

    captured = {}

    def fake_popen(args, cwd=None, creationflags=None):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["creationflags"] = creationflags

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(launcher, "_copy_to_clipboard", lambda text: True)

    result = launcher.launch_claude_code(str(root), "Resume prompt with & special | chars")

    assert result["launched"] is True
    assert result["cli_available"] is True
    assert result["executable"] == resolved
    assert result["prompt_copied"] is True
    assert captured["cwd"] == str(root)
    # The resolved executable is the *only* argv token -- "claude" (the
    # bare, re-resolvable name) never appears anywhere in the launched
    # command, and neither does "start"/a nested "cmd".
    assert captured["args"] == [resolved]
    assert captured["creationflags"] == launcher._CREATE_NEW_CONSOLE
    assert "start" not in captured["args"]
    assert "cmd" not in captured["args"]


def test_launch_never_falls_back_to_a_web_assistant_when_cli_missing(monkeypatch, tmp_path):
    """§6/§7: a missing local CLI must return a clear, actionable error --
    never open any process (which would risk opening some other, wrong
    environment), and never silently succeed."""
    monkeypatch.setattr(launcher, "resolve_claude_cli_path", lambda: None)
    popen_called = {"value": False}
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda *a, **k: popen_called.update(value=True)
    )
    monkeypatch.setattr(launcher, "_copy_to_clipboard", lambda text: True)

    result = launcher.launch_claude_code(str(tmp_path), "prompt text")

    assert result["launched"] is False
    assert result["executable"] is None
    assert result["cli_available"] is False
    assert popen_called["value"] is False
    assert "Local Claude Code CLI was not found" in result["message"]
    assert "claude.ai" not in result["message"].lower()
    assert "npm install -g" in result["message"]


def test_launch_reports_but_does_not_fail_when_clipboard_copy_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "resolve_claude_cli_path", lambda: "C:/npm/claude.CMD")
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda args, cwd=None, creationflags=None: None
    )

    def fake_clip(*args, **kwargs):
        raise subprocess.SubprocessError("clip.exe not available")

    monkeypatch.setattr(launcher.subprocess, "run", fake_clip)

    result = launcher.launch_claude_code(str(tmp_path), "prompt text")

    assert result["launched"] is True
    assert result["prompt_copied"] is False
    assert "could not be copied" in result["message"]


def test_claude_code_cli_available_reflects_the_resolver(monkeypatch):
    monkeypatch.setattr(launcher, "resolve_claude_cli_path", lambda: None)
    assert launcher.claude_code_cli_available() is False
    monkeypatch.setattr(launcher, "resolve_claude_cli_path", lambda: "C:/npm/claude.CMD")
    assert launcher.claude_code_cli_available() is True


def test_resolve_claude_cli_path_uses_shutil_which_not_a_bare_name(monkeypatch):
    """§2/§6: never assume a command named "claude" is the correct
    executable -- this must be the one place resolution happens, backed
    by a real PATH lookup, not a literal string handed to a shell."""
    monkeypatch.setattr(launcher.shutil, "which", lambda name: f"C:/resolved/{name}.CMD")
    assert launcher.resolve_claude_cli_path() == "C:/resolved/claude.CMD"


def test_directory_diagnostics_reports_real_local_contents(tmp_path):
    """§5's deterministic "runtime proof": server-side confirmation of
    exactly what the working directory being handed to Claude Code
    contains -- git repo, README, package manifests, entry count."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "src").mkdir()

    diagnostics = launcher.directory_diagnostics(tmp_path)

    assert diagnostics["cwd"] == str(tmp_path)
    assert diagnostics["has_git"] is True
    assert "README.md" in diagnostics["present_files"]
    assert "pyproject.toml" in diagnostics["present_files"]
    assert diagnostics["entry_count"] == 4


def test_launch_includes_directory_diagnostics_in_the_result(monkeypatch, tmp_path):
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    monkeypatch.setattr(launcher, "resolve_claude_cli_path", lambda: "C:/npm/claude.CMD")
    monkeypatch.setattr(
        launcher.subprocess, "Popen", lambda args, cwd=None, creationflags=None: None
    )
    monkeypatch.setattr(launcher, "_copy_to_clipboard", lambda text: True)

    result = launcher.launch_claude_code(str(tmp_path), "prompt text")

    assert result["directory_diagnostics"]["cwd"] == str(tmp_path)
    assert "README.md" in result["directory_diagnostics"]["present_files"]


def test_launch_popen_failure_raises_launcher_error(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "resolve_claude_cli_path", lambda: "C:/npm/claude.CMD")

    def raise_oserror(*args, **kwargs):
        raise OSError("access denied")

    monkeypatch.setattr(launcher.subprocess, "Popen", raise_oserror)
    monkeypatch.setattr(launcher, "_copy_to_clipboard", lambda text: True)

    with pytest.raises(launcher.LauncherError):
        launcher.launch_claude_code(str(tmp_path), "prompt text")
