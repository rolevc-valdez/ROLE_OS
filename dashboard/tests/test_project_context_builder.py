"""Tests for the ProjectContext builder (Sprint C1: Consolidation) --
`app.project_context.builder`. Real Discovery Engine runs against
synthetic folder trees throughout -- nothing mocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.project_context import builder
from app.projects import db as projects_db
from app.workspace import service


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "proj" / "projects.db"))
    monkeypatch.setenv("ROLE_OS_DB_PATH", str(tmp_path / "knowledge" / "role_os.db"))
    return Settings()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _adopt_real_project(tmp_path, settings, name="my-app"):
    root = tmp_path / "scan-root"
    _write(root / name / "README.md", "x")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    service.rescan(settings=settings, root=str(root))
    items = service.list_hierarchy(view="top_level", settings=settings)
    item = next(i for i in items if i["name"] == name)
    service.adopt_item(item["id"], settings=settings)
    return item


def test_returns_none_when_neither_identity_resolves(settings):
    assert builder.build_project_context(item_id="nope", settings=settings) is None
    assert builder.build_project_context(project_id="nope", settings=settings) is None
    assert builder.build_project_context(settings=settings) is None


def test_build_by_item_id_for_an_adopted_project(tmp_path, settings):
    item = _adopt_real_project(tmp_path, settings)
    ctx = builder.build_project_context(item_id=item["id"], settings=settings)
    assert ctx is not None
    assert ctx["display_name"] == "my-app"
    assert ctx["item_id"] == item["id"]
    assert ctx["is_discovered"] is True
    assert ctx["is_adopted"] is True
    assert ctx["resume_state"]["available"] is True
    assert ctx["id"] == ctx["canonical_id"] == ctx["project_id"]


def test_build_by_canonical_project_id_resolves_same_context_as_by_item_id(tmp_path, settings):
    item = _adopt_real_project(tmp_path, settings)
    by_item = builder.build_project_context(item_id=item["id"], settings=settings)
    by_project = builder.build_project_context(project_id=by_item["id"], settings=settings)
    assert by_project is not None
    assert by_project["id"] == by_item["id"]
    assert by_project["display_name"] == by_item["display_name"]
    assert by_project["item_id"] == item["id"]  # resolved back via discovery_item_id


def test_purely_manual_project_has_no_discovery_side_but_still_resolves(settings):
    project = projects_db.create_project(
        name="Manual Only", workspace="Products", settings=settings
    )
    ctx = builder.build_project_context(project_id=project["id"], settings=settings)
    assert ctx is not None
    assert ctx["is_discovered"] is False
    assert ctx["item_id"] is None
    assert ctx["git"] == {}
    # Sprint C1B: `resume_state` reflects the real Resume Work
    # orchestration (`workspace.resume.preview_resume_state`), which is
    # available for *any* real Project row, manual or discovered -- Resume
    # Work has never actually required a Workspace/discovery adoption, only
    # a valid canonical project id. C1's `resume_state.available` was tied
    # to `is_adopted` (a discovery-only concept), which made every manual
    # project's resume_state a false negative.
    assert ctx["resume_state"]["available"] is True
    assert ctx["resume_state"]["is_new_session_needed"] is True


def test_manual_project_next_action_falls_back_to_latest_snapshot(settings):
    """Regression: Cockpit's own JS previously computed `next_action`
    ad hoc as `latestSnapshot.next_prompt || "..."` with no source
    field/confidence and no fallback beyond the snapshot. The shared
    builder must produce an equivalent (but now centrally-computed)
    `next_action` for a purely-manual project too, not just for
    discovered ones (which already got this from `extract_next_action`)."""
    project = projects_db.create_project(
        name="Manual Only", workspace="Products", settings=settings
    )
    session = projects_db.create_ai_session(project["id"], assistant="claude", settings=settings)
    projects_db.create_ai_session_snapshot(
        session["id"], next_prompt="ship the release", settings=settings
    )
    ctx = builder.build_project_context(project_id=project["id"], settings=settings)
    assert ctx["next_action"]["text"] == "ship the release"
    assert ctx["next_action"]["source"] == "ai_session"


def test_discovered_project_next_action_prefers_discovery_extraction(tmp_path, settings):
    """A discovered/adopted project's `next_action` still comes from
    `extract_next_action` (NEXT_ACTION.md/TODO.md/ROADMAP.md/README/
    CHANGELOG/git commit), not the manual-project fallback above -- the
    fallback only ever fires when there is no Workspace item at all."""
    root = tmp_path / "scan-root"
    _write(root / "my-app" / "README.md", "x")
    _write(root / "my-app" / "NEXT_ACTION.md", "Ship the thing\n")
    _write(root / "my-app" / "pyproject.toml", "[project]\nname='a'")
    service.rescan(settings=settings, root=str(root))
    items = service.list_hierarchy(view="top_level", settings=settings)
    item = next(i for i in items if i["name"] == "my-app")
    service.adopt_item(item["id"], settings=settings)

    ctx = builder.build_project_context(item_id=item["id"], settings=settings)
    assert ctx["next_action"]["text"] == "Ship the thing"
    assert ctx["next_action"]["source"] == "NEXT_ACTION.md"


def test_health_tier_bucketing():
    """Sprint C1B: `_health_tier` moved to `app.project_context.health.
    health_tier` -- the one place these thresholds exist, imported (not
    duplicated) by both the builder and, by contract, required to be the
    only place the frontend's `healthTier` fallback is kept in sync with."""
    from app.project_context.health import health_tier

    assert health_tier(None) is None
    assert health_tier(90) == "healthy"
    assert health_tier(80) == "healthy"
    assert health_tier(79) == "warning"
    assert health_tier(50) == "warning"
    assert health_tier(49) == "critical"
    assert health_tier(0) == "critical"


