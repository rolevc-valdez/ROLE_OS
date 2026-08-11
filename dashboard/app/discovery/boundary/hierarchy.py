"""Corpus-level project-boundary assignment (§1-4 of the Sprint 3 brief).

Like `recommendation.container_override.apply_container_child_overrides`,
this is a whole-scan pass, not a per-project rule -- it needs to see every
project's parent/child relationships at once to decide which depth-1
folders are real project roots and how their depth-2 children relate to
them. Run once, after every project has been detected and classified (see
`service.run_audit`).
"""

from __future__ import annotations

from app.discovery.boundary.rules import (
    confidence_from_evidence,
    has_own_strong_markers,
    is_independent_despite_nesting,
    is_substantial_structure,
    matches_internal_folder_name,
)
from app.discovery.identity import compute_item_id
from app.discovery.models import DiscoveredProject
from app.discovery.pipeline import PipelineStage

_HEAVY_ASSET_THRESHOLD = 10


def _content_kind_for_internal_folder(child: DiscoveredProject) -> str:
    heavy_assets = (child.image_count + child.video_count) >= _HEAVY_ASSET_THRESHOLD
    heavy_docs = child.has_readme and (
        child.has_roadmap or child.has_changelog or child.doc_folders
    )
    if heavy_assets and not heavy_docs:
        return "asset_library"
    if heavy_docs:
        return "documentation"
    return "internal_folder"


def _assign_child(child: DiscoveredProject, parent: DiscoveredProject) -> None:
    if child.git.is_repo and is_independent_despite_nesting(child):
        child.item_kind = "project"
        child.is_top_level_project = True
        child.parent_item_id = None
        child.project_root_id = child.item_id
        child.hierarchy_depth = 0
        child.boundary_confidence = 0.7
        child.boundary_evidence = [
            (
                "nested inside another project's folder, but has strong independent-product "
                "evidence of its own (own git remote, roadmap/changelog, high overall "
                "confidence) -- treated as its own top-level project rather than a component"
            )
        ]
        return

    child.parent_item_id = parent.item_id
    child.project_root_id = parent.project_root_id or parent.item_id
    child.hierarchy_depth = parent.hierarchy_depth + 1

    if child.git.is_repo:
        child.item_kind = "repository"
        child.is_nested_repository = True
        child.boundary_confidence = 0.9
        child.boundary_evidence = [f"has its own .git repository, nested under '{parent.name}'"]
        return

    # has_own_strong_markers() re-checks the filesystem at *this exact*
    # path (see rules.py's docstring) rather than trusting
    # `child.tech_markers`, which -- for a child that is itself a
    # container with its own nested children -- would otherwise include
    # marker files belonging to *those* grandchildren too.
    if has_own_strong_markers(child):
        child.item_kind = "component"
        child.boundary_confidence = 0.75
        child.boundary_evidence = [
            f"has its own tech stack marker file(s), nested under '{parent.name}'"
        ]
        return

    if matches_internal_folder_name(child.name):
        child.is_internal_folder = True
        child.item_kind = _content_kind_for_internal_folder(child)
        child.boundary_confidence = 0.85
        child.boundary_evidence = [
            f"folder name matches a known internal-structure pattern, nested under '{parent.name}'"
        ]
        return

    child.item_kind = "unknown"
    child.boundary_confidence = 0.3
    child.boundary_evidence = [
        (
            f"nested under '{parent.name}' but shows no clear repository/component/"
            "internal-folder signal -- needs manual review"
        )
    ]


def _assign_top_level(project: DiscoveredProject, children: list[DiscoveredProject]) -> None:
    own_markers = has_own_strong_markers(project)
    children_with_markers = [c for c in children if has_own_strong_markers(c)]
    substantial_structure = is_substantial_structure(project, len(children))

    promote = own_markers or bool(children_with_markers) or substantial_structure

    if promote:
        evidence: list[str] = []
        if own_markers:
            if project.git.is_repo:
                evidence.append("has its own .git repository")
            if project.tech_markers:
                evidence.append(
                    f"has {len(project.tech_markers)} tech stack marker file(s) of its own"
                )
        if children_with_markers:
            names = ", ".join(c.name for c in children_with_markers)
            evidence.append(
                f"contains {len(children_with_markers)} nested folder(s) with their own "
                f"repository/package markers ({names})"
            )
        if substantial_structure:
            evidence.append(
                f"has a README plus substantial internal structure "
                f"({len(children)} internal folder(s); roadmap={project.has_roadmap}, "
                f"changelog={project.has_changelog})"
            )

        project.item_kind = "project"
        project.is_top_level_project = True
        project.parent_item_id = None
        project.project_root_id = project.item_id
        project.hierarchy_depth = 0
        project.boundary_confidence = confidence_from_evidence(
            own_markers, bool(children_with_markers), substantial_structure
        )
        project.boundary_evidence = evidence

        for child in children:
            _assign_child(child, project)
    else:
        project.item_kind = "non_project" if project.classification == "Non-project" else "unknown"
        project.is_top_level_project = False
        project.boundary_confidence = 0.2 if project.item_kind == "unknown" else 0.05
        project.boundary_evidence = [
            (
                "no top-level project boundary evidence found (no own repository/package "
                "markers, no nested folder with its own markers, no substantial "
                "documentation structure)"
            )
        ]
        # This container wasn't promoted, so its "children" (found by the
        # scanner's own is_candidate_signal check) never got a parent to
        # attach to -- evaluate each one as if it were standalone, so a real
        # project buried inside an unrecognized container is never silently
        # dropped.
        for child in children:
            _assign_standalone(child)


def _assign_standalone(project: DiscoveredProject) -> None:
    """A depth>=2 candidate whose parent folder was not recognized as a
    project. Falls back to evaluating it purely on its own evidence."""
    if has_own_strong_markers(project):
        project.item_kind = "project"
        project.is_top_level_project = True
        project.parent_item_id = None
        project.project_root_id = project.item_id
        project.hierarchy_depth = 0
        project.boundary_confidence = 0.6
        project.boundary_evidence = [
            (
                "its parent folder was not itself recognized as a project, so this nested "
                "folder is treated as its own independent top-level project based on its "
                "own repository/package markers"
            )
        ]
    else:
        project.item_kind = "non_project" if project.classification == "Non-project" else "unknown"
        project.is_top_level_project = False
        project.boundary_confidence = 0.1
        project.boundary_evidence = [
            (
                "no clear project boundary evidence, and its parent folder was not "
                "recognized as a project either"
            )
        ]


def assign_boundaries(projects: list[DiscoveredProject]) -> None:
    """Whole-scan pass: assigns item_id/item_kind/parent/hierarchy fields to
    every project in place. Excluded stubs (`item_kind == "excluded"`,
    already fully populated by `excluded_stub.build_excluded_project`) are
    left untouched."""
    for project in projects:
        if not project.item_id:
            project.item_id = compute_item_id(project.root_path)

    by_parent: dict[str, list[DiscoveredProject]] = {}
    for p in projects:
        if p.parent_path:
            by_parent.setdefault(p.parent_path, []).append(p)

    depth1 = [p for p in projects if p.depth <= 1 and p.item_kind != "excluded"]
    for project in depth1:
        _assign_top_level(project, by_parent.get(project.root_path, []))

    for project in projects:
        project.stage = PipelineStage.BOUNDARY
