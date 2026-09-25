"""Phase 3 Task 3 (Daily Command Center) tests.

Backend: `GET /mission-control` gains an additive `work` block (active /
completed / tools, domain + client, provenance-labelled next action, human
"why"). Tools and completed work never compete in the primary ranking.

Frontend: same string-assertion style as the other `*_ui.py` files -- there
is no JS runtime in this repo's test harness; the rendered page itself was
validated live in a browser (see docs/PHASE_3_TASK_3_DAILY_COMMAND_CENTER_UI.md).
"""

from __future__ import annotations

from pathlib import Path

from app.main import app
from app.workspace import classification
from fastapi.testclient import TestClient

client = TestClient(app)
_APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "app.js"


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _scan(tmp_path: Path, suffix: str, names: list[str], extra: dict[str, dict[str, str]] | None = None):
    root = tmp_path / f"dcc-scan-root-{suffix}"
    for name in names:
        _write(root / name / "README.md", "# A\n")
        _write(root / name / "pyproject.toml", "[project]\nname='a'")
        _write(root / name / "logo.png", "fake-png-bytes")
        for rel, content in ((extra or {}).get(name) or {}).items():
            _write(root / name / rel, content)
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    return {n: next(i for i in items if i["name"] == n) for n in names}


def _adopt(item: dict, **payload) -> dict:
    resp = client.post(f"/workspace/discovered/{item['id']}/adopt", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _patch(item: dict, **payload):
    resp = client.patch(f"/workspace/discovered/{item['id']}", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _work() -> dict:
    return client.get("/mission-control").json()["work"]


def _names(entries: list[dict]) -> set[str]:
    return {e["display_name"] for e in entries}


def _ranked_names(body: dict) -> set[str]:
    return {rp["project"]["display_name"] for rp in body["ranked_projects"]}


# ---------------------------------------------------------------------------
# Backend: grouping
# ---------------------------------------------------------------------------


def test_work_block_shape_and_domain_list():
    body = client.get("/mission-control").json()
    work = body["work"]
    assert set(work) >= {"domains", "active_projects", "completed_projects", "tools", "role_dashboard"}
    assert work["domains"] == list(classification.DOMAINS)
    # Backward compatible: every pre-existing key is still there.
    assert {"primary_focus", "todays_focus", "executive_decision", "ranked_projects", "portfolio"} <= set(body)


def test_active_completed_and_tool_grouping_with_domain_and_client(tmp_path):
    items = _scan(tmp_path, "group", ["dcc-act", "dcc-done", "dcc-tool", "dcc-client", "dcc-unclass"])
    _adopt(items["dcc-act"], domain="ROLE PERSONAL")
    _adopt(items["dcc-done"], domain="KONTOOR")
    _adopt(items["dcc-tool"], domain="ROLE PERSONAL", kind="tool")
    _adopt(items["dcc-client"], domain="CLIENTES", client_name="Ferretería VOLT")
    _adopt(items["dcc-unclass"])
    _patch(items["dcc-done"], status="completed")

    work = _work()
    active = {e["display_name"]: e for e in work["active_projects"]}
    assert {"dcc-act", "dcc-client", "dcc-unclass"} <= set(active)
    assert "dcc-done" not in active and "dcc-tool" not in active

    assert "dcc-done" in _names(work["completed_projects"])
    assert "dcc-tool" in _names(work["tools"])
    assert "dcc-tool" not in _names(work["completed_projects"])

    assert active["dcc-act"]["domain"] == "ROLE PERSONAL"
    assert active["dcc-client"]["domain"] == "CLIENTES"
    assert active["dcc-client"]["client_name"] == "Ferretería VOLT"
    # Unclassified stays representable (never guessed).
    assert active["dcc-unclass"]["domain"] is None
    assert active["dcc-unclass"]["kind"] == "project"
    tool = next(e for e in work["tools"] if e["display_name"] == "dcc-tool")
    assert tool["kind"] == "tool"


def test_completed_tool_is_listed_as_completed_not_as_active_tool(tmp_path):
    items = _scan(tmp_path, "ctool", ["dcc-old-tool"])
    _adopt(items["dcc-old-tool"], kind="tool")
    _patch(items["dcc-old-tool"], status="completed")
    work = _work()
    assert "dcc-old-tool" in _names(work["completed_projects"])
    assert "dcc-old-tool" not in _names(work["tools"])
    assert "dcc-old-tool" not in _names(work["active_projects"])


def test_paused_blocked_archived_stay_active_with_their_own_badges(tmp_path):
    items = _scan(tmp_path, "sem", ["dcc-paused", "dcc-blocked", "dcc-archived"])
    _adopt(items["dcc-paused"], status="paused")
    _adopt(items["dcc-blocked"], status="blocked")
    _adopt(items["dcc-archived"], status="archived")
    work = _work()
    active = {e["display_name"]: e for e in work["active_projects"]}
    assert "PAUSED" in active["dcc-paused"]["badges"]
    assert "BLOCKED" in active["dcc-blocked"]["badges"]
    assert "ARCHIVED" in active["dcc-archived"]["badges"]
    # archived is NOT completed
    assert "dcc-archived" not in _names(work["completed_projects"])
    assert "COMPLETED" not in active["dcc-archived"]["badges"]


def test_no_urgent_quick_win_or_waiting_is_fabricated(tmp_path):
    items = _scan(tmp_path, "nofake", ["dcc-nofake"])
    _adopt(items["dcc-nofake"], business_value="critical")
    for entry in _work()["active_projects"]:
        assert not ({"URGENT", "QUICK WIN", "WAITING"} & set(entry["badges"]))
    # A real, evidence-backed badge is still allowed.
    entry = next(e for e in _work()["active_projects"] if e["display_name"] == "dcc-nofake")
    assert "IMPORTANT" in entry["badges"]


# ---------------------------------------------------------------------------
# Backend: ranking exclusions
# ---------------------------------------------------------------------------


def test_tools_and_completed_never_compete_in_primary_ranking(tmp_path):
    items = _scan(tmp_path, "rank", ["dcc-r-live", "dcc-r-tool", "dcc-r-done"])
    _adopt(items["dcc-r-live"], business_value="low")
    _adopt(items["dcc-r-tool"], business_value="critical", kind="tool")
    _adopt(items["dcc-r-done"], business_value="critical")
    _patch(items["dcc-r-done"], status="completed")

    body = client.get("/mission-control").json()
    assert "dcc-r-live" in _ranked_names(body)
    for excluded in ("dcc-r-tool", "dcc-r-done"):
        assert excluded not in _ranked_names(body)
        recommended = (body["executive_decision"].get("recommended_project") or {}).get("display_name")
        assert recommended != excluded
        focus_name = ((body["primary_focus"] or {}).get("project_context") or {}).get("display_name")
        assert focus_name != excluded
        assert all((i.get("project") or {}).get("display_name") != excluded for i in body["todays_focus"])
        assert all((i.get("project") or {}).get("display_name") != excluded for i in body["needs_attention"])
    # ...but tool and completed item stay queryable in their own groups.
    assert "dcc-r-tool" in _names(body["work"]["tools"])
    assert "dcc-r-done" in _names(body["work"]["completed_projects"])


def test_active_projects_are_listed_in_ranking_order(tmp_path):
    items = _scan(tmp_path, "order", ["dcc-o-a", "dcc-o-b"])
    _adopt(items["dcc-o-a"], business_value="critical")
    _adopt(items["dcc-o-b"], business_value="low")
    body = client.get("/mission-control").json()
    ranked = [rp["project"]["display_name"] for rp in body["ranked_projects"]]
    listed = [e["display_name"] for e in body["work"]["active_projects"] if e["display_name"] in ranked]
    assert listed == ranked  # the UI never re-ranks: it renders this order
    assert body["work"]["active_projects"][0]["rank"] == 1
    assert body["work"]["active_projects"][0]["display_name"] == (
        body["executive_decision"]["recommended_project"]["display_name"]
    )


# ---------------------------------------------------------------------------
# Backend: pending work / next actions / why / provenance
# ---------------------------------------------------------------------------


def test_next_action_shows_source_and_is_not_labelled_inferred_when_recorded(tmp_path):
    items = _scan(
        tmp_path,
        "na",
        ["dcc-na-file", "dcc-na-none"],
        extra={"dcc-na-file": {"NEXT_ACTION.md": "Ship the export feature\n"}},
    )
    _adopt(items["dcc-na-file"])
    _adopt(items["dcc-na-none"])
    active = {e["display_name"]: e for e in _work()["active_projects"]}
    recorded = active["dcc-na-file"]["next_action"]
    assert recorded["text"].startswith("Ship the export feature")
    assert recorded["source"] == "NEXT_ACTION.md"
    assert recorded["inferred"] is False
    assert active["dcc-na-file"]["why"]  # human reasons exist
    assert any("next action" in w.lower() for w in active["dcc-na-file"]["why"])
    # No fake next action when nothing exists.
    none_entry = active["dcc-na-none"]
    assert none_entry["next_action"] is None or none_entry["next_action"]["inferred"] is True


def test_why_uses_plain_language_without_score_fragments(tmp_path):
    items = _scan(tmp_path, "why", ["dcc-why"], extra={"dcc-why": {"NEXT_ACTION.md": "Do X\n"}})
    _adopt(items["dcc-why"])
    entry = next(e for e in _work()["active_projects"] if e["display_name"] == "dcc-why")
    joined = " ".join(entry["why"])
    assert "priority " not in joined.lower() or "/100" not in joined
    assert "pts" not in joined and "/100" not in joined and "score" not in joined.lower()


# ---------------------------------------------------------------------------
# Approved classification persists via the established API
# ---------------------------------------------------------------------------

_APPROVED = ["ROLE_OS", "ROLE Commerce Factory", "ROLE MASTER", "role-ecosystem", "ROLE_KNOWLEDGE_OS"]


def test_approved_classification_persists_without_touching_anything_else(tmp_path):
    items = _scan(tmp_path, "approved", _APPROVED)
    before = {}
    for name in _APPROVED:
        _adopt(items[name])
        client.post(f"/workspace/discovered/{items[name]['id']}/notes", json={"text": f"note for {name}"})
        before[name] = client.get(f"/workspace/discovered/{items[name]['id']}").json()

    for name in _APPROVED:
        after = _patch(items[name], domain="ROLE PERSONAL", kind="project")
        assert after["domain"] == "ROLE PERSONAL"
        assert after["kind"] == "project"
        assert after["client_name"] is None
        for key in ("id", "status", "priority", "business_value", "tags", "notes", "adopted", "adopted_at"):
            assert after[key] == before[name][key], f"{name}: {key} changed"

    work = _work()
    active = {e["display_name"]: e for e in work["active_projects"]}
    assert all(active[n]["domain"] == "ROLE PERSONAL" for n in _APPROVED)
    assert len([n for n in _APPROVED if n in active]) == 5


def test_other_domains_are_empty_when_only_role_personal_work_exists(tmp_path):
    items = _scan(tmp_path, "empty", ["dcc-e-a"])
    _adopt(items["dcc-e-a"], domain="ROLE PERSONAL")
    work = _work()
    for domain in ("KONTOOR", "UNGER", "CLIENTES"):
        assert not [
            e for e in work["active_projects"] + work["completed_projects"] + work["tools"]
            if e["domain"] == domain and e["display_name"] == "dcc-e-a"
        ]


# ---------------------------------------------------------------------------
# Role Dashboard integration
# ---------------------------------------------------------------------------


def test_role_dashboard_link_points_to_dashboard_v2_and_it_still_loads():
    work = _work()
    assert work["role_dashboard"]["route"] == "#/dashboard"
    assert work["role_dashboard"]["summary_endpoint"] == "/dashboard/summary"
    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200
    assert resp.json()  # Dashboard v2's backend still answers

    js = _APP_JS.read_text(encoding="utf-8")
    assert "dashboard: renderDashboardPage" in js  # the route the button navigates to
    assert "function dccRoleDashboardHtml(work)" in js
    assert "Open Role Dashboard" in js
    assert 'fetchJSON("/dashboard/summary")' in js  # Dashboard v2 still fetches its own summary


# ---------------------------------------------------------------------------
# Resume Work regression
# ---------------------------------------------------------------------------


def test_top_recommendation_can_be_resumed(tmp_path):
    items = _scan(tmp_path, "resume", ["dcc-resume"])
    _adopt(items["dcc-resume"], domain="ROLE PERSONAL")
    top = _work()["active_projects"][0]
    assert top["item_id"]
    assert isinstance(top["resume_available"], bool)
    resp = client.post(f"/workspace/discovered/{top['item_id']}/resume-work")
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Frontend (string assertions)
# ---------------------------------------------------------------------------


def _skeleton(js: str) -> str:
    fn_start = js.index("async function renderMissionControlPage()")
    start = js.index("viewRoot.innerHTML = `", fn_start)
    return js[start : js.index("data = await fetchJSON", start)]


def _dcc_source(js: str) -> str:
    start = js.index("// DAILY COMMAND CENTER (Role OS 2.0 Phase 3 Task 3)")
    return js[start : js.index("async function wireMissionControlActions(data)")]


def test_landing_route_is_still_mission_control():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "home: renderMissionControlPage" in js
    assert 'return { view: view || "home", param };' in js
    assert "Daily Command Center" in _skeleton(js)


def test_sections_appear_in_the_target_information_architecture_order():
    sk = _skeleton(_APP_JS.read_text(encoding="utf-8"))
    order = [
        'id="dcc-domain-filter"',
        "What should I do now?",
        # Phase 3 Task 6B: continuity moved up, right after the recommendation.
        "Where I Left Off",
        "Pending Work / Next Actions",
        "Active Projects",
        "Completed",
        "Tools",
        "Role Dashboard",
    ]
    positions = [sk.index(marker) for marker in order]
    assert positions == sorted(positions)


def test_domain_filters_are_rendered_from_the_backend_domain_list():
    js = _APP_JS.read_text(encoding="utf-8")
    src = _dcc_source(js)
    assert "work.domains" in src  # the four domains come from the payload, not a hardcoded copy
    assert 'let dccDomainFilter = "ALL"' in src
    assert "data-dcc-domain" in src
    assert "dccMatchesFilter" in src
    # Unclassified stays representable, as a secondary (non-primary) chip.
    assert "DCC_UNCLASSIFIED" in src and "dcc-chip-secondary" in src
    # Filtering never touches global navigation.
    assert "#sidebar" not in src


def test_all_sections_have_honest_empty_states():
    src = _dcc_source(_APP_JS.read_text(encoding="utf-8"))
    for text in (
        "No completed projects yet.",
        "No tools registered yet.",
        "No projects in this domain.",
        "No next action recorded.",  # Phase 3 Task 6B wording
        "No resumable session available.",
        "No active projects yet.",
    ):
        assert text in src


def test_continue_working_is_primary_and_reuses_resume_work():
    src = _dcc_source(_APP_JS.read_text(encoding="utf-8"))
    assert "Continue Working" in src
    assert 'class="btn btn-primary btn-lg" data-resume-work-item=' in src
    assert 'top.resume_available ? "" : "disabled"' in src
    assert "triggerResumeWork(btn.dataset.resumeWorkItem)" in src  # one resume mechanism
    assert 'class="btn btn-lg u-mt-3" data-nav=' in src  # Open Role Dashboard: visible but secondary


def test_ui_does_not_fabricate_urgency_quick_wins_or_tasks_or_scores():
    src = _dcc_source(_APP_JS.read_text(encoding="utf-8"))
    for forbidden in ("URGENT", "QUICK WIN", "Quick Win", "WAITING", "decision_score", "pts", "Tasks"):
        assert forbidden not in src
    assert "Pending Work / Next Actions" in _skeleton(_APP_JS.read_text(encoding="utf-8"))


def test_inferred_next_actions_are_labelled_as_such():
    src = _dcc_source(_APP_JS.read_text(encoding="utf-8"))
    assert 'badgeHtml("inferred", "warning")' in src
    assert "na.inferred" in src


def test_stale_and_fallback_visibility_is_preserved():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "renderDashFreshnessBanner(data.data_freshness)" in js  # page-level stale banner
    assert "function dccStalenessNoteHtml(freshness)" in js  # on the recommendation itself
    assert "mcStalenessNoteHtml(freshness)" in js  # existing Executive Decision note kept
    assert "mcEcosystemDecisionsHtml(" in js and "Fallback snapshot" in js


def test_existing_mission_control_sections_are_still_rendered():
    js = _APP_JS.read_text(encoding="utf-8")
    sk = _skeleton(js)
    for marker in (
        "mc-primary-focus",
        "mc-executive-decision",
        "mc-todays-focus",
        "mc-portfolio-ranking",
        "mc-since-last-time",
        "mc-needs-attention",
        "mc-recent-activity",
        "mc-daily-session",
        "mc-value-signal",
        "mc-quick-actions",
        "mc-portfolio",
    ):
        assert marker in sk
    assert "Resume Work &rarr;" in js
    assert "dccRenderSections(data, { bindResume: false })" in js
