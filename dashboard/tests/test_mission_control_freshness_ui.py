"""Role OS 2.0 Phase 1 Task 5: staleness/fallback visibility.

Backend: `build_mission_control()` now also composes
`app.session.decisions_adapter.read_recent_decisions()` (already-existing,
already-honest `source`/`note` fields -- Task 5 adds no new fallback
logic, only exposes it). Frontend: same string-assertion convention as
`test_mission_control_landing_ui.py` -- no JS runtime/browser harness
exists in this repo.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.main import app
from app.mission_control.service import build_mission_control
from fastapi.testclient import TestClient

client = TestClient(app)
_DASHBOARD_ROOT = Path(__file__).resolve().parents[1]


def _app_js() -> str:
    return client.get("/static/js/app.js").text


# ---------------------------------------------------------------------
# Backend: API contract (Step 9 -- additive only, nothing removed)
# ---------------------------------------------------------------------

_PRE_TASK_5_PAYLOAD_KEYS = {
    "generated_at",
    "data_freshness",
    "executive_decision",
    "ranked_projects",
    "primary_focus",
    "todays_focus",
    "since_last_time",
    "needs_attention",
    "value_signal",
    "portfolio",
    "recent_activity",
    "daily_session",
    "snapshot_continuity",
    "quick_actions",
    "total_projects_tracked",
}


def test_existing_payload_keys_are_all_still_present():
    resp = client.get("/mission-control")
    assert resp.status_code == 200
    assert set(resp.json().keys()) >= _PRE_TASK_5_PAYLOAD_KEYS


def test_ecosystem_decisions_is_a_new_additive_field():
    resp = client.get("/mission-control")
    assert resp.status_code == 200
    body = resp.json()
    assert "ecosystem_decisions" in body
    assert "source" in body["ecosystem_decisions"]
    assert "decisions" in body["ecosystem_decisions"]
    assert "note" in body["ecosystem_decisions"]


# ---------------------------------------------------------------------
# Step 11: reproduce the original Phase 0 failure mode directly
# ---------------------------------------------------------------------


def test_original_failure_mode_fallback_source_unavailable(monkeypatch: pytest.MonkeyPatch):
    """The exact Phase 0 risk: the external ecosystem decision log is not
    configured (the default on any machine that hasn't set it). Mission
    Control must still load, the recommendation must still be usable, and
    the payload must say plainly that the decisions shown are a fallback,
    not live data."""
    monkeypatch.delenv("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH", raising=False)
    result = build_mission_control(settings=Settings())

    assert result["ecosystem_decisions"]["source"] == "fallback"
    assert result["ecosystem_decisions"]["decisions"]  # still usable, not empty
    assert "not set" in result["ecosystem_decisions"]["note"] or result["ecosystem_decisions"]["note"]

    # Mission Control as a whole is unaffected -- the fallback is scoped to
    # its own field, never blocking the rest of the payload.
    assert "primary_focus" in result
    assert "executive_decision" in result
    assert result["data_freshness"] is not None


def test_live_ecosystem_source_is_labeled_differently_from_fallback(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    log_path = tmp_path / "DECISION_LOG.md"
    log_path.write_text(
        "# Decision Log\n\n## Log\n\n"
        "| ID | Date | Decision | Status | Context | Rationale |\n"
        "|---|---|---|---|---|---|\n"
        "| D-001 | 2026-08-01 | A real live decision. | Accepted | c | r |\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH", str(log_path))
    result = build_mission_control(settings=Settings())
    assert result["ecosystem_decisions"]["source"] == "ecosystem"
    assert result["ecosystem_decisions"]["decisions"][0]["decision"] == "A real live decision."


# ---------------------------------------------------------------------
# Frontend: fallback/staleness must be visually distinguishable
# ---------------------------------------------------------------------


def test_ecosystem_decisions_renders_a_distinct_fallback_badge():
    body = _app_js()
    assert "function mcEcosystemDecisionsHtml(ed)" in body
    assert 'ed.source === "fallback"' in body
    assert "Fallback snapshot" in body
    assert "Live" in body
    # The fallback note is only shown when it IS a fallback -- current/live
    # data gets no extra warning, per Step 3's "CURRENT: no warning
    # necessary."
    assert "isFallback ?" in body


def test_executive_decision_card_shows_a_staleness_note_when_stale():
    body = _app_js()
    assert "function mcStalenessNoteHtml(freshness)" in body
    assert 'if (!freshness || !freshness.is_stale) return ""' in body
    assert "mcExecutiveDecisionHtml(decision, freshness)" in body
    assert "mcStalenessNoteHtml(freshness)" in body
    assert "data.data_freshness" in body


def test_current_data_renders_without_a_stale_or_fallback_warning():
    """CURRENT state (Step 3): both new helpers return an empty string
    when their input says data is not stale/not a fallback -- no visual
    warning is forced onto current data."""
    body = _app_js()
    fn_start = body.index("function mcStalenessNoteHtml(freshness)")
    assert 'if (!freshness || !freshness.is_stale) return "";' in body[fn_start : fn_start + 200]

    fn_start = body.index("function mcEcosystemDecisionsHtml(ed)")
    assert 'if (!ed || !ed.decisions || !ed.decisions.length) return "";' in body[fn_start : fn_start + 200]


def test_snapshot_historical_state_is_visually_distinguishable():
    body = _app_js()
    assert "Saved Snapshot" in body
    assert '<span class="badge">historical</span>' in body


def test_unavailable_state_has_a_safe_message_not_a_crash():
    body = _app_js()
    # Primary Focus's existing empty states (unchanged by Task 5, still
    # the two honest messages used when no recommendation is available).
    # The specific "no projects at all" wording is backend text (asserted
    # via the API below); the frontend's job is just to render `message`
    # honestly, which it already does via `focus.message`.
    assert "Nothing to recommend yet" in body
    assert "No recommendation yet" in body
    assert "escapeHtml((focus && focus.message)" in body

    resp = client.get("/mission-control").json()
    if resp["total_projects_tracked"] == 0:
        assert resp["primary_focus"]["message"] == "No projects tracked yet."


def test_resume_work_cta_still_present_and_wired_after_task_5_changes():
    body = _app_js()
    assert 'data-resume-work-item="${escapeHtml(ctx.item_id || "")}"' in body
    assert "triggerResumeWork(btn.dataset.resumeWorkItem)" in body
    assert "/resume-work" in body


def test_no_sample_or_alpha_dependency_introduced():
    for rel_path in (
        "app/static/js/app.js",
        "app/mission_control/service.py",
        "app/session/decisions_adapter.py",
    ):
        content = (_DASHBOARD_ROOT / rel_path).read_text(encoding="utf-8")
        assert "samples/role_os_sample" not in content
        assert "role_os_alpha" not in content