def test_advisor_summary_normalizes_workspace_advisor_shape(tmp_path, settings):
    root = tmp_path / "scan-root"
    _write(root / "my-app" / "pyproject.toml", "[project]\nname='a'")
    # No README/roadmap/tests -- triggers Workspace Advisor's rule_no_readme.
    service.rescan(settings=settings, root=str(root))
    items = service.list_hierarchy(view="top_level", settings=settings)
    item = next(i for i in items if i["name"] == "my-app")
    service.adopt_item(item["id"], settings=settings)

    ctx = builder.build_project_context(item_id=item["id"], settings=settings)
    assert ctx["advisor_summary"], "expected at least one recommendation"
    for rec in ctx["advisor_summary"]:
        assert set(rec.keys()) == {
            "title",
            "reason",
            "evidence",
            "priority",
            "confidence",
            "action_link",
            "source",
        }
        assert rec["source"] in ("workspace_advisor", "advisor")


def test_knowledge_count_never_raises_when_knowledge_db_missing(settings):
    # settings.db_path points at a nonexistent file in this fixture --
    # the soft cross-reference must degrade to 0, never propagate an error.
    ctx = builder.build_project_context(
        project_id=projects_db.create_project(name="X", workspace="Products", settings=settings)[
            "id"
        ],
        settings=settings,
    )
    assert ctx["knowledge_count"] == 0


def test_bulk_variant_matches_single_item_identity_and_skips_expensive_fields(tmp_path, settings):
    item = _adopt_real_project(tmp_path, settings)
    bulk = builder.build_project_contexts_for_workspace(adopted_only=True, settings=settings)
    assert len(bulk) == 1
    assert bulk[0]["item_id"] == item["id"]
    # Cost knobs: bulk intentionally omits the expensive per-item Epic 2
    # advisor call and full timeline (see builder.py's `_assemble` docstring).
    assert bulk[0]["timeline"] == []
    single = builder.build_project_context(item_id=item["id"], settings=settings)
    assert single["id"] == bulk[0]["id"]
    assert single["display_name"] == bulk[0]["display_name"]


def test_bulk_variant_excludes_unadopted_items_by_default(tmp_path, settings):
    root = tmp_path / "scan-root"
    _write(root / "my-app" / "README.md", "x")
    _write(root / "my-app" / "pyproject.toml", "[project]\nname='a'")
    service.rescan(settings=settings, root=str(root))
    # Never adopted.
    bulk = builder.build_project_contexts_for_workspace(adopted_only=True, settings=settings)
    assert bulk == []
