"""Shared, read-only constants used by the inventory walk and more than one
detector. Detector-specific constants (extension sets, regexes) that only
one detector cares about live in that detector's own module instead — this
file is only for things genuinely shared across module boundaries.
"""

from __future__ import annotations

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

# Used by both the scanner's candidate-admission heuristics
# (has_own_strong_markers/is_candidate_signal) and detectors/markers.py's
# tech-marker detection -- kept in one place so the two never drift apart.
TOP_LEVEL_MARKER_FILES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "composer.json",
    "pom.xml",
}

MAX_FILES = 20_000
