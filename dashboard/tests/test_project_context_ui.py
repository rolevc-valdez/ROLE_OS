"""Frontend regression tests for Sprint C1 (Consolidation) and Sprint C1B
(Rewiring): Cockpit and the Discovered Project Detail view both consume the
shared ProjectContext, rather than each independently recomputing it. Same
string-assertion style as the other *_ui.py files -- no JS runtime/browser
test harness exists in this repo (a live browser smoke test was run
manually for this sprint; see the completion report).
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_dproject_activity_uses_server_side_project_filter_not_client_filter():
    """Regression: the Discovered Project Detail page used to fetch the
    *entire* activity feed (every adopted project) and filter it
    client-side with `feed.filter((e) => e.project_id === itemId)` -- an
    O(all-projects) cost for a single-project page. It must now request
    the server-side-scoped feed directly."""
    body = client.get("/static/js/app.js").text
    detail_fn = body.split("async function renderDiscoveredProjectDetail")[1].split(
        "// ---------------------------------------------------------------------\n  // Boot"
    )[0]
    assert "/workspace/activity?project_id=" in detail_fn
    assert ".filter((e) => e.project_id" not in detail_fn


def test_cockpit_consumes_embedded_project_context_for_health_and_resume_state():
    """Sprint C1B (Rewiring): Cockpit no longer makes a separate,
    best-effort `/project-context/{id}` fetch (Sprint C1's design, kept
    Cockpit correct even if that call failed, but also meant deleting the
    module wouldn't break Cockpit at all). It now reads `project_context`
    already embedded on each `/pi/projects` entry (see `routers/pi/
    projects.py`) as its primary source for health/status/resume_state --
    a real dependency, not an optional side call.

    Sprint C7.1 (Resume Work Refactor): `next_action` display moved out of
    this embedded `project_context` read and into the server-built Project
    Memory card (`renderProjectMemoryCardHtml`, fetched from `GET /pi/
    projects/{id}/memory`) -- see `test_project_memory.py`'s Cockpit
    coverage in `test_cockpit_redesign_ui.py` for that assertion instead."""
    body = client.get("/static/js/app.js").text
    cockpit_fn = body.split("async function renderCockpitPage")[1].split(
        "async function renderDiscoveredProjectDetail"
    )[0]
    assert "project.project_context" in cockpit_fn
    assert "context.resume_state" in cockpit_fn
    # The old, separate additive fetch must be gone -- a real fetch call,
    # not just the string in a comment explaining why it was removed.
    assert "fetchJSON(`/project-context/" not in cockpit_fn


def test_project_context_router_registered():
    resp = client.get("/project-context")
    assert resp.status_code == 200
