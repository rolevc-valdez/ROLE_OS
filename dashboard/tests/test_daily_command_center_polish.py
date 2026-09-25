"""Phase 3 Task 6B (Daily Command Center polish) tests.

Covers the P3.6 daily-use fixes: canonical-path test guard, snapshot
invalidation (no current snapshot beats a wrong one), commit history never
presented as a next action, differentiating "why", Where I Left Off placement,
Role Dashboard scroll reset / way back, and tool detail semantics. Every test
that writes uses its own workspace + projects DBs (and clears the lru-cached
`get_settings`), never the session-wide or canonical ones.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from app.config import Settings, get_settings
from app.main import app
from app.mission_control.service import _differentiate_why
from app.projects import db as projects_db
from app.workspace import service
from fastapi.testclient import TestClient

from tests import conftest

client = TestClient(app)
GIT_AVAILABLE = shutil.which("git") is not None
_APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "app.js"
_INDEX = Path(__file__).resolve().parents[1] / "app" / "templates" / "index.html"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "pi" / "projects.db"))
    get_settings.cache_clear()
    yield Settings()
    get_settings.cache_clear()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git_repo(path: Path, message: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=str(path), check=True)
    subprocess.run(["git", "add", "."], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=str(path), check=True)


def _adopt_all(settings, root: Path) -> dict[str, dict]:
    service.rescan(settings=settings, root=str(root))
    items = {i["name"]: i for i in service.list_workspace_items(settings=settings)}
    for item in items.values():
        service.adopt_item(item["id"], settings=settings)
    return items


def _work() -> dict:
    return client.get("/mission-control").json()["work"]


# ---------------------------------------------------------------------------
# Test pollution guard (root cause of the Aug 2026 fixture rows)
# ---------------------------------------------------------------------------


def test_guard_flags_runtime_paths_inside_canonical_locations(monkeypatch, tmp_path):
    assert conftest.canonical_path_violations() == []  # this very session is isolated
    workspace_dir = tmp_path / "ROLE_KNOWLEDGE_OS"
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DIR", str(workspace_dir))
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(workspace_dir / "00_SYSTEM" / "role_os_projects.db"))
    repo_var = conftest.DASHBOARD_ROOT.parent / "var" / "role_os_dashboard" / "role_os_workspace.db"
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(repo_var))
    violations = " ".join(conftest.canonical_path_violations())
    assert "ROLE_OS_PROJECTS_DB_PATH" in violations
    assert "ROLE_OS_WORKSPACE_DB_PATH" in violations


# ---------------------------------------------------------------------------
# Snapshot invalidation: no current snapshot beats a wrong one
# ---------------------------------------------------------------------------


def _project_with_snapshot(settings, summary="Wrong project's summary"):
    project = projects_db.create_project(name="snap-proj", workspace="Discovered", settings=settings)
    session = projects_db.create_ai_session(project["id"], assistant="claude", title="s", settings=settings)
    snap = projects_db.create_ai_session_snapshot(
        session["id"], summary=summary, next_prompt="do next", pending_work="pending", settings=settings
    )
    return project, session, snap


def test_invalidated_snapshot_is_not_current_but_stays_in_history(settings):
    project, session, snap = _project_with_snapshot(settings)
    assert projects_db.get_latest_snapshot(session["id"], settings)["id"] == snap["id"]

    resp = client.post(
        f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/snapshots/{snap['id']}/invalidate",
        json={"reason": "describes another project"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["invalidated_at"] and body["invalidated_reason"] == "describes another project"
    assert body["summary"] == "Wrong project's summary"  # content never rewritten

    assert projects_db.get_latest_snapshot(session["id"], settings) is None
    history = projects_db.list_ai_session_snapshots(session["id"], settings)
    assert [h["id"] for h in history] == [snap["id"]]
    timeline = projects_db.list_project_timeline(project["id"], settings)
    assert any(e["excerpt"].startswith("[invalidated: describes another project]") for e in timeline)


def test_invalidate_requires_reason_and_matching_session(settings):
    project, session, snap = _project_with_snapshot(settings)
    base = f"/pi/projects/{project['id']}/ai-sessions/{session['id']}/snapshots"
    assert client.post(f"{base}/{snap['id']}/invalidate", json={"reason": "  "}).status_code == 422
    assert client.post(f"{base}/nope/invalidate", json={"reason": "x"}).status_code == 404
    assert projects_db.get_latest_snapshot(session["id"], settings)["id"] == snap["id"]


def test_invalidated_snapshot_never_reaches_continuity(settings, tmp_path):
    root = tmp_path / "root"
    _write(root / "cont-proj" / "pyproject.toml", "[project]\nname='c'")
    items = _adopt_all(settings, root)
    item = service.get_enriched_item(items["cont-proj"]["id"], settings)
    pid = item["canonical_project_id"]
    session = projects_db.create_ai_session(pid, assistant="claude", title="s", settings=settings)
    snap = projects_db.create_ai_session_snapshot(
        session["id"], summary="MISATTRIBUTED-ZX", next_prompt="MISATTRIBUTED-NEXT", settings=settings
    )
    assert "MISATTRIBUTED-ZX" in client.get("/mission-control").text
    projects_db.invalidate_snapshot(session["id"], snap["id"], "wrong project", settings=settings)
    text = client.get("/mission-control").text
    assert "MISATTRIBUTED-ZX" not in text
    assert "MISATTRIBUTED-NEXT" not in text


# ---------------------------------------------------------------------------
# Commit history is never a next action
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git not installed")
def test_commit_message_is_last_activity_not_next_action(settings, tmp_path):
    root = tmp_path / "root"
    _write(root / "commit-only" / "pyproject.toml", "[project]\nname='a'")
    _write(root / "has-next" / "pyproject.toml", "[project]\nname='b'")
    _write(root / "has-next" / "NEXT_ACTION.md", "Write the export\n")
    _git_repo(root / "commit-only", "fix: something already done")
    _adopt_all(settings, root)
    active = {e["display_name"]: e for e in _work()["active_projects"]}

    commit_only = active["commit-only"]
    assert commit_only["next_action"] is None
    assert commit_only["last_activity_note"]["source"] == "latest git commit"
    assert commit_only["last_activity_note"]["text"].startswith("fix: something already done")
    assert not any("next action" in w.lower() for w in commit_only["why"])

    forward = active["has-next"]
    assert forward["next_action"]["text"].startswith("Write the export")
    assert forward["next_action"]["source"] == "NEXT_ACTION.md"
    assert forward["last_activity_note"] is None


def test_manual_next_action_still_shown(settings):
    client.post("/workspace/external-work", json={"name": "ext-na", "source": "web", "next_action": "Call Bob"})
    active = {e["display_name"]: e for e in _work()["active_projects"]}
    assert active["ext-na"]["next_action"]["text"] == "Call Bob"
    assert active["ext-na"]["next_action"]["source"] == "manual entry"


def test_honest_empty_next_action_state_in_ui():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "No next action recorded." in js
    assert "No next action available." not in js
    assert "Last activity: " in js
    assert "HISTORICAL_NEXT_ACTION_SOURCES.includes(rawNa.source)" in js
    assert "No current snapshot." in js


# ---------------------------------------------------------------------------
# "Why" uses differentiating evidence only
# ---------------------------------------------------------------------------


def _item(name, days, signals):
    return {"display_name": name, "days_since_activity": days, "_signals": signals, "why": []}


def test_why_drops_signals_every_project_shares():
    stale = ("stale", "No activity in 40 days")
    a = _item("a", 40, [stale, ("next_action", "Has a recorded next action (from TODO.md)")])
    b = _item("b", 40, [stale])
    _differentiate_why([a, b])
    assert a["why"] == ["Has a recorded next action (from TODO.md)"]
    assert b["why"] == []


def test_why_marks_unique_most_recent_project_only():
    a = _item("a", 3, [])
    b = _item("b", 10, [])
    _differentiate_why([a, b])
    assert a["why"] == ["Most recently active project (3 days ago)"]
    c = _item("c", 5, [])
    d = _item("d", 5, [])
    _differentiate_why([c, d])
    assert not any("Most recently" in w for w in c["why"] + d["why"])


def test_why_is_honest_when_nothing_differentiates_the_top_item():
    shared = ("suggest:Commit", "Suggested: Commit")
    a = _item("a", 7, [shared])
    b = _item("b", 7, [shared])
    _differentiate_why([a, b])
    assert a["why"] == ["No single signal clearly sets it apart — it is first in the existing Executive Decision ranking."]
    assert "_signals" not in a


def test_single_active_project_keeps_all_its_reasons():
    a = _item("a", 50, [("stale", "No activity in 50 days"), ("pending_work", "Pending work is recorded")])
    _differentiate_why([a])
    assert a["why"] == ["No activity in 50 days", "Pending work is recorded"]


# ---------------------------------------------------------------------------
# Layout, navigation, terminology
# ---------------------------------------------------------------------------


def _skeleton(js: str) -> str:
    fn_start = js.index("async function renderMissionControlPage()")
    start = js.index("viewRoot.innerHTML = `", fn_start)
    return js[start : js.index("data = await fetchJSON", start)]


def test_where_i_left_off_comes_right_after_the_recommendation():
    sk = _skeleton(_APP_JS.read_text(encoding="utf-8"))
    now = sk.index("What should I do now?")
    left_off = sk.index("Where I Left Off")
    assert now < left_off < sk.index("Pending Work / Next Actions") < sk.index("Needs Attention")
    assert sk.count('id="mc-primary-focus"') == 1  # moved, not duplicated


def test_navigation_scrolls_to_top_and_dashboard_has_way_back():
    js = _APP_JS.read_text(encoding="utf-8")
    route = js[js.index("async function route()") : js.index('window.addEventListener("hashchange", route);')]
    assert "window.scrollTo(0, 0);" in route
    assert 'data-nav="home">&larr; Daily Command Center</button>' in js
    assert 'dashboard: "home"' in js


def test_sidebar_label_is_daily_command_center_route_unchanged():
    html = _INDEX.read_text(encoding="utf-8")
    assert "<span>Daily Command Center</span>" in html
    assert "<span>Mission Control</span>" not in html
    assert 'data-nav="home"' in html


# ---------------------------------------------------------------------------
# Tool detail semantics
# ---------------------------------------------------------------------------


def test_tool_primary_action_is_open_and_resume_only_with_a_session():
    js = _APP_JS.read_text(encoding="utf-8")
    fn = js[js.index("function dprojectPrimaryActionsHtml(item)") : js.index("async function renderDiscoveredProjectDetail")]
    assert 'if (item.kind === "tool")' in fn
    assert "latest_session" in fn
    assert "resumeBtn(false)" in fn  # secondary, never primary, for a tool
    assert 'target="_blank" rel="noopener noreferrer"' in fn
    detail = js[js.index("async function renderDiscoveredProjectDetail") :]
    assert "item.is_external" in detail  # no Git/Documentation/Tests sections for folder-less work


def test_tool_reference_stays_visible_with_url():
    js = _APP_JS.read_text(encoding="utf-8")
    fn = js[js.index("function dccSourceHtml(item)") : js.index("const DCC_BADGE_VARIANTS")]
    assert "const reference = item.external_reference" in fn
    assert "!item.external_url && item.external_reference" not in fn


def test_external_tool_detail_payload_has_open_and_reference(settings):
    created = client.post(
        "/workspace/external-work",
        json={"name": "tool-zz", "kind": "tool", "source": "other", "external_url": "https://example.com/t",
              "external_reference": "Run from PowerShell"},
    ).json()["item"]
    body = client.get(f"/workspace/discovered/{created['id']}").json()
    assert body["kind"] == "tool" and body["is_external"] is True
    assert body["external_url"] == "https://example.com/t"
    assert body["external_reference"] == "Run from PowerShell"
    assert (body.get("ai_sessions") or {}).get("latest_session") is None  # so Resume Work is not offered
