"""Data shapes produced by the Discovery Engine. No DB, no I/O here."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.discovery.pipeline import PipelineStage


@dataclass
class CommitInfo:
    hash: str
    date: str
    message: str


@dataclass
class GitInfo:
    is_repo: bool = False
    branch: str | None = None
    remote_url: str | None = None
    last_commit_hash: str | None = None
    last_commit_date: str | None = None
    last_commit_message: str | None = None
    commit_count: int | None = None
    is_dirty: bool | None = None
    error: str | None = None
    # Sprint 4 (Project Intelligence Wiring): last 5 commits, for the
    # unified Recent Activity feed and Home page -- read via one extra
    # read-only `git log` call, same guarantees as everything else here.
    recent_commits: list[CommitInfo] = field(default_factory=list)


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
    parent_path: str | None = None

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
    last_modified: str | None = None
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

    health_score: int | None = None
    health_breakdown: dict[str, int | None] = field(default_factory=dict)

    recommendation: str = "Requires manual review"
    recommendation_reasons: list[str] = field(default_factory=list)

    # Sprint 3: project-boundary / hierarchy model. Deliberately separate
    # from `classification` above -- `classification` answers "what kind of
    # thing is this" (Software Project/Website/...), `item_kind` answers
    # "where does this sit in the real project tree" (project/repository/
    # component/internal_folder/...). See app.discovery.boundary.
    item_id: str = ""
    item_kind: str = "unknown"
    parent_item_id: str | None = None
    project_root_id: str | None = None
    hierarchy_depth: int = 0
    is_top_level_project: bool = False
    is_nested_repository: bool = False
    is_internal_folder: bool = False
    is_excluded: bool = False
    exclusion_reason: str | None = None
    boundary_confidence: float = 0.0
    boundary_evidence: list[str] = field(default_factory=list)

    # Sprint 1.5: which pipeline stages have run for this project so far.
    # See `app.discovery.pipeline` -- `compute_health`/`recommend` refuse to
    # run against a project that hasn't reached their prerequisite stage,
    # instead of silently scoring incomplete data.
    stage: PipelineStage = PipelineStage.NEW


@dataclass
class ScanResult:
    root: str
    scanned_at: str
    duration_seconds: float
    projects: list[DiscoveredProject] = field(default_factory=list)
    skipped_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    max_depth: int = 2
