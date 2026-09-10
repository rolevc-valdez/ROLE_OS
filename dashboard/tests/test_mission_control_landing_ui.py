"""Role OS 2.0 Phase 1 Task 4: Mission Control as the canonical landing
experience. Same string-assertion style as the other *_ui.py files -- no
JS runtime/browser test harness exists in this repo (a live browser smoke
test was run manually for this task; see docs/PHASE_1_TASK_4.md).

These tests deliberately do not re-test `build_mission_control()` itself
(see test_mission_control_api.py) -- Task 4 changed only DOM order and
headings in `renderMissionControlPage()`, never the backend composition,
so what needs proving here is: (a) `/` is the canonical landing route
that renders Mission Control, (b) the three-question hierarchy and the
Resume Work CTA are present in that render, and (c) nothing new depends
on sample/demo data.
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
_DASHBOARD_ROOT = Path(__file__).resolve().parents[1]


def test_root_serves_the_app_shell_that_defaults_to_mission_control():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="app-shell"' in resp.text
    assert 'id="view-root"' in resp.text

    body = client.get("/static/js/app.js").text
    # parseHash() defaults to "home", and routes["home"] is Mission
    # Control -- this is the actual mechanism making "/" the landing
    # route (Sprint C5), unchanged by Task 4.
    assert 'return { view: view || "home", param };' in body
    assert "home: renderMissionControlPage" in body
    assert '"mission-control": renderMissionControlPage' in body


def test_mission_control_api_still_loads():
    resp = client.get("/mission-control")
    assert resp.status_code == 200
    assert "primary_focus" in resp.json()


def test_where_i_left_off_is_the_first_content_section():
    body = client.get("/static/js/app.js").text
    # Start at the template literal itself (`viewRoot.innerHTML = \``), not
    # the function declaration -- the function's own explanatory comment
    # mentions section names too, which would otherwise be matched first.
    fn_start = body.index("async function renderMissionControlPage()")
    skeleton_start = body.index("viewRoot.innerHTML = `", fn_start)
    skeleton_end = body.index("data = await fetchJSON", skeleton_start)
    skeleton = body[skeleton_start:skeleton_end]

    where_left_off = skeleton.index("Where I Left Off")
    what_matters_now = skeleton.index("What Matters Now")
    whats_next = skeleton.index("What's Next")
    portfolio_ranking = skeleton.index("Portfolio Ranking")

    # The exact ordering Task 4 requires: the three questions answered
    # before any analytics grid, not after it.
    assert where_left_off < what_matters_now < whats_next < portfolio_ranking

    # "Where I Left Off" must wrap the existing Primary Focus/Snapshot
    # Continuity mount point, not a new one.
    assert skeleton.index("mc-primary-focus") > where_left_off
    assert skeleton.index("mc-primary-focus") < what_matters_now


def test_what_matters_now_wraps_the_existing_executive_decision_card():
    body = client.get("/static/js/app.js").text
    # Start at the template literal itself (`viewRoot.innerHTML = \``), not
    # the function declaration -- the function's own explanatory comment
    # mentions section names too, which would otherwise be matched first.
    fn_start = body.index("async function renderMissionControlPage()")
    skeleton_start = body.index("viewRoot.innerHTML = `", fn_start)
    skeleton_end = body.index("data = await fetchJSON", skeleton_start)
    skeleton = body[skeleton_start:skeleton_end]
    what_matters_now = skeleton.index("What Matters Now")
    mc_executive_decision = skeleton.index("mc-executive-decision")
    whats_next = skeleton.index("What's Next")
    assert what_matters_now < mc_executive_decision < whats_next


def test_continue_working_resume_work_cta_is_present_and_reuses_existing_resume_work():
    body = client.get("/static/js/app.js").text
    # The CTA itself (inside the Primary Focus card, now under "Where I
    # Left Off"): a primary button, disabled (not hidden/broken) when no
    # resumable target exists -- Step 6's "useful explanation instead of
    # a broken button" is the existing disabled-state pattern.
    assert 'data-resume-work-item="${escapeHtml(ctx.item_id || "")}"' in body
    assert '${resumeAvailable ? "" : "disabled"}' in body
    assert "Resume Work" in body

    # Wiring reuses the one existing resume mechanism -- no parallel
    # implementation.
    assert 'btn.addEventListener("click", () => triggerResumeWork(btn.dataset.resumeWorkItem))' in body
    assert "/resume-work" in body
    assert 'result.execution_target === "claude_code"' in body
    assert 'result.execution_target === "user_choice"' in body


def test_missing_state_produces_a_safe_empty_state_not_a_fabricated_one():
    body = client.get("/static/js/app.js").text
    assert "Nothing to recommend yet" in body
    assert "No recommendation yet" in body


def test_landing_page_introduces_no_sample_or_demo_runtime_dependency():
    for rel_path in ("app/static/js/app.js", "app/mission_control/service.py"):
        content = (_DASHBOARD_ROOT / rel_path).read_text(encoding="utf-8")
        assert "samples/role_os_sample" not in content
        assert "role_os_alpha" not in content
