"""Deterministic relationship detectors. Each detector is a pure(-ish)
function over already-computed evidence -- `all_contexts` (from
`app.project_context.builder.all_project_contexts`, computed once by the
caller), the canonical Assets index, Knowledge cards, and PI dependencies/
capabilities -- and returns zero or more canonical relationship dicts
(`models.make_relationship`). No detector re-derives what another
canonical domain already owns: Assets stays canonical for asset identity/
duplicates, Knowledge stays canonical for card content, ProjectContext
stays canonical for git/health/next-action.

Every detector is additive to `ALL_DETECTORS` at the bottom -- adding a
new one never means editing an if/else chain, only appending a function.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import Settings
from app.project_ecosystem.models import BLOCKING_STATUSES, make_relationship, project_ref

# Bounded documentation read -- identical cap/encoding/error-handling
# convention to `app.discovery.next_action._read_text` and
# `app.explorer.service._read_markdown_excerpt` (both 20_000 bytes,
# utf-8/ignore, swallow OSError to `None`) -- not a new pattern, the same
# one applied a third time for a different purpose (text-reference
# search instead of next-step extraction).
_MAX_READ_BYTES = 20_000
_DOC_FILENAMES = ("README.md", "ROADMAP.md", "CHANGELOG.md", "TODO.md", "NEXT_ACTION.md")

# A project name shorter than this is too likely to false-positive-match
# unrelated text (e.g. a 2-3 letter project nickname appearing inside an
# unrelated word) to use as a text-reference search term.
_MIN_NAME_LENGTH_FOR_TEXT_SEARCH = 4


def _find_case_insensitive(root: Path, name: str) -> Path | None:
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower() == name.lower():
                return entry
    except OSError:
        return None
    return None


def _read_text(path: Path) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(_MAX_READ_BYTES)
    except OSError:
        return None


def _ref_for(context: dict[str, Any]) -> dict[str, Any]:
    return project_ref(
        canonical_project_id=context.get("id"),
        item_id=context.get("item_id"),
        display_name=context.get("display_name"),
    )


def _searchable_contexts(all_contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        c
        for c in all_contexts
        if len(c.get("display_name") or "") >= _MIN_NAME_LENGTH_FOR_TEXT_SEARCH
    ]


def detect_dependencies(
    all_contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """PI Dependencies (`app.projects.db.list_dependencies`) are already
    explicit, user-declared project-to-project edges -- the strongest,
    highest-confidence evidence this engine has. `blocks`/`blocked_by` are
    derived from the same edge: if the depended-on project's own health/
    status looks blocked, the dependency itself becomes blocking evidence.
    """
    from app.projects import db as projects_db

    contexts_by_id = {c["id"]: c for c in all_contexts if c.get("id")}
    relationships = []
    for context in all_contexts:
        canonical_id = context.get("id")
        if not canonical_id:
            continue
        for dep in projects_db.list_dependencies(canonical_id, settings=settings):
            target_context = contexts_by_id.get(dep["depends_on_project_id"])
            target_ref = (
                _ref_for(target_context)
                if target_context
                else project_ref(
                    canonical_project_id=dep["depends_on_project_id"],
                    display_name=dep.get("depends_on_project_name"),
                )
            )
            evidence = ["Explicitly declared PI dependency"]
            if dep.get("note"):
                evidence.append(f"Note: {dep['note']}")
            relationships.append(
                make_relationship(
                    source_project=_ref_for(context),
                    target_project=target_ref,
                    relationship_type="depends_on",
                    confidence=1.0,
                    evidence=evidence,
                    detector="pi_dependencies",
                )
            )

            target_status = (target_context or {}).get("status") or ""
            if target_status.lower() in BLOCKING_STATUSES:
                blocking_message = (
                    f"{target_ref['display_name']} status is '{target_status}' and "
                    f"{context['display_name']} depends on it"
                )
                blocking_evidence = [blocking_message]
                relationships.append(
                    make_relationship(
                        source_project=target_ref,
                        target_project=_ref_for(context),
                        relationship_type="blocks",
                        confidence=0.85,
                        evidence=blocking_evidence,
                        detector="pi_dependencies",
                    )
                )
                relationships.append(
                    make_relationship(
                        source_project=_ref_for(context),
                        target_project=target_ref,
                        relationship_type="blocked_by",
                        confidence=0.85,
                        evidence=blocking_evidence,
                        detector="pi_dependencies",
                    )
                )
    return relationships


def detect_capabilities(
    all_contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """PI Capabilities: a project that consumes another's capability
    `uses` it; the provider `produces` it for that consumer. Both directly
    reuse `app.projects.db`'s existing capability-provide/consume tables --
    no new capability concept."""
    from app.projects import db as projects_db

    contexts_by_id = {c["id"]: c for c in all_contexts if c.get("id")}
    relationships = []
    for context in all_contexts:
        canonical_id = context.get("id")
        if not canonical_id:
            continue
        for cap in projects_db.list_consumed_capabilities(canonical_id, settings=settings):
            provider_context = contexts_by_id.get(cap["project_id"])
            provider_ref = (
                _ref_for(provider_context)
                if provider_context
                else project_ref(
                    canonical_project_id=cap["project_id"],
                    display_name=cap.get("provider_project_name"),
                )
            )
            evidence = [f"Consumes capability '{cap['name']}'"]
            relationships.append(
                make_relationship(
                    source_project=_ref_for(context),
                    target_project=provider_ref,
                    relationship_type="uses",
                    confidence=1.0,
                    evidence=evidence,
                    detector="pi_capabilities",
                )
            )
            relationships.append(
                make_relationship(
                    source_project=provider_ref,
                    target_project=_ref_for(context),
                    relationship_type="produces",
                    confidence=1.0,
                    evidence=[
                        f"Capability '{cap['name']}' is consumed by {context['display_name']}"
                    ],
                    detector="pi_capabilities",
                )
            )
    return relationships


def detect_shared_assets(
    all_contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Reuses the canonical Assets index (`app.assets.service.
    list_all_assets`) verbatim -- `duplicate_group_id` is already resolved
    across every project by that service, so grouping by it and checking
    for 2+ distinct owning projects is the entire detector; no second
    asset mapper or hash computation happens here."""
    from app.assets.service import list_all_assets

    by_group: dict[str, list[Any]] = {}
    for record in list_all_assets(settings=settings):
        if record.duplicate_group_id and record.canonical_project_id:
            by_group.setdefault(record.duplicate_group_id, []).append(record)

    contexts_by_id = {c["id"]: c for c in all_contexts if c.get("id")}
    relationships = []
    for records in by_group.values():
        projects_in_group = {r.canonical_project_id: r for r in records}
        if len(projects_in_group) < 2:
            continue
        project_ids = list(projects_in_group)
        sample_filenames = sorted({r.filename for r in records})[:3]
        for i, source_id in enumerate(project_ids):
            for target_id in project_ids[i + 1 :]:
                source_ctx = contexts_by_id.get(source_id)
                target_ctx = contexts_by_id.get(target_id)
                if not source_ctx or not target_ctx:
                    continue
                evidence = [f"Shares asset file(s): {', '.join(sample_filenames)}"]
                relationships.append(
                    make_relationship(
                        source_project=_ref_for(source_ctx),
                        target_project=_ref_for(target_ctx),
                        relationship_type="shares_assets",
                        confidence=0.9,
                        evidence=evidence,
                        detector="assets_duplicate_hash",
                    )
                )
    return relationships


