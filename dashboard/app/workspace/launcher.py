"""Claude Code Launcher (hotfix §4/§7; corrected by a second hotfix after
real dogfooding showed the first version opening a sandbox/remote-looking
environment instead of the actual local project): starts the LOCAL Claude
Code CLI installed on this Windows machine, working directory set to the
project's own canonical local root, and puts the Resume Prompt where the
user can paste it.

Root cause of the first version's bug (see module history / hotfix
report): it launched a bare `"claude"` token inside a *nested* shell via
`cmd /c start "title" cmd /k claude`. Two independent things could go
wrong with that:

  1. `"claude"` was never resolved to a real path by this module -- the
     nested `cmd /k claude` re-resolved it itself, via its own PATH
     search, inside a brand-new process `start` spawned. Anything else
     named `claude` earlier in *that* shell's resolution (an App
     Execution Alias, a differently-scoped PATH, a remote/sandboxed
     wrapper) would launch instead of the confirmed local CLI.
  2. `start` hands the new console off to whatever Windows treats as the
     "Default Terminal Application" (typically Windows Terminal on
     Windows 11), which can open using a *profile's own configured
     starting directory* instead of reliably inheriting the spawned
     process's actual working directory -- an independent way to lose
     the cwd, unrelated to (1).

This version fixes both by never using `start`/a nested shell at all:
`shutil.which` resolves the *exact* local executable once, up front, and
`subprocess.Popen(..., creationflags=CREATE_NEW_CONSOLE)` launches that
exact path directly -- Python's own `CreateProcess` call sets the working
directory on the process we create, with no `start`/terminal-profile
hand-off in between to override it.

Safety contract this module exists to keep (unchanged):
  - the project root is never taken from a raw string the caller typed --
    it must already be an adopted project's own `root_path` (resolved by
    `app.workspace.service`, same as every other Resume Work call), and
    is validated to exist and not be an excluded/internal folder;
  - the command line launched is a fixed, literal argument list -- the
    resolved executable path and the project root are both passed as
    discrete argv/`cwd` values (Windows' own `CreateProcess`/
    `list2cmdline` quoting), never built by concatenating caller text
    into a shell string;
  - if the local CLI cannot be found, this module never falls back to
    Claude web, and never opens any process at all -- it returns a clear,
    actionable error instead (§7);
  - the Resume Prompt is written to the clipboard over stdin (`clip`),
    never interpolated into a shell command, so it is safe regardless of
    quotes/newlines/special characters it may contain.

Follows the exact `subprocess`/Windows-only conventions already
established by `app.routers.assets` (`_confirm_windows`, `os.startfile`,
`subprocess.run([...], check=...)`).
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

CLAUDE_CLI_NAME = "claude"

# Windows-only flag (absent on other platforms, so guarded behind
# `_confirm_windows()` before ever being read) -- tells `CreateProcess` to
# allocate a brand-new console for the child instead of attaching to ours,
# with no `start`/default-terminal-application hand-off in between.
_CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)

_NOT_FOUND_MESSAGE = (
    "Local Claude Code CLI was not found. Install it with `npm install -g "
    "@anthropic-ai/claude-code`, confirm `where.exe claude` resolves to a real "
    "path, and make sure that location is on this account's PATH, then try again."
)

_DIAGNOSTIC_FILES = ("README.md", "package.json", "pyproject.toml")


class LauncherError(Exception):
    """Raised for any condition that must stop the launch before a
    process is spawned (not Windows, root missing, root not a
    directory)."""


def _confirm_windows() -> None:
    if platform.system() != "Windows":
        raise LauncherError(
            "Launching Claude Code is only implemented for the Windows desktop "
            "this dashboard normally runs on"
        )


def _confirm_root(root_path: str | None) -> Path:
    if not root_path or not root_path.strip():
        raise LauncherError("This project has no local root path to launch Claude Code in")
    path = Path(root_path)
    if not path.is_dir():
        raise LauncherError(f"Project root does not exist on disk: {root_path}")
    return path


def _copy_to_clipboard(text: str) -> bool:
    """Best-effort clipboard copy via the Windows `clip` builtin, piped
    over stdin -- never interpolated into a command string, so arbitrary
    prompt content (quotes, newlines, `&`, `|`, ...) is inert here.
    Returns whether it succeeded; a failure here is not fatal to the
    launch itself (§8: "if reliable CLI prompt injection is not
    supported, copy it to clipboard and tell the user to paste it" --
    this is that fallback path, so its own failure just means the caller
    must say so, not abort the launch)."""
    try:
        subprocess.run(
            ["clip"],
            input=text.encode("utf-16-le"),
            check=True,
            timeout=5,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def resolve_claude_cli_path() -> str | None:
    """The one place this module resolves `"claude"` to a real path --
    every launch uses this exact resolved value, never the bare name, so
    there is no second, independent PATH lookup (by a nested shell) that
    could resolve to something else (hotfix §2/§6: "do not assume a
    command named 'claude' is the correct executable")."""
    return shutil.which(CLAUDE_CLI_NAME)


def claude_code_cli_available() -> bool:
    return resolve_claude_cli_path() is not None


def directory_diagnostics(root: Path) -> dict[str, Any]:
    """Hotfix §5's "runtime proof", the deterministic half of it: this
    module cannot make the just-launched interactive CLI report back what
    it sees, but it *can* prove, server-side, exactly what the working
    directory it is handing that CLI actually contains -- the same
    guarantee a human would get by running `Get-ChildItem` themselves
    before trusting the launch. Bounded to a top-level listing (never a
    recursive walk) -- this is a sanity check, not a second Discovery
    Engine scan."""
    try:
        entries = sorted(p.name for p in root.iterdir())
    except OSError:
        entries = []
    return {
        "cwd": str(root),
        "entry_count": len(entries),
        "sample_entries": entries[:10],
        "has_git": (root / ".git").exists(),
        "present_files": [name for name in _DIAGNOSTIC_FILES if (root / name).exists()],
    }


def launch_claude_code(root_path: str, prompt: str) -> dict[str, Any]:
    """Opens a brand-new console window running the resolved local Claude
    Code CLI directly, working directory = `root_path`. The Resume Prompt
    is always copied to the clipboard (§8's clipboard fallback) since
    there is no reliably supported way to feed an arbitrary multi-line
    prompt straight into an interactive CLI's first turn -- the user
    pastes it once the session opens. Never auto-submits anything, and
    never falls back to a web assistant if the local CLI is missing.
    """
    _confirm_windows()
    root = _confirm_root(root_path)
    diagnostics = directory_diagnostics(root)

    prompt_copied = _copy_to_clipboard(prompt)
    cli_path = resolve_claude_cli_path()

    if cli_path is None:
        return {
            "launched": False,
            "working_directory": str(root),
            "executable": None,
            "cli_available": False,
            "prompt_copied": prompt_copied,
            "message": _NOT_FOUND_MESSAGE,
            "directory_diagnostics": diagnostics,
        }

    # A new console hosting the resolved executable directly, launched by
    # this process's own `CreateProcess` call -- no `start`/nested-shell/
    # default-terminal-application hand-off that could substitute a
    # different working directory or resolve `claude` a second time.
    args = [cli_path]
    try:
        subprocess.Popen(args, cwd=str(root), creationflags=_CREATE_NEW_CONSOLE)
    except OSError as exc:
        raise LauncherError(f"could not launch Claude Code: {exc}") from exc

    message = (
        f"Claude Code (local) launching in {root} — prompt copied, paste it once the "
        "session opens."
        if prompt_copied
        else f"Claude Code (local) launching in {root}, but the prompt could not be "
        "copied automatically — copy it manually from the Resume Work card."
    )

    return {
        "launched": True,
        "working_directory": str(root),
        "executable": cli_path,
        "cli_available": True,
        "prompt_copied": prompt_copied,
        "message": message,
        "directory_diagnostics": diagnostics,
    }
