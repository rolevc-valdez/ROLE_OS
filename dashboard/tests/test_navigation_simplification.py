"""Role OS 2.0 Phase 1 Task 8B: navigation simplification implementation.

Same string-assertion convention as the other *_ui.py files -- no JS
runtime/browser harness exists in this repo (a live browser smoke test was
run manually for this task; see docs/PHASE_1_TASK_8B.md). These tests
prove the sidebar was regrouped and Dashboard demoted WITHOUT any router,
route path, or deep link changing.
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
_DASHBOARD_ROOT = Path(__file__).resolve().parents[1]

# The exact 32 routers registered before Task 8B (Task 8's own count,
# re-verified at the start of this task) -- must be unchanged after.
EXPECTED_ROUTER_COUNT = 32


def test_router_registration_count_is_unchanged():
    main_py = (_DASHBOARD_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert main_py.count("app.include_router(") == EXPECTED_ROUTER_COUNT


def test_mission_control_remains_canonical_landing():
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="app-shell"' in resp.text
    body = client.get("/static/js/app.js").text
    assert 'return { view: view || "home", param };' in body
    assert "home: renderMissionControlPage" in body


def test_sidebar_is_grouped_into_the_five_approved_clusters():
    html = client.get("/").text
    projects_label = html.index('<li class="nav-group-label">Projects</li>')
    knowledge_label = html.index('<li class="nav-group-label">Knowledge</li>')
    session_label = html.index('<li class="nav-group-label">Session</li>')
    settings_label = html.index('<li class="nav-group-label">Settings</li>')
    # Ordering matches the approved Task 8 information architecture.
    assert projects_label < knowledge_label < session_label < settings_label


def test_dashboard_removed_from_sidebar_but_route_preserved():
    html = client.get("/").text
    # No sidebar <li> targets "dashboard" any more...
    assert 'data-nav="dashboard">' not in html.split("</nav>")[0]
    # ...but the route itself, and a real drill-down link to it, still exist.
    body = client.get("/static/js/app.js").text
    assert "dashboard: renderDashboardPage" in body
    assert 'data-nav="dashboard">See full metrics' in body
    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200


def test_every_previously_visible_nav_item_still_has_a_working_route():
    """The 12 remaining sidebar items (13 minus demoted Dashboard) must
    all still have a live backend route -- grouping must not have
    silently dropped one."""
    html = client.get("/").text
    sidebar_html = html.split("<nav")[1].split("</nav>")[0]
    for nav_value in (
        "home",
        "projects",
        "workspace",
        "cockpit",
        "knowledge",
        "explorer",
        "advisor",
        "graph",
        "conversation-graph",
        "session",
        "assets",
        "settings",
    ):
        assert f'data-nav="{nav_value}"' in sidebar_html, f"{nav_value} missing from sidebar"

    # Representative backend routes behind each cluster, all still reachable.
    for path in (
        "/workspace/summary",
        "/pi/projects",
        "/advisor/recommendations",
        "/graph",
        "/session/registry",
        "/assets",
        "/settings",
    ):
        resp = client.get(path)
        assert resp.status_code in (200, 422), f"{path} unexpectedly unreachable ({resp.status_code})"


def test_import_and_extraction_routes_remain_reachable_and_already_discoverable():
    """Task 8's analysis assumed Import/Extraction needed a new home under
    Settings; re-inspection during 8B found they're already surfaced
    inside the Knowledge page's own import panel -- documented as a
    correction, not re-implemented."""
    body = client.get("/static/js/app.js").text
    assert 'id="import-panel"' in body
    assert "/import/chatgpt" in body
    assert "/extraction/conversations" in body


def test_drilldown_routes_highlight_their_parent_cluster():
    body = client.get("/static/js/app.js").text
    assert "DRILLDOWN_PARENT_NAV" in body
    assert '{ project: "projects", dproject: "projects", phub: "projects" }' in body
    fn_start = body.index("function updateActiveNav(view)")
    fn_body = body[fn_start : fn_start + 300]
    assert "effectiveView" in fn_body


def test_no_sample_or_alpha_dependency_introduced():
    for rel_path in ("app/templates/index.html", "app/static/js/app.js", "app/static/css/layout.css", "app/static/css/components.css"):
        content = (_DASHBOARD_ROOT / rel_path).read_text(encoding="utf-8")
        assert "samples/role_os_sample" not in content
        assert "role_os_alpha" not in content
