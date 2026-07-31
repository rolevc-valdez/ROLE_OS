"""Corpus-level post-process pass, run once across a whole scan's results
(not a per-project rule, since it needs to see every project's parent/child
relationships at once -- see `service.run_audit`, which calls this after
`engine.recommend()` has run for every project).
"""

from __future__ import annotations

from app.discovery.models import DiscoveredProject


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def apply_container_child_overrides(projects: list[DiscoveredProject]) -> None:
    """If a depth-1 folder's *only* nested project shares its (normalized)
    name -- e.g. `AGUA-AZUL-APP/agua-azul-app` -- the outer folder is very
    likely a bare container wrapping a single inner project, not two
    separate projects. Overrides the *outer* folder's recommendation to
    `Rename` (flatten it away) in place; the inner project's own
    recommendation is untouched.

    Precedence note: this runs *after* every project has already gone
    through `engine.recommend()`, and takes precedence over that result
    -- except when the outer folder's own move risk is high, in which case
    `rules.high_move_risk`'s "Requires manual review" already takes
    priority and this override does not apply.
    """
    by_parent: dict[str, list[DiscoveredProject]] = {}
    for p in projects:
        if p.parent_path:
            by_parent.setdefault(p.parent_path, []).append(p)

    for project in projects:
        children = by_parent.get(project.root_path)
        if not children or len(children) != 1:
            continue
        child = children[0]
        if _normalize(child.name) != _normalize(project.name):
            continue
        if project.move_risk == "high":
            continue  # manual review already takes priority
        project.recommendation = "Rename"
        project.recommendation_reasons = [
            f"this folder's only nested project ('{child.name}') has the same name -- "
            "it looks like a redundant wrapper folder; consider flattening "
            f"'{child.name}' up one level instead of keeping both"
        ]
