"""Data shapes produced by the Discovery Engine. No DB, no I/O here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GitInfo:
    is_repo: bool = False
    branch: Optional[str] = None
    remote_url: Optional[str] = None
    last_commit_hash: Optional[str] = None
    last_commit_date: Optional[str] = None
    last_commit_message: Optional[str] = None
    commit_count: Optional[int] = None
    is_dirty: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class AbsolutePathReference:
    file: str
    line: int
    snippet: str


@dataclass
class DiscoveredProject:
    root_path: str
    name: str
    depth: int
    parent_path: Optional[str] = None

    git: GitInfo = field(default_factory=GitInfo)

    has_readme: bool = False
    has_roadmap: bool = False
    has_changelog: bool = False
    has_todo: bool = False
    has_license: bool = False
    doc_folders: list[str] = field(default_factory=list)

    languages: dict[str, int] = field(default_factory=dict)
    tech_markers: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)

    has_tests: bool = False
    test_file_count: int = 0

    image_count: int = 0
    video_count: int = 0
    document_count: int = 0
    design_file_count: int = 0
    font_count: int = 0
    logo_files: list[str] = field(default_factory=list)

    sqlite_files: list[str] = field(default_factory=list)
    env_files: list[str] = field(default_factory=list)
    batch_scripts: list[str] = field(default_factory=list)
    powershell_scripts: list[str] = field(default_factory=list)

    has_dockerfile: bool = False
    has_docker_compose: bool = False
    has_github_actions: bool = False

    has_obsidian_vault: bool = False
    vscode_workspace_files: list[str] = field(default_factory=list)

    absolute_path_refs: list[AbsolutePathReference] = field(default_factory=list)
    absolute_path_ref_count: int = 0

    total_files: int = 0
    total_dirs: int = 0
    last_modified: Optional[str] = None
    truncated: bool = False
    reparse_points_skipped: list[str] = field(default_factory=list)
    scan_errors: list[str] = field(default_factory=list)

    classification: str = "Unknown"
    confidence_score: float = 0.0
    confidence_reasons: list[str] = field(default_factory=list)

    move_risk: str = "low"
    move_risk_reasons: list[str] = field(default_factory=list)

    maturity: str = "unknown"
    maturity_reasons: list[str] = field(default_factory=list)

    commercial_readiness: str = "unknown"
    commercial_reasons: list[str] = field(default_factory=list)

    health_score: Optional[int] = None
    health_breakdown: dict[str, Optional[int]] = field(default_factory=dict)

    recommendation: str = "Requires manual review"
    recommendation_reasons: list[str] = field(default_factory=list)


@dataclass
class ScanResult:
    root: str
    scanned_at: str
    duration_seconds: float
    projects: list[DiscoveredProject] = field(default_factory=list)
    skipped_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    max_depth: int = 2
