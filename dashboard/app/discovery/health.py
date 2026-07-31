"""Project Health Score for discovered folders.

Mirrors `dashboard/app/projects/health/__init__.py`'s shape (weighted 0-100
signals, renormalized over whichever are available) but scores a
`DiscoveredProject` from filesystem evidence instead of a DB-backed project
dict. Each signal is a small pure function so any one of them can be
inspected or unit-tested independently; `compute_health` combines them and
returns the exact reasoning behind every number, per the Discovery Audit
requirement that every score be explainable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.discovery.models import DiscoveredProject
from app.discovery.pipeline import PipelineStage, require_stage

# Relative importance of each signal. Only signals that produced a value
# (not None) count toward the score -- weights are renormalized over the
# signals actually present, same rule as `projects/health/compute_health_score`.
SIGNAL_WEIGHTS: dict[str, float] = {
    "documentation": 0.20,
    "recent_activity": 0.20,
    "tests": 0.15,
    "roadmap": 0.10,
    "architecture": 0.10,
    "automation": 0.10,
    "commercial_readiness": 0.10,
    "deployment": 0.05,
}


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


def score_documentation(project: DiscoveredProject) -> int:
    """README + ROADMAP/CHANGELOG/TODO + a docs folder, weighted by count."""
    score = 0
    if project.has_readme:
        score += 55
    if project.doc_folders:
        score += 20
    if project.has_roadmap or project.has_changelog:
        score += 15
    if project.has_todo:
        score += 10
    return min(score, 100)


def score_tests(project: DiscoveredProject) -> int:
    if not project.has_tests:
        return 15
    return 100 if project.test_file_count >= 3 else 70


def score_recent_activity(project: DiscoveredProject) -> int | None:
    """Most recent signal between the last commit and the last file mtime."""
    age = _age_days(project.git.last_commit_date) if project.git.is_repo else None
    if age is None:
        age = _age_days(project.last_modified)
    if age is None:
        return None
    if age <= 7:
        return 100
    if age <= 30:
        return 80
    if age <= 90:
        return 55
    if age <= 180:
        return 30
    return 10


def score_roadmap(project: DiscoveredProject) -> int:
    if project.has_roadmap:
        return 100
    if project.has_todo:
        return 50
    return 20


def score_architecture(project: DiscoveredProject) -> int:
    """Weak proxy: a dedicated docs folder or clear tech markers suggest an
    intentional structure rather than a loose pile of files."""
    if project.doc_folders and project.tech_markers:
        return 100
    if project.doc_folders or project.tech_markers:
        return 60
    return 25


def score_automation(project: DiscoveredProject) -> int:
    signals = sum(
        [
            project.has_dockerfile or project.has_docker_compose,
            project.has_github_actions,
            bool(project.batch_scripts or project.powershell_scripts),
        ]
    )
    return {0: 15, 1: 55, 2: 80}.get(signals, 100)


_COMMERCIAL_SCORES = {
    "production": 100,
    "client-ready": 75,
    "early": 40,
    "not-commercial": 10,
    "unknown": 20,
}


def score_commercial_readiness(project: DiscoveredProject) -> int:
    return _COMMERCIAL_SCORES.get(project.commercial_readiness, 20)


def score_deployment(project: DiscoveredProject) -> int:
    if project.has_dockerfile or project.has_docker_compose:
        return 100
    if project.has_github_actions:
        return 60
    return 15


def compute_health(project: DiscoveredProject) -> tuple[int, dict[str, int | None]]:
    """Returns (score 0-100, breakdown per signal name).

    A signal that returns `None` (currently only `recent_activity`, when
    there is no git history and no readable file mtime at all) is excluded
    from both the breakdown and the weighted average, exactly like
    `projects/health/compute_health_score`'s `commit_dates=None` case.
    """
    require_stage(project, PipelineStage.CLASSIFIED, "health.compute_health")

    breakdown: dict[str, int | None] = {
        "documentation": score_documentation(project),
        "tests": score_tests(project),
        "recent_activity": score_recent_activity(project),
        "roadmap": score_roadmap(project),
        "architecture": score_architecture(project),
        "automation": score_automation(project),
        "commercial_readiness": score_commercial_readiness(project),
        "deployment": score_deployment(project),
    }

    available = {k: v for k, v in breakdown.items() if v is not None}
    active_weights = {k: SIGNAL_WEIGHTS[k] for k in available}
    total_weight = sum(active_weights.values()) or 1.0
    weighted_sum = sum(available[k] * active_weights[k] for k in available)
    score = round(max(0.0, min(100.0, weighted_sum / total_weight)))

    project.stage = PipelineStage.SCORED
    return score, breakdown
