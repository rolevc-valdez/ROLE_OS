"""Session Intent hotfix acceptance tests: Resume Work must give Claude
an explicit instruction, not just project context. Real Discovery Engine
runs / real PI projects/Daily Sessions throughout, nothing mocked -- same
convention as the rest of this test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.main import app
from app.project_memory.prompt import build_resume_prompt
from app.project_memory.service import build_project_memory
from app.project_memory.session_intent import (
    is_valid_requested_action,
    resolve_requested_action,
)
from app.session import db as session_db
from app.workspace.resume import resume_work
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "projects.db"))
    monkeypatch.setenv("ROLE_OS_ECOSYSTEM_DB_PATH", str(tmp_path / "ecosystem.db"))
    # Isolates the Daily Session domain too (its own table has a "only one
    # active session at a time" constraint) -- without this, tests that
    # start a session here would collide with any session left active by
    # another test file in the same pytest run.
    monkeypatch.setenv("ROLE_OS_SESSION_DB_PATH", str(tmp_path / "session.db"))
    return Settings()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_and_adopt(
    tmp_path: Path, suffix: str, name: str, *, business_value: str | None = None
) -> dict:
    root = tmp_path / f"intent-scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    payload = {"business_value": business_value} if business_value else {}
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json=payload)
    return adopted.json()


def _make_and_adopt_quiet(tmp_path: Path, suffix: str, name: str) -> dict:
    """Unlike `_make_and_adopt`'s bare project (which always earns a real
    "Add tests" Operational Intelligence recommendation -- correctly a
    valid action, not a no-action scenario), this fixture is fully
    documented, tested, and has no git repo, so no Operational
    Intelligence rule fires and no ROADMAP/TODO unchecked item exists --
    a genuine "nothing trustworthy anywhere" case for exercising the
    no-action guard."""
    root = tmp_path / f"intent-scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n\nA fully documented project.\n")
    _write(root / name / "ROADMAP.md", "# Roadmap\n\nNo unchecked items here.\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    _write(root / name / "tests" / "test_x.py", "def test_x(): pass\n")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return adopted.json()


# ---------------------------------------------------------------------------
# Vague action / phase-status row rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_text",
    [
        "Foundation phase active",
        "Deliverables still match what `projects/` files describe",
        "Continue this project",
        "Review project status",
        "Review the project",
        "Keep the momentum going",
        "Make progress",
        "Continue working",
        "",
        None,
        "   ",
    ],
)
def test_invalid_actions_are_rejected(invalid_text):
    assert is_valid_requested_action(invalid_text) is False


@pytest.mark.parametrize(
    "valid_text",
    [
        "Fix the hardcoded absolute-path references found in ROLE_OS",
        "Commit or stash uncommitted changes",
        "Implement and test the Shopify product-write workflow",
        "Update ROADMAP.md with the completed C1-C10 consolidation milestones",
        "Reconcile projects/ROLE_OS.md with the current released architecture",
    ],
)
def test_valid_actions_are_accepted(valid_text):
    assert is_valid_requested_action(valid_text) is True


def test_phase_descriptor_with_active_marker_is_rejected():
    assert is_valid_requested_action("1 -- Foundation -- Active -- ROLE OS, ROLE MASTER") is False


# ---------------------------------------------------------------------------
# Source priority
# ---------------------------------------------------------------------------


def test_active_daily_session_objective_wins_over_everything_else(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "active-session", "Active Session Project")
    session_db.start_session(
        date="2026-08-05",
        project_id=None,
        project_name="Active Session Project",
        mode="Build",
        objective="Fix the Shopify webhook signature verification bug",
        expected_result="Webhook signatures verify correctly",
        settings=settings,
    )
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "Active Session Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": None,
    }
    text, source = resolve_requested_action(
        context, settings, recommendation=None, next_action_output={}
    )
    assert text == "Fix the Shopify webhook signature verification bug"
    assert source == "active_daily_session"


def test_user_selected_objective_from_cockpit_wins_over_every_derived_source(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "user-obj", "User Objective Project")
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "User Objective Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": {"next_prompt": "Fix the login bug"},
    }
    text, source = resolve_requested_action(
        context,
        settings,
        recommendation=None,
        next_action_output={},
        user_objective={"requested_action": "Reconcile the API docs with the current schema"},
    )
    assert text == "Reconcile the API docs with the current schema"
    assert source == "user_provided"


def test_snapshot_next_prompt_priority_when_no_daily_session(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "snapshot", "Snapshot Priority Project")
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "Snapshot Priority Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": {"next_prompt": "Fix the authentication timeout bug"},
    }
    text, source = resolve_requested_action(
        context, settings, recommendation=None, next_action_output={}
    )
    assert text == "Fix the authentication timeout bug"
    assert source == "latest_snapshot.next_prompt"


def test_deterministic_next_action_priority_when_valid(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "next-action", "Next Action Priority Project")
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "Next Action Priority Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": None,
    }
    text, source = resolve_requested_action(
        context,
        settings,
        recommendation=None,
        next_action_output={"text": "Fix hardcoded absolute paths", "source": "NEXT_ACTION.md"},
    )
    assert text == "Fix hardcoded absolute paths"
    assert "next_action" in source


def test_deterministic_next_action_rejected_when_vague_falls_through(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "next-action-vague", "Vague Next Action Project")
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "Vague Next Action Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": None,
    }
    text, source = resolve_requested_action(
        context,
        settings,
        recommendation={"suggested_action": "Fix the broken CI pipeline"},
        next_action_output={"text": "Continue this project", "source": "latest git commit"},
    )
    assert text == "Fix the broken CI pipeline"
    assert source == "operational_intelligence.suggested_action"


def test_operational_intelligence_suggested_action_fallback(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "oi-fallback", "OI Fallback Project")
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "OI Fallback Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": None,
    }
    text, source = resolve_requested_action(
        context,
        settings,
        recommendation={"suggested_action": "Add tests for the payment adapter"},
        next_action_output={},
    )
    assert text == "Add tests for the payment adapter"
    assert source == "operational_intelligence.suggested_action"


def test_roadmap_unchecked_item_fallback(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "roadmap-fallback", "Roadmap Fallback Project")
    root = Path(adopted["root_path"])
    _write(root / "ROADMAP.md", "# Roadmap\n\n- [ ] Migrate the database schema to v2\n")
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "Roadmap Fallback Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": None,
    }
    text, source = resolve_requested_action(
        context, settings, recommendation=None, next_action_output={}
    )
    assert text == "Migrate the database schema to v2"
    assert "ROADMAP.md" in source


def test_todo_unchecked_item_fallback(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "todo-fallback", "Todo Fallback Project")
    root = Path(adopted["root_path"])
    _write(root / "TODO.md", "# TODO\n\n- [ ] Write the deployment documentation\n")
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "Todo Fallback Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": None,
    }
    text, source = resolve_requested_action(
        context, settings, recommendation=None, next_action_output={}
    )
    assert text == "Write the deployment documentation"
    assert "TODO.md" in source


def test_no_valid_action_anywhere_returns_none(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "no-action", "No Action Project")
    context = {
        "id": adopted["canonical_project_id"],
        "display_name": "No Action Project",
        "root_path": adopted["root_path"],
        "latest_snapshot": None,
    }
    text, source = resolve_requested_action(
        context,
        settings,
        recommendation={"suggested_action": "Keep the momentum going"},
        next_action_output={"text": "Continue this project"},
    )
    assert text is None
    assert source is None


# ---------------------------------------------------------------------------
# Expected deliverable
# ---------------------------------------------------------------------------


def test_expected_deliverable_generation_is_never_vague(tmp_path):
    adopted = _make_and_adopt(tmp_path, "deliverable", "Deliverable Project", business_value="high")
    memory = build_project_memory(adopted["canonical_project_id"])
    session_intent = memory["session_intent"]
    assert session_intent is not None
    deliverable = session_intent["expected_deliverable"].lower()
    for banned in ("make progress", "continue working", "review the project"):
        assert banned not in deliverable
    assert session_intent["expected_deliverable"].strip() != ""


def test_completion_criteria_is_present_and_concrete(tmp_path):
    adopted = _make_and_adopt(tmp_path, "criteria", "Criteria Project", business_value="high")
    memory = build_project_memory(adopted["canonical_project_id"])
    session_intent = memory["session_intent"]
    assert session_intent is not None
    assert session_intent["completion_criteria"].strip() != ""


def test_relevant_resources_is_bounded_and_embeds_real_content(tmp_path):
    # A bare project (README.md + pyproject.toml only) reliably earns a
    # real "Add tests" Operational Intelligence recommendation -- what's
    # under test here is `relevant_resources`'s own shape: structured
    # resource dicts with embedded excerpts of real file content, never
    # bare absolute paths (hotfix: a fresh Claude web conversation cannot
    # read local paths).
    adopted = _make_and_adopt(tmp_path, "resources", "Resources Project", business_value="high")
    memory = build_project_memory(adopted["canonical_project_id"])
    session_intent = memory["session_intent"]
    assert session_intent is not None
    resources = session_intent["relevant_resources"]
    assert 1 <= len(resources) <= 8
    for r in resources:
        assert r["resource_name"] == "README.md"
        assert not Path(r["relative_path"]).is_absolute()
        assert "A" in r["excerpt"]
        assert r["excerpt_reason"]
        assert isinstance(r["sensitive_content_redacted"], bool)
        assert isinstance(r["omitted_character_count"], int)
    assert session_intent["context_sufficient"] is True
    assert session_intent["embedded_resource_count"] == len(resources)
    assert session_intent["embedded_character_count"] > 0


# ---------------------------------------------------------------------------
# The no-action guard (requires_user_objective)
# ---------------------------------------------------------------------------


def test_requires_user_objective_true_when_nothing_trustworthy(tmp_path):
    """A fully documented, tested, git-free project -- no daily session,
    no snapshot, no ROADMAP/TODO unchecked item, and no Operational
    Intelligence rule left to fire (has_readme/has_roadmap/has_tests all
    true, no git repo so no commit/dirty rule) -- must trigger the guard
    rather than inventing an action."""
    adopted = _make_and_adopt_quiet(tmp_path, "guard", "Guard Project")
    result = resume_work(adopted["canonical_project_id"])
    assert result["requires_user_objective"] is True
    assert "Guard Project" in result["message"]
    assert "prompt" not in result
    assert "session_id" not in result


def test_no_action_guard_never_creates_a_session(tmp_path):
    adopted = _make_and_adopt_quiet(tmp_path, "guard-no-session", "Guard No Session Project")
    from app.projects import db as projects_db

    before = projects_db.list_ai_sessions(adopted["canonical_project_id"])
    resume_work(adopted["canonical_project_id"])
    after = projects_db.list_ai_sessions(adopted["canonical_project_id"])
    assert len(before) == len(after) == 0


def test_user_objective_resolves_the_guard_and_builds_a_real_prompt(tmp_path):
    adopted = _make_and_adopt_quiet(tmp_path, "guard-resolved", "Guard Resolved Project")
    guarded = resume_work(adopted["canonical_project_id"])
    assert guarded["requires_user_objective"] is True

    resolved = resume_work(
        adopted["canonical_project_id"],
        user_objective={
            "requested_action": "Reconcile the README with the current architecture",
            "expected_deliverable": "README accurately describes the shipped architecture.",
            "completion_criteria": "A reviewer confirms no stale claims remain.",
        },
    )
    assert resolved["requires_user_objective"] is False
    assert "Reconcile the README with the current architecture" in resolved["prompt"]
    assert "Session Intent:" in resolved["prompt"]
    assert "Requested Action:" in resolved["prompt"]
    assert "Expected Deliverable:" in resolved["prompt"]
    assert "Completion Criteria:" in resolved["prompt"]
    assert "Relevant Context:" in resolved["prompt"]
    assert "Execution Instructions:" in resolved["prompt"]
    assert "Read C:\\" not in resolved["prompt"]
    assert "you do not have" in resolved["prompt"]


# ---------------------------------------------------------------------------
# Prompt shape
# ---------------------------------------------------------------------------


def test_prompt_ends_with_session_intent_block_when_present():
    memory = {
        "project_name": "Test Project",
        "project_summary": {"text": "A test project."},
        "current_objective": "Ship v2",
        "where_we_left_off": "Finished the migration",
        "pending_work": "Deploy the migration",
        "next_action": {"text": "Deploy the migration"},
        "operational_recommendation": None,
        "session_intent": {
            "session_intent": "Continue work on Test Project: Deploy the migration",
            "requested_action": "Deploy the migration",
            "expected_deliverable": "Migration deployed to production.",
            "completion_criteria": "Verified via a new Session Snapshot recording the change.",
            "relevant_resources": [
                {
                    "resource_name": "README.md",
                    "relative_path": "README.md",
                    "resource_type": "markdown",
                    "modified_at": "2026-01-01T00:00:00+00:00",
                    "selected_heading": "Overview",
                    "excerpt": "Test Project is a demo project used for prompt-shape tests.",
                    "excerpt_reason": "Defines the project and its purpose.",
                    "omitted_character_count": 0,
                    "sensitive_content_redacted": False,
                },
            ],
        },
    }
    prompt = build_resume_prompt(memory)
    assert prompt.rstrip().endswith(
        "- When finished, report files changed, tests performed, result, and next action."
    )
    assert prompt.index("Session Intent:") > prompt.index("Conversation:")
    assert "Do not ask which project or thread this is." in prompt
    assert "Path: README.md" in prompt
    assert "Test Project is a demo project used for prompt-shape tests." in prompt
    assert "Read C:\\" not in prompt
    assert "do not have direct access" in prompt


def test_prompt_omits_session_intent_block_when_absent():
    memory = {
        "project_name": "Test Project",
        "project_summary": {"text": "A test project."},
        "current_objective": "Ship v2",
        "where_we_left_off": "Finished the migration",
        "pending_work": "",
        "next_action": {},
        "operational_recommendation": None,
        "session_intent": None,
    }
    prompt = build_resume_prompt(memory)
    assert "Session Intent:" not in prompt
    assert "Execution Instructions:" not in prompt


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------


def test_api_returns_requires_user_objective_without_building_a_session(tmp_path):
    adopted = _make_and_adopt_quiet(tmp_path, "api-guard", "Api Guard Project")
    response = client.post(f"/workspace/discovered/{adopted['id']}/resume-work", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_user_objective"] is True
    assert payload.get("session_id") is None


def test_api_accepts_user_objective_and_returns_full_result(settings, tmp_path):
    adopted = _make_and_adopt(tmp_path, "api-resolved", "Api Resolved Project")
    response = client.post(
        f"/workspace/discovered/{adopted['id']}/resume-work",
        json={
            "user_objective": {
                "requested_action": "Write integration tests for the export pipeline",
                "expected_deliverable": "Export pipeline covered by integration tests.",
            }
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_user_objective"] is False
    assert payload["session_id"] is not None
    assert "Write integration tests for the export pipeline" in payload["prompt"]
    assert payload["context_sufficient"] is True
    assert payload["embedded_resource_count"] >= 1
    assert payload["embedded_character_count"] > 0


# ---------------------------------------------------------------------------
# Context Sufficiency Guard (hotfix §7): never send Claude a prompt that
# knowingly requires inaccessible local content.
# ---------------------------------------------------------------------------


def _make_and_adopt_no_docs(tmp_path: Path, suffix: str, name: str) -> dict:
    """A project with no supported documentation at all -- the Context
    Package will have zero resources to embed even once a requested
    action exists (supplied directly as `user_objective`, bypassing the
    no-action guard so the sufficiency guard is what's under test)."""
    root = tmp_path / f"intent-scan-root-{suffix}"
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    adopted = client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return adopted.json()


def test_context_sufficient_guard_blocks_resume_when_no_local_docs(tmp_path):
    adopted = _make_and_adopt_no_docs(tmp_path, "no-docs", "No Docs Project")
    result = resume_work(
        adopted["canonical_project_id"],
        user_objective={"requested_action": "Implement the export pipeline"},
    )
    assert result["requires_user_objective"] is False
    assert result["context_sufficient"] is False
    assert result["missing_context"]
    assert result["embedded_resource_count"] == 0
    assert "prompt" not in result
    assert "session_id" not in result
    assert "No Docs Project" in result["message"]


def test_context_sufficient_guard_never_creates_a_session(tmp_path):
    adopted = _make_and_adopt_no_docs(tmp_path, "no-docs-session", "No Docs Session Project")
    from app.projects import db as projects_db

    before = projects_db.list_ai_sessions(adopted["canonical_project_id"])
    resume_work(
        adopted["canonical_project_id"],
        user_objective={"requested_action": "Implement the export pipeline"},
    )
    after = projects_db.list_ai_sessions(adopted["canonical_project_id"])
    assert len(before) == len(after) == 0


def test_api_reports_context_insufficient_without_local_docs(tmp_path):
    adopted = _make_and_adopt_no_docs(tmp_path, "api-no-docs", "Api No Docs Project")
    response = client.post(
        f"/workspace/discovered/{adopted['id']}/resume-work",
        json={"user_objective": {"requested_action": "Implement the export pipeline"}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["context_sufficient"] is False
    assert payload.get("session_id") is None
    assert payload.get("prompt") is None


def test_prompt_never_instructs_reading_local_paths(tmp_path):
    adopted = _make_and_adopt(tmp_path, "no-claim", "No Claim Project", business_value="high")
    resolved = resume_work(adopted["canonical_project_id"])
    prompt = resolved["prompt"]
    assert "Read C:\\" not in prompt
    assert "read only the listed relevant resources" not in prompt
    assert "you do not have direct access" in prompt
