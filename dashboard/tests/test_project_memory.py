"""Sprint C7.1 (Resume Work Refactor) acceptance tests: Project Memory is
the source of truth for the Resume Prompt; the AI Session is only ever the
transport. Real Discovery Engine / real PI projects throughout, nothing
mocked -- same convention as the rest of this test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.main import app
from app.project_memory.naming import needs_retitle, session_title_for
from app.project_memory.prompt import build_resume_prompt
from app.project_memory.service import (
    _current_objective,
    _next_action_output,
    _pending_work,
    _roadmap_current_phase,
    build_project_memory,
)
from app.project_memory.session_selection import select_best_session
from app.project_memory.summary import build_project_summary
from app.projects import db as projects_db
from app.session import db as session_db
from fastapi.testclient import TestClient

client = TestClient(app)

REQUIRED_SECTIONS = [
    "Project:",
    "Project Summary:",
    "Current Objective:",
    "Where We Left Off:",
    "Pending Work:",
    "Next Action:",
    "Operational Recommendation:",
    "Conversation:",
]


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    monkeypatch.setenv("ROLE_OS_ADVISOR_DB_PATH", str(tmp_path / "advisor.db"))
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "workspace.db"))
    return Settings()


# ---------------------------------------------------------------------------
# Naming: never "Resume Work" / "Untitled" / "Session 1"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_title", ["Resume Work", "Untitled", "Session 1", "", "  ", None])
def test_needs_retitle_flags_disallowed_names(bad_title):
    assert needs_retitle(bad_title) is True


@pytest.mark.parametrize("good_title", ["ROLE OS — Continue Sprint 5", "Refactor auth flow"])
def test_needs_retitle_leaves_real_titles_alone(good_title):
    assert needs_retitle(good_title) is False


def test_session_title_for_matches_the_required_format():
    title = session_title_for("ROLE Commerce Factory", "Shopify Adapter")
    assert title == "ROLE Commerce Factory — Shopify Adapter"


def test_session_title_for_truncates_very_long_objectives():
    title = session_title_for("Project", "x" * 200)
    assert title.startswith("Project — ")
    assert len(title) < 200


def test_session_title_for_falls_back_when_objective_missing():
    title = session_title_for("Project", "")
    assert title == "Project — Continue this project"


# ---------------------------------------------------------------------------
# Session selection: latest active > pinned > preferred > newest
# ---------------------------------------------------------------------------


def test_select_best_session_empty_list():
    session, reason = select_best_session([])
    assert session is None
    assert "no existing" in reason.lower()


def test_select_best_session_prefers_latest_active():
    sessions = [
        {"id": "old-active", "status": "active", "last_used_at": "2026-01-01T00:00:00Z"},
        {"id": "new-active", "status": "active", "last_used_at": "2026-06-01T00:00:00Z"},
        {
            "id": "favorited",
            "status": "paused",
            "favorite": True,
            "last_used_at": "2026-07-01T00:00:00Z",
        },
    ]
    session, reason = select_best_session(sessions)
    assert session["id"] == "new-active"
    assert "active" in reason.lower()


def test_select_best_session_falls_back_to_pinned():
    sessions = [
        {"id": "paused-1", "status": "paused", "favorite": False},
        {
            "id": "pinned",
            "status": "paused",
            "favorite": True,
            "last_used_at": "2026-05-01T00:00:00Z",
        },
    ]
    session, reason = select_best_session(sessions)
    assert session["id"] == "pinned"
    assert "pinned" in reason.lower()


def test_select_best_session_falls_back_to_preferred_current():
    sessions = [
        {"id": "plain", "status": "paused", "favorite": False, "current": False},
        {"id": "current-one", "status": "paused", "favorite": False, "current": True},
    ]
    session, reason = select_best_session(sessions)
    assert session["id"] == "current-one"
    assert "preferred" in reason.lower()


def test_select_best_session_falls_back_to_newest():
    sessions = [
        {"id": "older", "status": "paused", "started_at": "2026-01-01T00:00:00Z"},
        {"id": "newer", "status": "completed", "started_at": "2026-06-01T00:00:00Z"},
    ]
    session, reason = select_best_session(sessions)
    assert session["id"] == "newer"
    assert "newest" in reason.lower()


# ---------------------------------------------------------------------------
# Prompt: exact required section order/labels; Project Memory owns it, not
# the session.
# ---------------------------------------------------------------------------


def _memory(**overrides):
    payload = {
        "project_id": "p1",
        "project_name": "ROLE Commerce Factory",
        "project_summary": {
            "text": "Turns design assets into listed, sellable products across commerce platforms.",
            "source": "README.md",
            "source_path": None,
        },
        "current_objective": "Shopify Adapter",
        "where_we_left_off": "Finished the cart sync",
        "pending_work": "Wire up webhooks",
        "next_action": {"text": "Implement webhook signature verification"},
        "operational_recommendation": None,
        "latest_snapshot": None,
    }
    payload.update(overrides)
    return payload


def test_prompt_sections_appear_in_the_required_order():
    prompt = build_resume_prompt(_memory())
    positions = [prompt.index(section) for section in REQUIRED_SECTIONS]
    assert positions == sorted(positions)
    assert prompt.startswith("Project:\nROLE Commerce Factory")


def test_prompt_never_asks_what_are_we_working_on():
    prompt = build_resume_prompt(_memory())
    assert "what are we working on" not in prompt.lower()
    assert "which thread" not in prompt.lower()
    assert "ROLE Commerce Factory" in prompt
    assert "Shopify Adapter" in prompt


def test_prompt_includes_operational_recommendation_when_present():
    rec = {
        "recommendation": "Consider shipping/launching",
        "reason": "Health score 90 with commercial readiness 'client-ready'",
        "expected_benefit": "Unlocks the commercial/launch value already sitting in this project.",
    }
    prompt = build_resume_prompt(_memory(operational_recommendation=rec))
    assert "Consider shipping/launching" in prompt
    assert "Unlocks the commercial/launch value" in prompt


def test_prompt_is_honest_when_no_recommendation_exists():
    prompt = build_resume_prompt(_memory(operational_recommendation=None))
    assert "No active recommendation for this project right now." in prompt


def test_prompt_conversation_section_names_session_and_reason_not_prompt_source():
    """Session data appears ONLY in the Conversation section -- the AI
    Session never owns any other part of the prompt."""
    prompt = build_resume_prompt(
        _memory(),
        session={"title": "ROLE Commerce Factory — Shopify Adapter", "assistant": "claude"},
        session_selection_reason="latest active session",
    )
    conversation_section = prompt.split("Conversation:\n")[1]
    assert "ROLE Commerce Factory — Shopify Adapter" in conversation_section
    assert "latest active session" in conversation_section


def test_prompt_conversation_section_honest_when_no_session_exists():
    prompt = build_resume_prompt(_memory(), session=None)
    assert "New conversation" in prompt.split("Conversation:\n")[1]


def test_prompt_never_calls_any_external_api():
    import ast
    import inspect

    from app.project_memory import prompt as prompt_module

    tree = ast.parse(inspect.getsource(prompt_module))
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported_modules <= {"__future__", "typing"}


# ---------------------------------------------------------------------------
# build_project_memory: real composition, no re-derivation
# ---------------------------------------------------------------------------


def test_build_project_memory_returns_none_for_unknown_project(settings):
    assert build_project_memory("does-not-exist", settings=settings) is None


def test_build_project_memory_has_every_required_field(settings):
    project = projects_db.create_project(
        name="Memory Test", workspace="Products", settings=settings
    )
    memory = build_project_memory(project["id"], settings=settings)
    assert memory["project_name"] == "Memory Test"
    for field in (
        "project_summary",
        "current_objective",
        "where_we_left_off",
        "pending_work",
        "next_action",
        "operational_recommendation",
    ):
        assert field in memory


def test_build_project_memory_can_skip_operational_recommendation_for_cheap_preview(settings):
    project = projects_db.create_project(
        name="Cheap Preview", workspace="Products", settings=settings
    )
    memory = build_project_memory(
        project["id"], settings=settings, include_operational_recommendation=False
    )
    assert memory["operational_recommendation"] is None


def test_build_project_memory_where_we_left_off_prefers_snapshot(settings):
    project = projects_db.create_project(name="Snap Test", workspace="Products", settings=settings)
    session = projects_db.create_ai_session(project["id"], assistant="claude", settings=settings)
    projects_db.create_ai_session_snapshot(
        session["id"], summary="Halfway through the migration", settings=settings
    )
    memory = build_project_memory(project["id"], settings=settings)
    assert memory["where_we_left_off"] == "Halfway through the migration"


# ---------------------------------------------------------------------------
# Hotfix (post-launch): "What is this project?" -- Project Summary and a
# Pending Work fallback beyond the AI Session Snapshot alone.
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_and_adopt(tmp_path: Path, suffix: str, name: str) -> dict:
    root = tmp_path / f"memory-scan-root-{suffix}"
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return adopted.json()


def test_prompt_project_summary_appears_before_current_objective():
    """The hotfix's core requirement: a fresh conversation must be told
    what the project IS before anything asks what to do about it."""
    prompt = build_resume_prompt(_memory())
    assert prompt.index("Project Summary:") < prompt.index("Current Objective:")
    assert "Turns design assets into listed, sellable products" in prompt


def test_prompt_project_summary_is_honest_when_missing():
    memory = _memory()
    del memory["project_summary"]
    prompt = build_resume_prompt(memory)
    assert "Project Summary:\nNone recorded." in prompt


def test_build_project_summary_prefers_readme(tmp_path):
    root = tmp_path / "proj"
    _write(
        root / "README.md",
        "# Widget Factory\n\n## Purpose\n\nBuilds widgets for the ecosystem, "
        "end to end.\n\n## Getting Started\n\nRun `make build`.\n",
    )
    _write(root / "PROJECT.md", "# Widget Factory\n\nThis text must never be used.\n")
    context = {"display_name": "Widget Factory", "root_path": str(root)}
    result = build_project_summary(context)
    assert result["source"] == "README.md"
    assert "Builds widgets for the ecosystem, end to end." in result["text"]
    assert "must never be used" not in result["text"]


def test_build_project_summary_falls_back_to_project_md(tmp_path):
    root = tmp_path / "proj"
    _write(
        root / "PROJECT.md",
        "# Widget Factory\n\n## Overview\n\nA standalone product spec, no README here.\n",
    )
    context = {"display_name": "Widget Factory", "root_path": str(root)}
    result = build_project_summary(context)
    assert result["source"] == "PROJECT.md"
    assert "A standalone product spec, no README here." in result["text"]


def test_build_project_summary_falls_back_to_roadmap(tmp_path):
    root = tmp_path / "proj"
    _write(
        root / "ROADMAP.md",
        "# Roadmap\n\nThis product ships widgets on a quarterly cadence.\n",
    )
    context = {"display_name": "Widget Factory", "root_path": str(root)}
    result = build_project_summary(context)
    assert result["source"] == "ROADMAP.md"
    assert "This product ships widgets on a quarterly cadence." in result["text"]


def test_build_project_summary_falls_back_to_project_context_when_no_files(tmp_path):
    context = {
        "display_name": "Widget Factory",
        "root_path": str(tmp_path / "does-not-exist"),
        "classification": "Software Project",
        "technology_stack": ["Python", "FastAPI"],
        "business_value": "high",
        "status": "active",
    }
    result = build_project_summary(context)
    assert result["source"] == "ProjectContext"
    assert "Software Project" in result["text"]
    assert "Python" in result["text"]


def test_build_project_summary_falls_back_to_discovery_signals(tmp_path):
    context = {
        "display_name": "Widget Factory",
        "root_path": str(tmp_path / "does-not-exist"),
        "documents_count": 4,
        "documentation_status": "partial",
    }
    result = build_project_summary(context)
    assert result["source"] == "Discovery"
    assert "4 document(s) indexed" in result["text"]


def test_build_project_summary_never_hallucinates_when_nothing_is_known():
    context = {"display_name": "Ghost Project"}
    result = build_project_summary(context)
    assert result["source"] == "none"
    assert "no description found" in result["text"].lower()


def test_build_project_summary_is_bounded_to_150_words(tmp_path):
    root = tmp_path / "proj"
    long_paragraph = " ".join(f"word{i}" for i in range(400))
    _write(root / "README.md", f"# Widget Factory\n\n{long_paragraph}\n")
    context = {"display_name": "Widget Factory", "root_path": str(root)}
    result = build_project_summary(context)
    word_count = len(result["text"].rstrip(".").split())
    assert word_count <= 151  # 150 words + the "..." truncation marker
    assert result["text"].endswith("...")


def test_pending_work_falls_back_to_next_action_when_no_snapshot():
    text = _pending_work(
        snapshot=None,
        next_action={"text": "Implement webhook retries", "source": "TODO.md"},
        recommendation=None,
    )
    assert "Implement webhook retries" in text
    assert "TODO.md" in text


def test_pending_work_falls_back_to_operational_recommendation():
    text = _pending_work(
        snapshot=None,
        next_action={},
        recommendation={
            "recommendation": "Rescan the Workspace",
            "reason": "Discovery data is stale",
        },
    )
    assert "Rescan the Workspace" in text
    assert "Discovery data is stale" in text


def test_pending_work_prefers_snapshot_over_everything_else():
    text = _pending_work(
        snapshot={"pending_work": "Wire up webhooks"},
        next_action={"text": "Some other next action"},
        recommendation={"recommendation": "Some other rec", "reason": "..."},
    )
    assert text == "Wire up webhooks"


def test_pending_work_honest_when_nothing_at_all_is_known():
    assert _pending_work(snapshot=None, next_action={}, recommendation=None) == ""


def test_build_project_memory_pending_work_uses_next_action_without_a_snapshot(tmp_path):
    """Real-world regression: a discovery-adopted project with no AI
    Session Snapshot yet must not report "None recorded." for Pending
    Work when a real NEXT_ACTION.md exists on disk."""
    adopted = _make_and_adopt(tmp_path, "next-action", "Widget Factory")
    root = Path(adopted["root_path"])
    _write(root / "NEXT_ACTION.md", "Finish the Shopify adapter integration.\n")
    client.post("/workspace/rescan", json={"root": str(root.parent)})

    memory = build_project_memory(adopted["canonical_project_id"])
    assert memory["pending_work"]
    assert memory["pending_work"] != ""
    assert "Finish the Shopify adapter integration." in memory["pending_work"]


# ---------------------------------------------------------------------------
# Hotfix (runtime verification): Current Objective and Next Action must
# never collapse into the same text -- the real bug found when tracing
# the actual runtime prompt.
# ---------------------------------------------------------------------------


@pytest.fixture
def session_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_SESSION_DB_PATH", str(tmp_path / "session.db"))
    return Settings()


def test_current_objective_defaults_when_nothing_is_known(session_settings):
    context = {"display_name": "No Signal Project", "root_path": None}
    objective = _current_objective("No Signal Project", context, session_settings)
    assert objective == "Continue this project"


def test_current_objective_prefers_daily_session_objective_matched_by_name(session_settings):
    session_db.start_session(
        date="2026-08-05",
        project_id=None,
        project_name="Widget Factory",
        mode="Build",
        objective="Ship the v2 onboarding flow",
        expected_result="Onboarding flow live",
        settings=session_settings,
    )
    context = {"display_name": "Widget Factory", "root_path": None}
    objective = _current_objective("Widget Factory", context, session_settings)
    assert objective == "Ship the v2 onboarding flow"


def test_current_objective_daily_session_match_is_case_insensitive_and_scoped_by_name(
    session_settings,
):
    session_db.start_session(
        date="2026-08-05",
        project_id=None,
        project_name="widget factory",
        mode="Build",
        objective="Ship the v2 onboarding flow",
        expected_result="Onboarding flow live",
        settings=session_settings,
    )
    context = {"display_name": "Widget Factory", "root_path": None}
    objective = _current_objective("Widget Factory", context, session_settings)
    assert objective == "Ship the v2 onboarding flow"

    other_context = {"display_name": "A Totally Different Project", "root_path": None}
    other_objective = _current_objective(
        "A Totally Different Project", other_context, session_settings
    )
    assert other_objective == "Continue this project"


def test_roadmap_current_phase_reads_the_active_marker(tmp_path):
    root = tmp_path / "proj"
    _write(
        root / "ROADMAP.md",
        "# Roadmap\n\n"
        "| Phase | Name | Status |\n"
        "|---|---|---|\n"
        "| 1 | Foundation | 🟢 Active |\n"
        "| 2 | Creation | ⚪ Planned |\n",
    )
    phase = _roadmap_current_phase(str(root))
    assert phase is not None
    assert "Foundation" in phase
    assert "Active" in phase
    assert "Creation" not in phase


def test_roadmap_current_phase_ignores_top_level_status_metadata(tmp_path):
    """Real-world regression: role-ecosystem's own ROADMAP.md opens with
    `**Status:** Active` (the document's own top-level status, not a
    phase) before its real phase table -- that line must never be
    mistaken for "what phase are we in"."""
    root = tmp_path / "proj"
    _write(
        root / "ROADMAP.md",
        "# Roadmap\n\n"
        "**Version:** 1.0\n"
        "**Status:** Active\n"
        "**Owner:** Someone\n\n"
        "## Roadmap Overview\n\n"
        "| Phase | Name | Status |\n"
        "|---|---|---|\n"
        "| 1 | Foundation | 🟢 Active |\n",
    )
    phase = _roadmap_current_phase(str(root))
    assert phase is not None
    assert "Foundation" in phase
    assert phase != "**Status:** Active"


def test_roadmap_current_phase_ignores_status_legend_table(tmp_path):
    """Real-world regression: role-ecosystem's ROADMAP.md has a status
    LEGEND table (`| 🟢 Active | Currently being executed |`) explaining
    what the emoji means, above its real phase table -- the legend row's
    first cell is the marker itself, not a phase number, and must never
    be mistaken for the actual active phase."""
    root = tmp_path / "proj"
    _write(
        root / "ROADMAP.md",
        "# Roadmap\n\n"
        "## Status Legend\n\n"
        "| Status | Meaning |\n"
        "|---|---|\n"
        "| 🟢 Active | Currently being executed |\n"
        "| ⚪ Planned | Sequenced but dependent |\n\n"
        "## Roadmap Overview\n\n"
        "| Phase | Name | Status |\n"
        "|---|---|---|\n"
        "| 1 | Foundation | 🟢 Active |\n"
        "| 2 | Creation | ⚪ Planned |\n",
    )
    phase = _roadmap_current_phase(str(root))
    assert phase is not None
    assert "Foundation" in phase
    assert "Currently being executed" not in phase


def test_roadmap_current_phase_skips_inactive_lines(tmp_path):
    root = tmp_path / "proj"
    _write(root / "ROADMAP.md", "# Roadmap\n\nPhase 0 is inactive.\nPhase 1 is 🟢 Active.\n")
    phase = _roadmap_current_phase(str(root))
    assert phase is not None
    assert "Phase 1" in phase


def test_current_objective_falls_back_to_roadmap_when_no_daily_session(session_settings, tmp_path):
    root = tmp_path / "proj"
    _write(root / "ROADMAP.md", "# Roadmap\n\n| Phase | Status |\n|---|---|\n| 1 | 🟢 Active |\n")
    context = {"display_name": "Unregistered Project", "root_path": str(root)}
    objective = _current_objective("Unregistered Project", context, session_settings)
    assert "Active" in objective


def test_next_action_output_falls_back_to_operational_intelligence_suggested_action():
    result = _next_action_output(
        next_action={},
        recommendation={
            "recommendation": "Rescan the Workspace",
            "reason": "Discovery data is stale",
            "suggested_action": "Rescan Workspace",
        },
    )
    assert result["text"] == "Rescan Workspace"
    assert result["source"] == "operational_intelligence"


def test_next_action_output_prefers_the_file_based_text():
    result = _next_action_output(
        next_action={"text": "Finish the migration", "source": "NEXT_ACTION.md"},
        recommendation={"suggested_action": "Should never appear"},
    )
    assert result["text"] == "Finish the migration"
    assert result["source"] == "NEXT_ACTION.md"


def test_next_action_output_honest_when_nothing_is_known():
    result = _next_action_output(next_action={}, recommendation=None)
    assert not result.get("text")


def test_current_objective_and_next_action_never_share_a_source(tmp_path):
    """The exact regression: real-world Resume Work validation found
    Current Objective and Next Action rendering identical text because
    both read `next_action.get("text")`. With a real NEXT_ACTION.md and
    no Daily Session/active ROADMAP phase, they must now differ."""
    adopted = _make_and_adopt(tmp_path, "no-dup", "Distinct Fields Project")
    root = Path(adopted["root_path"])
    _write(root / "NEXT_ACTION.md", "Wire up the payment webhook handler.\n")
    client.post("/workspace/rescan", json={"root": str(root.parent)})

    memory = build_project_memory(adopted["canonical_project_id"])
    assert memory["next_action"]["text"] == "Wire up the payment webhook handler."
    assert memory["current_objective"] != memory["next_action"]["text"]
    assert memory["current_objective"] == "Continue this project"
