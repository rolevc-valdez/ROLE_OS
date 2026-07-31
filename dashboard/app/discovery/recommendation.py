"""Move/keep recommendation for a discovered folder.

One of exactly six actions, chosen by deterministic rules over signals
`classifier.py` and `health.py` already computed -- no filesystem access, no
ML, always paired with the specific reasons behind the call so a human can
override it. This module only *recommends*; nothing here moves, renames,
merges, or deletes anything.
"""

from __future__ import annotations

from app.discovery.models import DiscoveredProject

VALID_ACTIONS = (
    "Leave where it is",
    "Move into IA PROJECTS",
    "Archive",
    "Merge with another project",
    "Rename",
    "Requires manual review",
)

_REAL_PROJECT_KINDS = {"Software Project", "Website", "Mixed Project"}


def recommend(project: DiscoveredProject) -> tuple[str, list[str]]:
    """Returns (action, reasons). `project` must already be classified and
    have a `health_score` (see `classifier.classify` / `health.compute_health`)."""
    reasons: list[str] = []

    if project.classification == "Non-project":
        if project.total_files == 0 or (project.maturity == "stale" and project.total_files < 5):
            reasons.append(
                f"classified Non-project, stale, and only {project.total_files} file(s) "
                "-- looks like an empty or abandoned folder"
            )
            return "Archive", reasons
        reasons.append("classified Non-project -- not something the Discovery Engine should manage")
        return "Leave where it is", reasons

    if project.move_risk == "high":
        reasons.append(
            f"move risk is high ({'; '.join(project.move_risk_reasons)}) -- "
            "fix hardcoded paths/config before relocating"
        )
        return "Requires manual review", reasons

    if project.classification == "Brand / Asset Project":
        if project.maturity == "stale":
            reasons.append("stale asset collection with no code or docs signal")
            return "Archive", reasons
        reasons.append("asset collection, not a codebase -- keep with other creative assets")
        return "Leave where it is", reasons

    if project.classification == "Documentation Project":
        reasons.append("documentation-only folder -- confirm it belongs with the project it documents")
        return "Requires manual review", reasons

    if project.classification in _REAL_PROJECT_KINDS:
        if project.maturity == "stale":
            reasons.append(f"real project but stale (classification={project.classification})")
            return "Archive", reasons
        score = project.health_score if project.health_score is not None else 0
        if project.move_risk in {"low", "medium"} and score >= 50:
            reasons.append(
                f"{project.classification.lower()} with health score {score} and "
                f"{project.move_risk} move risk -- safe to consolidate into IA PROJECTS"
            )
            return "Move into IA PROJECTS", reasons
        reasons.append(
            f"{project.classification.lower()} but health score {score} is below the "
            "confidence threshold for an automatic move"
        )
        return "Requires manual review", reasons

    reasons.append(f"unclassified signal mix (classification={project.classification})")
    return "Requires manual review", reasons


def apply_container_child_overrides(projects: list[DiscoveredProject]) -> None:
    """Post-process pass across one scan's results: if a depth-1 folder's
    *only* nested project shares its (normalized) name -- e.g.
    `AGUA-AZUL-APP/agua-azul-app` -- the outer folder is very likely a bare
    container wrapping a single inner project, not two separate projects.
    Overrides the *outer* folder's recommendation to `Rename` (flatten it
    away) in place; the inner project's own recommendation is untouched.
    """

    def normalize(name: str) -> str:
        return "".join(ch for ch in name.lower() if ch.isalnum())

    by_parent: dict[str, list[DiscoveredProject]] = {}
    for p in projects:
        if p.parent_path:
            by_parent.setdefault(p.parent_path, []).append(p)

    for project in projects:
        children = by_parent.get(project.root_path)
        if not children or len(children) != 1:
            continue
        child = children[0]
        if normalize(child.name) != normalize(project.name):
            continue
        if project.move_risk == "high":
            continue  # manual review already takes priority
        project.recommendation = "Rename"
        project.recommendation_reasons = [
            f"this folder's only nested project ('{child.name}') has the same name -- "
            "it looks like a redundant wrapper folder; consider flattening "
            f"'{child.name}' up one level instead of keeping both"
        ]