def detect_shared_knowledge(
    all_contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Reuses Knowledge's own cards verbatim -- the same soft, case-
    insensitive `card['project']` name match `ProjectContext._knowledge_
    count`/Explorer's `project_hub` already use to attribute a card to a
    project. Two projects "share knowledge" when their own cards reference
    the same person/application/vendor."""
    from app import db as knowledge_db

    try:
        cards = knowledge_db.list_all_cards(settings=settings)
    except knowledge_db.DatabaseUnavailableError:
        return []

    contexts_by_name = {(c.get("display_name") or "").strip().lower(): c for c in all_contexts}

    # tag -> {project_key: (context, [evidence tag labels])}
    tag_to_projects: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for card in cards:
        owner = contexts_by_name.get((card.get("project") or "").strip().lower())
        if owner is None:
            continue
        for tag_type, values in (
            ("person", card.get("people") or []),
            ("application", card.get("applications") or []),
            ("vendor", card.get("vendors") or []),
        ):
            for value in values:
                if not value:
                    continue
                key = (tag_type, value.strip().lower())
                bucket = tag_to_projects.setdefault(key, {})
                bucket[owner["id"]] = owner

    relationships = []
    for (tag_type, value), owners in tag_to_projects.items():
        if len(owners) < 2:
            continue
        owner_list = list(owners.values())
        for i, source_ctx in enumerate(owner_list):
            for target_ctx in owner_list[i + 1 :]:
                relationships.append(
                    make_relationship(
                        source_project=_ref_for(source_ctx),
                        target_project=_ref_for(target_ctx),
                        relationship_type="shares_knowledge",
                        confidence=0.6,
                        evidence=[f"Both reference {tag_type} '{value}' in imported conversations"],
                        detector="knowledge_shared_tags",
                    )
                )
    return relationships


def detect_shared_documentation(
    all_contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Bounded read of each project's own README/ROADMAP/CHANGELOG/TODO/
    NEXT_ACTION (same 20KB cap as `discovery.next_action`) searched for
    another project's display name as a literal text reference -- a
    project's docs explicitly naming another project is real, if modest,
    evidence of a documented relationship."""
    searchable = _searchable_contexts(all_contexts)
    relationships = []
    for context in all_contexts:
        root_path = context.get("root_path")
        if not root_path:
            continue
        root = Path(root_path)
        if not root.is_dir():
            continue
        for filename in _DOC_FILENAMES:
            found = _find_case_insensitive(root, filename)
            if not found:
                continue
            text = _read_text(found)
            if not text:
                continue
            text_lower = text.lower()
            for other in searchable:
                if other.get("id") == context.get("id"):
                    continue
                other_name = (other.get("display_name") or "").strip()
                if other_name.lower() in text_lower:
                    relationships.append(
                        make_relationship(
                            source_project=_ref_for(context),
                            target_project=_ref_for(other),
                            relationship_type="shares_documentation",
                            confidence=0.6,
                            evidence=[f"'{filename}' mentions '{other_name}'"],
                            detector="documentation_text_reference",
                        )
                    )
    return relationships


def detect_git_remote_references(
    all_contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """A project's own `git remote get-url origin` (already read by
    Discovery, never re-run here) sometimes names another adopted
    project's repository -- a real, if weak, cross-reference."""
    searchable = _searchable_contexts(all_contexts)
    relationships = []
    for context in all_contexts:
        remote_url = (context.get("git") or {}).get("remote_url")
        if not remote_url:
            continue
        remote_lower = remote_url.lower()
        for other in searchable:
            if other.get("id") == context.get("id"):
                continue
            other_name = (other.get("display_name") or "").strip()
            slug = other_name.lower().replace(" ", "-")
            if slug in remote_lower or other_name.lower().replace(" ", "") in remote_lower.replace(
                "-", ""
            ):
                relationships.append(
                    make_relationship(
                        source_project=_ref_for(context),
                        target_project=_ref_for(other),
                        relationship_type="related",
                        confidence=0.5,
                        evidence=[f"git remote references '{other_name}': {remote_url}"],
                        detector="git_remote_reference",
                    )
                )
    return relationships


def detect_shared_prompts_and_sessions(
    all_contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """A project's latest Session Snapshot or AI Session sometimes
    mentions another project by name (a person working across two
    projects in one conversation) -- weak but real, evidence-carrying
    signal for `shares_prompts`/`shares_sessions`."""
    searchable = _searchable_contexts(all_contexts)
    relationships = []
    for context in all_contexts:
        snapshot = context.get("latest_snapshot") or {}
        session = context.get("latest_ai_session") or {}
        snapshot_text = " ".join(
            str(snapshot.get(f) or "") for f in ("pending_work", "next_prompt", "summary")
        ).lower()
        session_text = " ".join(str(session.get(f) or "") for f in ("title", "notes")).lower()
        for other in searchable:
            if other.get("id") == context.get("id"):
                continue
            other_name = (other.get("display_name") or "").strip().lower()
            if snapshot_text and other_name in snapshot_text:
                relationships.append(
                    make_relationship(
                        source_project=_ref_for(context),
                        target_project=_ref_for(other),
                        relationship_type="shares_prompts",
                        confidence=0.4,
                        evidence=[f"Latest session snapshot mentions '{other['display_name']}'"],
                        detector="snapshot_text_reference",
                    )
                )
            if session_text and other_name in session_text:
                relationships.append(
                    make_relationship(
                        source_project=_ref_for(context),
                        target_project=_ref_for(other),
                        relationship_type="shares_sessions",
                        confidence=0.4,
                        evidence=[f"Latest AI session mentions '{other['display_name']}'"],
                        detector="session_text_reference",
                    )
                )
    return relationships


def detect_sibling_projects(
    all_contexts: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Two adopted top-level projects living under the same parent folder
    are structurally related (shared workspace/runtime folder) even
    absent any other evidence -- a real filesystem-path signal, kept at
    low confidence since sharing a parent folder alone says little about
    the projects' actual relationship."""
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for context in all_contexts:
        if not context.get("is_adopted"):
            continue
        root_path = context.get("root_path")
        if not root_path:
            continue
        parent = str(Path(root_path).parent)
        by_parent.setdefault(parent, []).append(context)

    relationships = []
    for parent, siblings in by_parent.items():
        if len(siblings) < 2:
            continue
        for i, source_ctx in enumerate(siblings):
            for target_ctx in siblings[i + 1 :]:
                relationships.append(
                    make_relationship(
                        source_project=_ref_for(source_ctx),
                        target_project=_ref_for(target_ctx),
                        relationship_type="related",
                        confidence=0.3,
                        evidence=[f"Both are top-level projects under '{parent}'"],
                        detector="sibling_workspace_path",
                    )
                )
    return relationships


ALL_DETECTORS: tuple[Any, ...] = (
    detect_dependencies,
    detect_capabilities,
    detect_shared_assets,
    detect_shared_knowledge,
    detect_shared_documentation,
    detect_git_remote_references,
    detect_shared_prompts_and_sessions,
    detect_sibling_projects,
)
