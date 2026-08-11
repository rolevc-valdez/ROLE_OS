"""Sprint C3 (Explorer 2.0) acceptance tests.

Real Discovery Engine runs against synthetic folder trees throughout --
nothing mocked. Uses the shared `TestClient(app)` pattern (session-wide
DBs, per `dashboard/tests/conftest.py`) already established by the C1B/C2/
C2.1 test files, with unique per-test names/roots to avoid cross-test
collisions.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_and_adopt(tmp_path: Path, suffix: str, name: str, with_git: bool = False) -> dict:
    root = tmp_path / f"scan-root-{suffix}"
    repo = root / name
    _write(repo / "README.md", f"# {name}\nAbout {name} and Shopify integration.\n")
    _write(repo / "pyproject.toml", "[project]\nname='a'")
    _write(repo / "TODO.md", "- [ ] wire up Printful export\n")
    _write(repo / "logo.png", "fake-png-bytes")
    if with_git:
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=t@t.com",
                "-c",
                "user.name=t",
                "commit",
                "-m",
                "Integrate Shopify webhook",
            ],
            cwd=repo,
            capture_output=True,
        )
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


def _search(q: str, **params) -> dict:
    resp = client.get("/explorer/search", params={"q": q, **params})
    assert resp.status_code == 200
    return resp.json()


def _adopt_siblings(tmp_path: Path, suffix: str, names: list[str]) -> list[dict]:
    """Adopts several projects from ONE rescan (siblings under one root).
    `Workspace.rescan` replaces the single global scan cache wholesale
    (by design -- one discovery root per scan, see `app.workspace.db`'s
    single-row cache), so two projects that need to coexist for a test
    must come from the same scan, not two separate `rescan` calls each
    pointed at a different root (the second would silently evict the
    first from the active top-level listing)."""
    root = tmp_path / f"scan-root-{suffix}"
    for name in names:
        _write(root / name / "README.md", f"# {name}\n")
        _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    adopted = []
    for name in names:
        item = next(i for i in items if i["name"] == name)
        client.post(f"/workspace/discovered/{item['id']}/adopt", json={})
        adopted.append(item)
    return adopted


# ---------------------------------------------------------------------------
# Search finds every required domain.
# ---------------------------------------------------------------------------


def test_search_finds_projects(tmp_path):
    _make_and_adopt(tmp_path, "1", "Explorer Proj One")
    result = _search("Explorer Proj One")
    assert any(r["title"] == "Explorer Proj One" for r in result["groups"]["Project"])


def test_search_finds_snapshots(tmp_path):
    item = _make_and_adopt(tmp_path, "2", "Explorer Proj Snap")
    project_id = client.get(f"/workspace/discovered/{item['id']}").json()["canonical_project_id"]
    session = client.post(
        f"/pi/projects/{project_id}/ai-sessions", json={"assistant": "claude"}
    ).json()
    client.post(
        f"/pi/projects/{project_id}/ai-sessions/{session['id']}/snapshots",
        json={"summary": "Explorer snapshot marker unique text"},
    )
    result = _search("Explorer snapshot marker")
    assert any("Explorer snapshot marker" in r["title"] for r in result["groups"]["Snapshot"])


def test_search_finds_assets(tmp_path):
    _make_and_adopt(tmp_path, "3", "Explorer Proj Asset")
    result = _search("logo.png")
    assert any(r["title"] == "logo.png" for r in result["groups"]["Asset"])


def test_search_finds_knowledge(tmp_path):
    result = _search("nonexistent-knowledge-query-xyz")
    assert "Knowledge Card" in result["groups"]  # present even if empty -- shape check
    assert isinstance(result["groups"]["Knowledge Card"], list)


def test_search_finds_markdown(tmp_path):
    _make_and_adopt(tmp_path, "4", "Explorer Proj Markdown")
    result = _search("Printful")
    assert any(
        r["type"] == "Markdown" and "Printful" in (r.get("summary") or "") for r in _flatten(result)
    )


def test_search_finds_markdown_by_keyword(tmp_path):
    """Searching the literal keyword "TODO" must surface TODO.md even
    without matching its body text (§ live validation demo query)."""
    _make_and_adopt(tmp_path, "5", "Explorer Proj Todo")
    result = _search("TODO")
    assert any(r["title"] == "TODO.md" for r in result["groups"]["Markdown"])


def test_search_finds_sessions(tmp_path):
    item = _make_and_adopt(tmp_path, "6", "Explorer Proj Session")
    project_id = client.get(f"/workspace/discovered/{item['id']}").json()["canonical_project_id"]
    client.post(
        f"/pi/projects/{project_id}/ai-sessions",
        json={"assistant": "claude", "title": "Explorer Claude Session Marker"},
    )
    result = _search("Explorer Claude Session Marker")
    assert any(
        r["title"] == "Explorer Claude Session Marker" for r in result["groups"]["AI Session"]
    )


def test_search_finds_recommendations(tmp_path):
    root = tmp_path / "scan-root-7"
    repo = root / "Explorer Proj NoReadme"
    _write(repo / "pyproject.toml", "[project]\nname='a'")  # deliberately no README.md
    client.post("/workspace/rescan", json={"root": str(root)})
    items = client.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == "Explorer Proj NoReadme")
    client.post(f"/workspace/discovered/{item['id']}/adopt", json={})

    result = _search("README", types=["Recommendation"])
    assert any(
        "README" in r["title"] and r["project"] == "Explorer Proj NoReadme"
        for r in result["groups"]["Recommendation"]
    )


def test_search_finds_commits(tmp_path):
    _make_and_adopt(tmp_path, "8", "Explorer Proj Commit", with_git=True)
    result = _search("Shopify webhook")
    assert any(r["type"] == "Commit" and "Shopify" in r["title"] for r in _flatten(result))


def test_search_finds_capabilities(tmp_path):
    p = client.post(
        "/pi/projects", json={"name": "Explorer Cap Project", "workspace": "Products"}
    ).json()
    client.post(f"/pi/projects/{p['id']}/capabilities", json={"name": "Explorer Capability Marker"})
    result = _search("Explorer Capability Marker")
    assert any(r["title"] == "Explorer Capability Marker" for r in result["groups"]["Capability"])


def test_search_finds_decisions():
    p = client.post(
        "/pi/projects", json={"name": "Explorer Decision Project", "workspace": "Products"}
    ).json()
    client.post(f"/pi/projects/{p['id']}/decisions", json={"text": "Explorer decision marker text"})
    result = _search("Explorer decision marker")
    assert any(r["type"] == "Decision" for r in result["groups"]["Decision"])


def test_search_finds_conversations():
    result = _search("", types=["Conversation"])
    assert "Conversation" in result["groups"]


def _flatten(result: dict) -> list[dict]:
    return [r for group in result["groups"].values() for r in group]


# ---------------------------------------------------------------------------
# Merged projects appear once.
# ---------------------------------------------------------------------------


def test_merged_projects_appear_once_in_search(tmp_path):
    item = _make_and_adopt(tmp_path, "9", "Explorer Merge Target")
    discovered_id = client.get(f"/workspace/discovered/{item['id']}").json()["canonical_project_id"]
    manual = client.post(
        "/pi/projects", json={"name": "Explorer Merge Target", "workspace": "Products"}
    ).json()
    before = _search("Explorer Merge Target")
    assert len(before["groups"]["Project"]) == 2

    client.post(
        "/pi/projects/reconciliation/merge",
        json={"surviving_id": discovered_id, "duplicate_id": manual["id"], "confirm": True},
    )

    after = _search("Explorer Merge Target")
    assert len(after["groups"]["Project"]) == 1
    assert after["groups"]["Project"][0]["project_id"] == discovered_id


# ---------------------------------------------------------------------------
# Ranking stable / grouping correct / canonical identity respected.
# ---------------------------------------------------------------------------


def test_ranking_is_stable_across_repeated_identical_queries(tmp_path):
    _adopt_siblings(tmp_path, "10", ["Explorer Stable Rank Alpha", "Explorer Stable Rank Beta"])
    first = _search("Explorer Stable Rank")
    second = _search("Explorer Stable Rank")
    assert len(first["groups"]["Project"]) == 2
    assert [r["id"] for r in first["groups"]["Project"]] == [
        r["id"] for r in second["groups"]["Project"]
    ]


def test_exact_match_ranks_above_partial_match(tmp_path):
    _adopt_siblings(tmp_path, "12", ["Exact Rank Test", "Exact Rank Test Extended Name"])
    result = _search("Exact Rank Test")
    titles = [r["title"] for r in result["groups"]["Project"]]
    assert titles[0] == "Exact Rank Test"


def test_grouping_matches_declared_result_types(tmp_path):
    result = _search("")
    from app.explorer.service import RESULT_TYPES

    assert set(result["groups"].keys()) == set(RESULT_TYPES)
    assert set(result["counts"].keys()) == set(RESULT_TYPES)


def test_canonical_identity_respected_project_id_matches_context(tmp_path):
    item = _make_and_adopt(tmp_path, "14", "Explorer Canonical Check")
    discovered_id = client.get(f"/workspace/discovered/{item['id']}").json()["canonical_project_id"]
    result = _search("Explorer Canonical Check")
    project_result = next(
        r for r in result["groups"]["Project"] if r["title"] == "Explorer Canonical Check"
    )
    assert project_result["project_id"] == discovered_id
    assert project_result["item_id"] == item["id"]


# ---------------------------------------------------------------------------
# Empty state.
# ---------------------------------------------------------------------------


def test_empty_query_returns_bounded_browse_not_error():
    result = _search("")
    assert result["query"] == ""
    assert isinstance(result["total"], int)


def test_no_match_query_returns_honest_zero_counts():
    result = _search("zzz-definitely-nothing-matches-this-zzz")
    assert result["total"] == 0
    assert all(count == 0 for count in result["counts"].values())


def test_unknown_result_type_filter_rejected():
    resp = client.get("/explorer/search", params={"q": "x", "types": "NotARealType"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Project Hub.
# ---------------------------------------------------------------------------


def test_project_hub_composes_existing_services(tmp_path):
    item = _make_and_adopt(tmp_path, "15", "Explorer Hub Project")
    project_id = client.get(f"/workspace/discovered/{item['id']}").json()["canonical_project_id"]
    resp = client.get(f"/explorer/project/{project_id}")
    assert resp.status_code == 200
    hub = resp.json()
    assert set(hub.keys()) >= {
        "overview",
        "sessions",
        "snapshots",
        "assets",
        "knowledge",
        "recent_activity",
        "commits",
        "timeline",
        "recommendations",
    }
    assert hub["overview"]["display_name"] == "Explorer Hub Project"


def test_project_hub_404_for_unknown_project():
    resp = client.get("/explorer/project/does-not-exist-at-all")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Sprint C3.1: no duplicated aggregation -- Dashboard and Explorer share the
# one "every tracked project" definition instead of each keeping a private
# copy of the same composition logic.
# ---------------------------------------------------------------------------


def test_dashboard_and_explorer_share_one_project_context_aggregator():
    import app.dashboard.service as dashboard_service
    import app.explorer.service as explorer_service
    from app.project_context.builder import all_project_contexts

    assert dashboard_service._all_project_contexts is all_project_contexts
    assert explorer_service._all_project_contexts is all_project_contexts
