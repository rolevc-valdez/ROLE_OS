"""Read-only git metadata extraction (§10 of the Import Engine proposal).

Every call here is a local, read-only `git` subcommand — no fetch, pull,
push, clone, or any command that touches the working tree or a remote.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.discovery.models import GitInfo

_TIMEOUT = 5
_READ_ONLY_ENV_GUARD = {"GIT_TERMINAL_PROMPT": "0"}


def _run(args: list[str], cwd: Path) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env=_READ_ONLY_ENV_GUARD,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return 1, "", str(exc)


def read_git_info(path: Path) -> GitInfo:
    git_marker = path / ".git"
    if not git_marker.exists():
        return GitInfo(is_repo=False)

    info = GitInfo(is_repo=True)

    code, out, err = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], path)
    if code == 0:
        info.branch = out or None
    else:
        info.error = err or "failed to read branch"

    code, out, _ = _run(["git", "remote", "get-url", "origin"], path)
    if code == 0:
        info.remote_url = out or None

    code, out, _ = _run(
        ["git", "log", "-1", "--format=%H%x1f%aI%x1f%s"], path
    )
    if code == 0 and out:
        parts = out.split("\x1f")
        if len(parts) == 3:
            info.last_commit_hash, info.last_commit_date, info.last_commit_message = parts

    code, out, _ = _run(["git", "rev-list", "--count", "HEAD"], path)
    if code == 0 and out.isdigit():
        info.commit_count = int(out)

    code, out, _ = _run(["git", "status", "--porcelain"], path)
    if code == 0:
        info.is_dirty = bool(out.strip())

    return info
