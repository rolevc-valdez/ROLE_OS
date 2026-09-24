"""Phase 3 Task 5 (Universal Project & Tool Ingestion) tests.

External managed work (Claude Web / ChatGPT / Chrome bookmark / GitHub / web
/ other) is recorded as an adopted overlay row with no local folder. Every
test uses its own workspace DB (and clears the lru-cached `get_settings`),
so nothing reaches the session-wide DB or any canonical runtime DB.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.config import Settings, get_settings
from app.main import app
from app.workspace import classification, db, external, registration, service
from fastapi.testclient import TestClient

client = TestClient(app)
_APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "app.js"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    get_settings.cache_clear()
    yield Settings()
    get_settings.cache_clear()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _add(settings, **payload) -> dict:
    payload.setdefault("name", "External thing")
    payload.setdefault("source", "web")
    return service.create_external_work(payload, settings=settings)["item"]


def _api_add(**payload) -> dict:
    payload.setdefault("source", "web")
    resp = client.post("/workspace/external-work", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["item"]


def _work() -> dict:
    return client.get("/mission-control").json()["work"]


def _names(entries) -> set[str]:
    return {e["display_name"] for e in entries}


# ---------------------------------------------------------------------------
# Source vocabulary / validation
# ---------------------------------------------------------------------------


def test_source_vocabulary_and_validation():
    assert classification.normalize_source("Claude-Web") == "claude_web"
    assert classification.normalize_source(" CHATGPT ") == "chatgpt"
    assert classification.normalize_source("chrome bookmark") == "chrome_bookmark"
    for bad in ("claude", "KONTOOR", "", None, "dropbox"):
        with pytest.raises(ValueError):
            classification.normalize_source(bad)
    with pytest.raises(ValueError):
        classification.normalize_source("local", allow_local=False)


def test_domain_list_is_unchanged_and_sources_are_not_domains():
    assert classification.DOMAINS == ("KONTOOR", "UNGER", "ROLE PERSONAL", "CLIENTES")
    for provider in ("CLAUDE", "CHATGPT", "CHROME", "claude_web"):
        with pytest.raises(ValueError):
            classification.normalize_domain(provider)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///C:/secret.txt",
        "data:text/html,hi",
        "claude.ai/project/abc",
        "https://user:pass@example.com/x",
        "https://exa mple.com",
    ],
)
def test_unsafe_or_invalid_urls_rejected(url):
    with pytest.raises(ValueError):
        external.normalize_url(url)


def test_bookmarklet_code_is_not_accepted_as_reference():
    with pytest.raises(ValueError):
        external.normalize_reference("javascript:(function(){document.title='x'})()")
    assert external.normalize_reference("  Chrome  bookmarks bar > Kontoor ") == "Chrome bookmarks bar > Kontoor"


def test_invalid_source_and_local_source_rejected_via_api(settings):
    assert client.post("/workspace/external-work", json={"name": "X", "source": "dropbox"}).status_code == 422
    assert client.post("/workspace/external-work", json={"name": "X", "source": "local"}).status_code == 422
    assert client.post("/workspace/external-work", json={"name": "", "source": "web"}).status_code == 422
    assert db.list_external_overlays(settings) == []


def test_domain_and_clientes_rules_still_apply(settings):
    with pytest.raises(ValueError):
        _add(settings, domain="CHATGPT")
    with pytest.raises(ValueError):
        _add(settings, domain="KONTOOR", client_name="Acme")
    item = _add(settings, domain="clientes", client_name="  Acme  Corp ")
    assert item["domain"] == "CLIENTES" and item["client_name"] == "Acme Corp"


def test_dry_run_review_persists_nothing(settings):
    resp = client.post(
        "/workspace/external-work?dry_run=true",
        json={"name": " Kontoor Automation ", "source": "claude_web", "kind": "project", "domain": "kontoor",
              "external_url": "https://claude.ai/project/abc"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["record"]["name"] == "Kontoor Automation"
    assert body["record"]["domain"] == "KONTOOR"
    assert db.list_external_overlays(settings) == []


# ---------------------------------------------------------------------------
# External work without a local folder
# ---------------------------------------------------------------------------


def test_claude_web_project_without_local_path(settings):
    item = _add(
        settings,
        name="Kontoor Automation Project",
        kind="project",
        domain="KONTOOR",
        source="claude_web",
        external_url="https://claude.ai/project/0199-abc",
        purpose="Automate FS ticket triage",
        next_action="Draft the triage rules",
    )
    assert item["root_path"] is None
    assert item["is_external"] is True
    assert item["source"] == "claude_web"
    assert item["external_url"] == "https://claude.ai/project/0199-abc"
    assert item["adopted"] is True and item["kind"] == "project" and item["domain"] == "KONTOOR"
    assert item["notes"][0]["text"] == "Automate FS ticket triage"
    assert item["workspace_key"].startswith("external:")
    assert item["canonical_project_id"]  # a real Role OS project, like any adoption


def test_chatgpt_reference(settings):
    item = _add(settings, name="Unger pricing", source="chatgpt", domain="UNGER",
                external_url="https://chatgpt.com/g/g-p-123/project")
    assert item["source"] == "chatgpt" and item["root_path"] is None


def test_chrome_bookmark_tool_without_url(settings):
    item = _add(settings, name="Freshservice Quick Actions", kind="tool", domain="KONTOOR",
                source="chrome_bookmark", external_reference="Chrome bookmarks bar > Kontoor > FS Quick Actions")
    assert item["kind"] == "tool"
    assert item["external_url"] is None
    assert item["external_reference"] == "Chrome bookmarks bar > Kontoor > FS Quick Actions"


def test_normal_web_and_github_references(settings):
    web = _add(settings, name="Cobalt-like tool", kind="tool", source="web", external_url="https://example.com/tool")
    gh = _add(settings, name="Remote only repo", source="github", external_url="https://github.com/someone/repo")
    assert web["source"] == "web" and gh["source"] == "github"


def test_external_url_serialization_and_enriched_detail(settings):
    item = _add(settings, name="Serialize me", source="web", external_url="https://example.com/a?b=1&c=%20")
    resp = client.get(f"/workspace/discovered/{item['id']}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["external_url"] == "https://example.com/a?b=1&c=%20"
    assert body["root_path"] is None
    assert body["project_context"]["external_url"] == "https://example.com/a?b=1&c=%20"
    assert body["project_context"]["source"] == "web"
    json.dumps(body)  # fully JSON-serializable


def test_external_ids_are_stable_and_unique(settings):
    a = _add(settings, name="Same name")
    b = _add(settings, name="Same name")
    assert a["id"] != b["id"]
    assert service.get_item(a["id"], settings)["id"] == a["id"]
    assert {i["id"] for i in service.list_workspace_items(settings=settings)} >= {a["id"], b["id"]}


def test_external_work_never_reads_the_filesystem(settings, tmp_path, monkeypatch):
    # a NEXT_ACTION.md in the server's CWD must never be mistaken for this item's
    _write(tmp_path / "cwd" / "NEXT_ACTION.md", "# Next\nDo the CWD thing\n")
    monkeypatch.chdir(tmp_path / "cwd")
    item = _add(settings, name="No folder")
    enriched = service.get_enriched_item(item["id"], settings)
    assert enriched["next_action"]["text"] is None
    assert service.list_project_assets(settings=settings, project_id=item["id"]) == {}


def test_recorded_next_action_and_patch(settings):
    item = _add(settings, name="Editable", next_action="First step")
    assert service.get_enriched_item(item["id"], settings)["next_action"]["source"] == "manual entry"
    resp = client.patch(
        f"/workspace/discovered/{item['id']}",
        json={"next_action": "Second step", "external_url": "https://example.com/new", "status": "paused"},
    )
    assert resp.status_code == 200, resp.text
    enriched = service.get_enriched_item(item["id"], settings)
    assert enriched["next_action"]["text"] == "Second step"
    assert enriched["external_url"] == "https://example.com/new"
    assert enriched["status"] == "paused"
    bad = client.patch(f"/workspace/discovered/{item['id']}", json={"external_url": "javascript:x"})
    assert bad.status_code == 422


def test_launch_claude_code_refused_for_external(settings):
    item = _add(settings, name="No launch")
    resp = client.post(f"/workspace/discovered/{item['id']}/launch-claude-code", json={"prompt": "hi"})
    assert resp.status_code == 200
    assert resp.json()["launched"] is False
    assert "no local folder" in resp.json()["message"]


# ---------------------------------------------------------------------------
# Local backward compatibility / P3.4 regression
# ---------------------------------------------------------------------------


def test_existing_local_project_backward_compatible(settings, tmp_path):
    root = tmp_path / "scan-root"
    _write(root / "local-app" / "pyproject.toml", "[project]\nname='l'")
    service.rescan(settings=settings, root=str(root))
    [local] = service.list_workspace_items(settings=settings)
    old_id = local["id"]
    adopted = service.adopt_item(old_id, domain="ROLE PERSONAL", settings=settings)
    assert adopted["id"] == old_id
    assert adopted["source"] == "local"
    assert adopted["is_external"] is False
    assert adopted["root_path"] == str(root / "local-app")
    assert db.get_overlay(old_id, settings)["source"] is None  # resolved, never back-filled


def test_explicit_registration_still_local_and_unadopted(settings, tmp_path):
    folder = tmp_path / "home-like" / "registered-proj"
    _write(folder / "pyproject.toml", "[project]\nname='r'")
    review = registration.register_path(str(folder), settings)
    item = service.get_item(review["item_id"], settings)
    assert item["adopted"] is False
    assert item["source"] == "local"
    assert item["registration_source"] == "explicit"
    before = Settings().get_discovery_roots()
    _add(settings, name="Unrelated external")
    assert Settings().get_discovery_roots() == before
    assert service.get_item(review["item_id"], settings)["adopted"] is False


def test_resume_work_still_works_for_external_project(settings):
    item = _add(settings, name="Resume external", next_action="Write the plan")
    resp = client.post(
        f"/workspace/discovered/{item['id']}/resume-work",
        json={"user_objective": {"requested_action": "Write the plan", "expected_deliverable": "plan",
                                 "completion_criteria": "done"}},
    )
    assert resp.status_code == 200, resp.text
    target = resp.json().get("execution_target") or {}
    assert (target.get("execution_target") if isinstance(target, dict) else target) != "claude_code"


# ---------------------------------------------------------------------------
# Daily Command Center
# ---------------------------------------------------------------------------


def test_external_project_active_and_tool_in_tools(settings):
    _api_add(name="ext-project-zz1", kind="project", domain="KONTOOR", source="claude_web",
             external_url="https://claude.ai/project/zz1", next_action="Ship it")
    _api_add(name="ext-tool-zz2", kind="tool", domain="KONTOOR", source="chrome_bookmark",
             external_reference="Bookmarks bar")
    work = _work()
    active = {e["display_name"]: e for e in work["active_projects"]}
    assert "ext-project-zz1" in active
    assert active["ext-project-zz1"]["source"] == "claude_web"
    assert active["ext-project-zz1"]["external_url"] == "https://claude.ai/project/zz1"
    assert active["ext-project-zz1"]["domain"] == "KONTOOR"
    assert active["ext-project-zz1"]["next_action"]["text"] == "Ship it"
    assert "ext-tool-zz2" in _names(work["tools"])
    assert "ext-tool-zz2" not in _names(work["active_projects"])


def test_external_tool_excluded_from_recommendation(settings):
    _api_add(name="only-tool-zz3", kind="tool", source="web", external_url="https://example.com")
    mc = client.get("/mission-control").json()
    ranked = [(rp.get("project") or {}).get("display_name") for rp in mc["ranked_projects"]]
    assert "only-tool-zz3" not in ranked
    assert "only-tool-zz3" not in json.dumps(mc["executive_decision"])
    assert "only-tool-zz3" not in json.dumps(mc["primary_focus"])
    assert "only-tool-zz3" in _names(mc["work"]["tools"])


def test_completed_external_project_grouping(settings):
    _api_add(name="done-ext-zz4", kind="project", source="chatgpt", status="completed")
    mc = client.get("/mission-control").json()
    assert "done-ext-zz4" in _names(mc["work"]["completed_projects"])
    assert "done-ext-zz4" not in _names(mc["work"]["active_projects"])
    ranked = [(rp.get("project") or {}).get("display_name") for rp in mc["ranked_projects"]]
    assert "done-ext-zz4" not in ranked


def test_domain_filtering_data_applies_to_external(settings):
    _api_add(name="unger-ext-zz5", kind="project", domain="UNGER", source="web")
    _api_add(name="clientes-ext-zz6", kind="project", domain="CLIENTES", client_name="Acme", source="other")
    active = {e["display_name"]: e for e in _work()["active_projects"]}
    assert active["unger-ext-zz5"]["domain"] == "UNGER"
    assert active["clientes-ext-zz6"]["domain"] == "CLIENTES"
    assert active["clientes-ext-zz6"]["client_name"] == "Acme"


def test_ignored_external_work_leaves_mission_control(settings):
    item = _api_add(name="hide-me-zz7", kind="project", source="web")
    assert client.post(f"/workspace/discovered/{item['id']}/ignore").status_code == 200
    assert "hide-me-zz7" not in json.dumps(client.get("/mission-control").json())


# ---------------------------------------------------------------------------
# UI (string-level, same convention as the other *_ui tests)
# ---------------------------------------------------------------------------


def test_add_external_work_ui_present():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "Add External Work" in js
    assert "/workspace/external-work?dry_run=true" in js
    for label in ("Name", "Kind", "Domain", "Source", "URL", "Reference", "Status", "Priority", "Next action"):
        assert label in js
    for source in classification.EXTERNAL_SOURCES:
        assert source in js
    assert "external_url" in js and 'rel="noopener noreferrer"' in js
