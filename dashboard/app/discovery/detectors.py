"""Single-pass, read-only signal extraction for one candidate folder.

`analyze_folder` walks a folder tree exactly once, never opens a file for
writing, never deletes/renames/creates anything, and never follows a
symlink or NTFS junction (those are recorded in `reparse_points_skipped`
instead of being descended into, so a cyclic link can never cause an
infinite walk).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from app.discovery.models import AbsolutePathReference, DiscoveredProject

# Directories that are never descended into: build artifacts, caches, VCS
# internals, and dependency trees that would otherwise dwarf the real
# project signal (and, for node_modules/.venv in particular, could contain
# tens of thousands of files).
IGNORE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".idea",
    ".vscode",
    "target",
    "bin",
    "obj",
    ".cache",
    "site-packages",
    "$RECYCLE.BIN",
    "System Volume Information",
}

TOP_LEVEL_MARKER_FILES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "composer.json",
}

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico", ".tiff"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv", ".flv"}
DB_EXT = {".db", ".sqlite", ".sqlite3"}
DOCUMENT_EXT = {".pdf"}
DESIGN_FILE_EXT = {".psd", ".ai", ".xd", ".fig", ".sketch"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}

LANGUAGE_EXT_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".swift": "Swift",
    ".kt": "Kotlin",
}

TEST_FILE_RE = re.compile(r"(^test_.+\.py$|.+_test\.py$|.+\.test\.[jt]sx?$|.+\.spec\.[jt]sx?$)", re.I)
README_RE = re.compile(r"^readme(\..*)?$", re.I)
ROADMAP_RE = re.compile(r"^roadmap(\..*)?$", re.I)
CHANGELOG_RE = re.compile(r"^changelog(\..*)?$", re.I)
TODO_RE = re.compile(r"^todo(\..*)?$", re.I)
LICENSE_RE = re.compile(r"^licen[sc]e(\..*)?$", re.I)
LOGO_RE = re.compile(r"(logo|icon|favicon)", re.I)
ENV_FILE_RE = re.compile(r"^\.env(\..+)?$", re.I)

TEXT_SCAN_EXT = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".ps1",
    ".bat",
    ".cmd",
    ".sh",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".cfg",
    ".ini",
    ".toml",
    ".code-workspace",
}
# Absolute-path references commonly sit inside quoted strings, and real
# paths on this machine contain spaces/parentheses (e.g. "My Drive
# (user@example.com)"), so we only stop at a closing quote/angle-bracket
# or end of line, not at whitespace.
ABS_WIN_RE = re.compile(r"[A-Za-z]:\\+[^\r\n\"'<>|]+")
ABS_POSIX_RE = re.compile(r"/(?:home|Users|mnt|root)/[^\r\n\"'<>|]+")

MAX_FILES = 20_000
MAX_ABS_SCAN_FILES = 500
MAX_ABS_SCAN_BYTES = 200_000
MAX_ABS_REFS_KEPT = 25


def _is_reparse_point(entry: os.DirEntry) -> bool:
    """True for symlinks and Windows junctions/reparse points."""
    try:
        if entry.is_symlink():
            return True
        st = entry.stat(follow_symlinks=False)
        attrs = getattr(st, "st_file_attributes", 0)
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def has_own_strong_markers(path: Path) -> bool:
    """True if `path` itself looks like a self-contained project root.

    Used by the scanner to decide whether to also look one level deeper
    (a container/monorepo folder) or stop here.
    """
    try:
        if (path / ".git").exists():
            return True
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file() and entry.name in TOP_LEVEL_MARKER_FILES:
                    return True
    except OSError:
        return False
    return False


def is_candidate_signal(path: Path) -> bool:
    """Minimal-signal check used to admit a *nested* (depth-2+) folder."""
    try:
        if (path / ".git").exists():
            return True
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    if entry.name in TOP_LEVEL_MARKER_FILES:
                        return True
                    if README_RE.match(entry.name):
                        return True
    except OSError:
        return False
    return False


def analyze_folder(root: Path) -> DiscoveredProject:
    """Walk `root` once (read-only) and populate a DiscoveredProject."""
    project = DiscoveredProject(root_path=str(root), name=root.name, depth=0)

    stack = [root]
    file_count = 0
    dir_count = 0
    max_mtime = 0.0
    abs_scan_budget_files = MAX_ABS_SCAN_FILES
    abs_scan_budget_bytes = MAX_ABS_SCAN_BYTES

    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except PermissionError as exc:
            project.scan_errors.append(f"permission denied: {current} ({exc})")
            continue
        except OSError as exc:
            project.scan_errors.append(f"error reading {current}: {exc}")
            continue

        for entry in entries:
            if _is_reparse_point(entry):
                project.reparse_points_skipped.append(entry.path)
                continue

            if entry.is_dir(follow_symlinks=False):
                dir_count += 1
                if entry.name in IGNORE_DIR_NAMES:
                    continue
                lower = entry.name.lower()
                if lower in {"docs", "documentation", "doc"}:
                    project.doc_folders.append(entry.path)
                if lower == "tests" or lower == "test":
                    project.has_tests = True
                if lower == "workflows" and Path(current).name.lower() == ".github":
                    project.has_github_actions = True
                if lower == ".obsidian":
                    project.has_obsidian_vault = True
                if file_count < MAX_FILES:
                    stack.append(Path(entry.path))
                continue

            if not entry.is_file(follow_symlinks=False):
                continue

            file_count += 1
            if file_count > MAX_FILES:
                project.truncated = True
                continue

            try:
                stat = entry.stat(follow_symlinks=False)
                max_mtime = max(max_mtime, stat.st_mtime)
            except OSError:
                pass

            name = entry.name
            stem_lower = name.lower()
            ext = Path(name).suffix.lower()

            if README_RE.match(name):
                project.has_readme = True
            if ROADMAP_RE.match(name):
                project.has_roadmap = True
            if CHANGELOG_RE.match(name):
                project.has_changelog = True
            if TODO_RE.match(name):
                project.has_todo = True
            if LICENSE_RE.match(name):
                project.has_license = True

            if stem_lower.endswith(".code-workspace"):
                project.vscode_workspace_files.append(entry.path)

            if name in TOP_LEVEL_MARKER_FILES:
                project.tech_markers.append(entry.path)
            if stem_lower.startswith("dockerfile"):
                project.has_dockerfile = True
            if stem_lower in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
                project.has_docker_compose = True
            if stem_lower.endswith(".csproj") or stem_lower == "go.mod":
                project.tech_markers.append(entry.path)

            if TEST_FILE_RE.match(name):
                project.has_tests = True
                project.test_file_count += 1

            if ext in IMAGE_EXT:
                project.image_count += 1
                if LOGO_RE.search(stem_lower):
                    project.logo_files.append(entry.path)
            elif ext in VIDEO_EXT:
                project.video_count += 1
            elif ext in DB_EXT:
                project.sqlite_files.append(entry.path)
            elif ext in DOCUMENT_EXT:
                project.document_count += 1
            elif ext in DESIGN_FILE_EXT:
                project.design_file_count += 1
            elif ext in FONT_EXT:
                project.font_count += 1

            if ENV_FILE_RE.match(name):
                project.env_files.append(entry.path)
            if ext == ".bat" or ext == ".cmd":
                project.batch_scripts.append(entry.path)
            if ext == ".ps1":
                project.powershell_scripts.append(entry.path)

            if ext in LANGUAGE_EXT_MAP:
                lang = LANGUAGE_EXT_MAP[ext]
                project.languages[lang] = project.languages.get(lang, 0) + 1

            if ext in TEXT_SCAN_EXT and abs_scan_budget_files > 0:
                refs, bytes_read = _scan_absolute_paths(
                    Path(entry.path), abs_scan_budget_bytes
                )
                abs_scan_budget_files -= 1
                abs_scan_budget_bytes -= bytes_read
                for ref in refs:
                    project.absolute_path_ref_count += 1
                    if len(project.absolute_path_refs) < MAX_ABS_REFS_KEPT:
                        project.absolute_path_refs.append(ref)

    project.total_files = file_count
    project.total_dirs = dir_count
    if max_mtime:
        from datetime import datetime, timezone

        project.last_modified = datetime.fromtimestamp(max_mtime, tz=timezone.utc).isoformat()

    return project


def _scan_absolute_paths(
    file_path: Path, byte_budget: int
) -> tuple[list[AbsolutePathReference], int]:
    """Read up to `byte_budget` bytes of a text file, read-only, looking
    for hardcoded absolute-path strings. Never writes to the file."""
    refs: list[AbsolutePathReference] = []
    read_bytes = 0
    try:
        size = file_path.stat().st_size
        if size <= 0:
            return refs, 0
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            for lineno, line in enumerate(fh, start=1):
                read_bytes += len(line.encode("utf-8", errors="ignore"))
                if read_bytes > byte_budget:
                    break
                for pattern in (ABS_WIN_RE, ABS_POSIX_RE):
                    match = pattern.search(line)
                    if match:
                        refs.append(
                            AbsolutePathReference(
                                file=str(file_path),
                                line=lineno,
                                snippet=match.group(0)[:200],
                            )
                        )
    except OSError:
        pass
    return refs, read_bytes
