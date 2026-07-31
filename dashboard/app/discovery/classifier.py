"""Classification and scoring heuristics (§8, §11 of the proposal).

These are transparent, explainable weighted heuristics — not ML — by
design (see 08_IMPORT_ENGINE_PROPOSAL.md §8/§11). Every score carries a
list of the specific reasons behind it so a human can sanity-check or
override it. Nothing here reads the filesystem; it only scores fields
already populated by `detectors.py`/`git_reader.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.discovery.health import compute_health
from app.discovery.models import DiscoveredProject
from app.discovery.recommendation import recommend

WEB_FRAMEWORK_HINTS = {"next.config", "vite.config", "nuxt.config", "astro.config", "gatsby-config"}
COMMERCIAL_KEYWORDS = (
    "launch",
    "live",
    "production",
    "client",
    "deploy",
    "customer",
    "invoice",
    "pricing",
)


def _age_days(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    except ValueError:
        return None


def _has_source_files(project: DiscoveredProject) -> bool:
    return sum(project.languages.values()) > 0


def _is_web_marker_present(project: DiscoveredProject) -> bool:
    lowered = [m.lower() for m in project.tech_markers]
    if any("package.json" in m for m in lowered):
        return True
    return False


def classify_confidence(project: DiscoveredProject) -> None:
    """Populate confidence_score / confidence_reasons (0.0-1.0)."""
    score = 0.0
    reasons: list[str] = []

    if project.git.is_repo:
        score += 0.3
        reasons.append("has a .git repository")
    if project.tech_markers:
        score += 0.25
        reasons.append(f"has {len(project.tech_markers)} tech stack marker file(s)")
    if project.has_readme or project.has_roadmap or project.doc_folders:
        score += 0.15
        reasons.append("has README/ROADMAP or a docs folder")
    if project.has_tests:
        score += 0.1
        reasons.append("has a tests folder or test files")
    if _has_source_files(project):
        score += 0.2
        reasons.append("contains recognized source code files")

    project.confidence_score = round(min(score, 1.0), 2)
    project.confidence_reasons = reasons


def classify_kind(project: DiscoveredProject) -> None:
    """Populate `classification` from the signals already extracted."""
    has_code = _has_source_files(project) or bool(project.tech_markers) or project.git.is_repo
    heavy_assets = (project.image_count + project.video_count) >= 10
    heavy_docs = bool(
        project.has_readme and (project.has_roadmap or project.has_changelog or project.doc_folders)
    )
    is_web = _is_web_marker_present(project) or any(
        marker.lower().startswith(hint) for marker in project.tech_markers for hint in WEB_FRAMEWORK_HINTS
    )

    total_signal_axes = sum([has_code, heavy_assets, heavy_docs])

    if project.total_files == 0 and project.total_dirs == 0:
        project.classification = "Non-project"
        return

    if project.confidence_score < 0.15 and not heavy_assets and not heavy_docs:
        project.classification = "Non-project"
        return

    if total_signal_axes >= 2:
        project.classification = "Mixed Project"
        return

    if is_web and has_code:
        project.classification = "Website"
        return
    if has_code:
        project.classification = "Software Project"
        return
    if heavy_docs:
        project.classification = "Documentation Project"
        return
    if heavy_assets:
        project.classification = "Brand / Asset Project"
        return

    project.classification = "Unknown"


def classify_move_risk(project: DiscoveredProject) -> None:
    """Populate move_risk / move_risk_reasons.

    Move risk = "will this break if the folder is relocated to a different
    machine or path?" — driven by hardcoded absolute-path references and
    machine-specific config, not by project quality.
    """
    reasons: list[str] = []
    score = 0

    if project.absolute_path_ref_count > 5:
        score += 3
        reasons.append(f"{project.absolute_path_ref_count} hardcoded absolute-path references found")
    elif project.absolute_path_ref_count > 0:
        score += 1
        reasons.append(f"{project.absolute_path_ref_count} hardcoded absolute-path reference(s) found")

    if project.batch_scripts or project.powershell_scripts:
        script_refs = sum(
            1
            for ref in project.absolute_path_refs
            if ref.file.lower().endswith((".bat", ".cmd", ".ps1"))
        )
        if script_refs:
            score += 1
            reasons.append("launcher/batch/PowerShell script(s) contain absolute paths")

    if project.env_files:
        score += 1
        reasons.append(f"{len(project.env_files)} .env file(s) present (likely machine/environment-specific)")

    if project.git.remote_url and project.git.remote_url.startswith(("/", "file://")) or (
        project.git.remote_url and ":" in project.git.remote_url[:2] and project.git.remote_url[1] == ":"
    ):
        score += 1
        reasons.append("git remote points at a local filesystem path")

    if project.has_obsidian_vault:
        score += 1
        reasons.append(
            "contains an .obsidian vault config (may reference this folder's "
            "absolute path in its workspace/plugin settings)"
        )

    if project.vscode_workspace_files:
        script_refs = sum(
            1
            for ref in project.absolute_path_refs
            if ref.file.lower().endswith(".code-workspace")
        )
        if script_refs:
            score += 1
            reasons.append("VS Code *.code-workspace file(s) contain absolute paths")

    if score >= 3:
        project.move_risk = "high"
    elif score >= 1:
        project.move_risk = "medium"
    else:
        project.move_risk = "low"
        if not reasons:
            reasons.append("no hardcoded absolute paths or machine-specific config detected")
    project.move_risk_reasons = reasons


def classify_maturity(project: DiscoveredProject) -> None:
    """Populate maturity / maturity_reasons."""
    reasons: list[str] = []
    activity_age = _age_days(project.git.last_commit_date) if project.git.last_commit_date else None
    if activity_age is None:
        activity_age = _age_days(project.last_modified)

    commit_count = project.git.commit_count or 0

    if activity_age is not None and activity_age > 180:
        project.maturity = "stale"
        reasons.append(f"no activity in {int(activity_age)} days")
    elif activity_age is not None and activity_age <= 30:
        if project.has_tests and (project.has_readme or project.doc_folders) and commit_count >= 20:
            project.maturity = "mature"
            reasons.append("recent activity, tests, docs, and commit history all present")
        else:
            project.maturity = "active"
            reasons.append(f"activity within the last {int(activity_age)} days")
    elif commit_count == 0 and not project.has_tests and project.total_files < 20:
        project.maturity = "prototype"
        reasons.append("few files, no commit history, no tests")
    else:
        project.maturity = "active"
        reasons.append("moderate signal; defaulting to active")

    project.maturity_reasons = reasons


def classify_commercial_readiness(project: DiscoveredProject) -> None:
    """Populate commercial_readiness / commercial_reasons.

    Deliberately weak/heuristic per §11 of the proposal — a suggestion for
    a human to confirm or override, not an assertion.
    """
    reasons: list[str] = []
    score = 0

    if project.has_dockerfile or project.has_docker_compose:
        score += 1
        reasons.append("has Docker deployment config")
    if project.has_github_actions:
        score += 1
        reasons.append("has CI (GitHub Actions) configured")
    if project.has_tests:
        score += 1
        reasons.append("has automated tests")
    if project.has_readme and (project.has_roadmap or project.has_changelog):
        score += 1
        reasons.append("has README plus roadmap/changelog")

    text_blobs = " ".join(ref.snippet.lower() for ref in project.absolute_path_refs)
    if any(keyword in text_blobs for keyword in COMMERCIAL_KEYWORDS):
        score += 1
        reasons.append("commercial-signal keywords found in scanned text")

    if score >= 4:
        project.commercial_readiness = "production"
    elif score >= 2:
        project.commercial_readiness = "client-ready"
    elif score >= 1:
        project.commercial_readiness = "early"
    else:
        project.commercial_readiness = "not-commercial"
        if not reasons:
            reasons.append("no deployment, CI, test, or roadmap signal found")

    project.commercial_reasons = reasons


def classify(project: DiscoveredProject) -> DiscoveredProject:
    """Run every classifier/scorer over a fully-detected project in place."""
    classify_confidence(project)
    classify_kind(project)
    classify_move_risk(project)
    classify_maturity(project)
    classify_commercial_readiness(project)
    project.health_score, project.health_breakdown = compute_health(project)
    project.recommendation, project.recommendation_reasons = recommend(project)
    return project
