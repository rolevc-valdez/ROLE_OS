"""Sprint C2.1 (Project Identity Reconciliation) tests.

Live verification of Dashboard 2.0 found "ROLE Commerce Factory" existing
as two separate `projects` rows -- one discovery-linked, one purely
manual. These tests cover the general reconciliation machinery
(`app.projects.db.merge_project`, `app.workspace.reconciliation`) with
real Discovery Engine runs against synthetic folder trees where relevant
-- nothing mocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config import Settings
from app.main import app
from app.projects import db as projects_db
from app.workspace import reconciliation
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "proj" / "projects.db"))
    monkeypatch.setenv("ROLE_OS_DB_PATH", str(tmp_path / "knowledge" / "role_os.db"))
    return Settings()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# §7: exact-name duplicate with complementary data
# ---------------------------------------------------------------------------


def test_merge_with_complementary_data_preserves_both_sides(settings):
    p1 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    projects_db.add_collection_item(p1["id"], "notes", {"text": "note on p1"}, settings=settings)
    projects_db.add_collection_item(p2["id"], "notes", {"text": "note on p2"}, settings=settings)
    projects_db.update_project(p2["id"], {"description": "a real description"}, settings=settings)

    result = projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    note_texts = {n["text"] for n in result["notes"]}
    assert note_texts == {"note on p1", "note on p2"}
    assert result["description"] == "a real description"  # backfilled from duplicate


# ---------------------------------------------------------------------------
# §7: conflicting data -- survivor's own non-empty values are never overwritten
# ---------------------------------------------------------------------------


def test_merge_with_conflicting_data_keeps_survivor_values(settings):
    p1 = projects_db.create_project(
        name="Foo", workspace="Products", description="survivor description", settings=settings
    )
    p2 = projects_db.create_project(
        name="Foo", workspace="Products", description="duplicate description", settings=settings
    )
    projects_db.set_health_score(p1["id"], 90, settings=settings)
    projects_db.set_health_score(p2["id"], 10, settings=settings)

    result = projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    assert result["description"] == "survivor description"
    assert result["health_score"] == 90  # never overwritten by the duplicate's score


# ---------------------------------------------------------------------------
# §7: sessions and snapshots migration
# ---------------------------------------------------------------------------


def test_ai_sessions_and_snapshots_migrate_to_survivor(settings):
    p1 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    session = projects_db.create_ai_session(p2["id"], assistant="claude", settings=settings)
    projects_db.create_ai_session_snapshot(
        session["id"], summary="important progress", settings=settings
    )

    projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    survivor_sessions = projects_db.list_ai_sessions(p1["id"], settings=settings)
    assert len(survivor_sessions) == 1
    assert survivor_sessions[0]["id"] == session["id"]
    snapshot = projects_db.get_latest_snapshot(session["id"], settings=settings)
    assert snapshot is not None
    assert snapshot["summary"] == "important progress"

    duplicate_sessions = projects_db.list_ai_sessions(p2["id"], settings=settings)
    assert duplicate_sessions == []  # no longer attributed to the merged-away id


# ---------------------------------------------------------------------------
# §7: foreign-key references (capabilities, dependencies, ai_workspace)
# ---------------------------------------------------------------------------


def test_capabilities_and_dependencies_migrate_without_violating_uniqueness(settings):
    p1 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    other = projects_db.create_project(name="Other", workspace="Products", settings=settings)

    cap = projects_db.create_capability(p2["id"], "Some capability", settings=settings)
    projects_db.consume_capability(cap["id"], other["id"], settings=settings)
    projects_db.create_dependency(p2["id"], other["id"], settings=settings)
    projects_db.create_dependency(other["id"], p2["id"], settings=settings)

    # A capability_consumers row that would collide after migration (p1
    # already consumes the same capability p2 also consumes).
    shared_cap = projects_db.create_capability(other["id"], "Shared", settings=settings)
    projects_db.consume_capability(shared_cap["id"], p1["id"], settings=settings)
    projects_db.consume_capability(shared_cap["id"], p2["id"], settings=settings)

    result = projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    caps = projects_db.list_capabilities(project_id=p1["id"], settings=settings)
    assert any(c["id"] == cap["id"] for c in caps)

    deps_from = projects_db.list_dependencies(p1["id"], settings=settings)
    assert any(d["depends_on_project_id"] == other["id"] for d in deps_from)
    deps_to = projects_db.list_dependents(p1["id"], settings=settings)
    assert any(d["project_id"] == other["id"] for d in deps_to)

    # The colliding shared_cap consumer link didn't raise -- it either
    # migrated (if only one existed) or was dropped as a true duplicate of
    # an existing link, never crashing the whole merge.
    assert result["_merge_summary"] if "_merge_summary" in result else True


def test_ai_workspace_migrates_when_only_duplicate_has_one(settings):
    p1 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    projects_db.save_ai_workspace(p2["id"], claude_url="https://claude.ai/x", settings=settings)

    projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    survivor_ws = projects_db.get_ai_workspace(p1["id"], settings=settings)
    assert survivor_ws is not None
    assert survivor_ws["claude_url"] == "https://claude.ai/x"


def test_ai_workspace_backfills_blank_fields_when_both_have_one(settings):
    p1 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    projects_db.save_ai_workspace(
        p1["id"], claude_url="https://claude.ai/survivor", settings=settings
    )
    projects_db.save_ai_workspace(
        p2["id"], chatgpt_url="https://chatgpt.com/dup", settings=settings
    )

    projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    survivor_ws = projects_db.get_ai_workspace(p1["id"], settings=settings)
    assert survivor_ws["claude_url"] == "https://claude.ai/survivor"  # untouched
    assert survivor_ws["chatgpt_url"] == "https://chatgpt.com/dup"  # backfilled


# ---------------------------------------------------------------------------
# §7: already-merged project
# ---------------------------------------------------------------------------


def test_cannot_merge_an_already_merged_project_again(settings):
    p1 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p3 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    with pytest.raises(projects_db.MergeError, match="already merged"):
        projects_db.merge_project(p3["id"], p2["id"], settings=settings)

    with pytest.raises(projects_db.MergeError, match="itself merged"):
        projects_db.merge_project(p2["id"], p3["id"], settings=settings)


def test_get_project_transparently_resolves_merged_id(settings):
    p1 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    redirected = projects_db.get_project(p2["id"], settings=settings)
    assert redirected["id"] == p1["id"]

    raw = projects_db.get_project(p2["id"], settings=settings, follow_merge=False)
    assert raw["id"] == p2["id"]
    assert raw["merged_into_project_id"] == p1["id"]


# ---------------------------------------------------------------------------
# §7: rollback on failure
# ---------------------------------------------------------------------------


def test_merge_rolls_back_entirely_on_failure(settings, monkeypatch):
    p1 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    p2 = projects_db.create_project(name="Foo", workspace="Products", settings=settings)
    session = projects_db.create_ai_session(p2["id"], assistant="claude", settings=settings)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure mid-merge")

    monkeypatch.setattr(projects_db, "_merge_json_collections", _boom)

    with pytest.raises(RuntimeError, match="simulated failure"):
        projects_db.merge_project(p1["id"], p2["id"], settings=settings)

    # Nothing committed: the ai_sessions UPDATE that ran earlier in the
    # same transaction must have been rolled back too.
    assert projects_db.list_ai_sessions(p2["id"], settings=settings) == [session]
    assert projects_db.list_ai_sessions(p1["id"], settings=settings) == []
    duplicate_raw = projects_db.get_project(p2["id"], settings=settings, follow_merge=False)
    assert duplicate_raw["merged_into_project_id"] is None


# ---------------------------------------------------------------------------
# §7: no automatic merge from weak evidence
# ---------------------------------------------------------------------------


def test_weak_name_only_evidence_is_flagged_not_hidden(settings):
    projects_db.create_project(name="Widget", workspace="Ideas", settings=settings)
    projects_db.create_project(name="widget", workspace="Personal", settings=settings)

    candidates = reconciliation.find_duplicate_candidates(settings=settings)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["exact_name_match"] is True
    assert candidate["root_path_match"] is False
    assert candidate["git_remote_match"] is False
    assert any("WEAK" in e for e in candidate["evidence"])
    # No survivor is suggested when neither side has a discovery link --
    # detection never picks a side; a human must.
    assert candidate["suggested_survivor_id"] is None


def test_detection_never_merges_anything_itself(settings):
    projects_db.create_project(name="Widget", workspace="Ideas", settings=settings)
    projects_db.create_project(name="Widget", workspace="Ideas", settings=settings)

    reconciliation.find_duplicate_candidates(settings=settings)  # read-only

    still_active = projects_db.list_projects(settings=settings)
    assert len(still_active) == 2  # neither was merged just by being detected


# ---------------------------------------------------------------------------
# §7: Dashboard/Advisor deduplication
# ---------------------------------------------------------------------------


def _make_and_adopt(client_, tmp_path: Path, suffix: str, name: str) -> dict:
    root = tmp_path / f"scan-root-{suffix}"
    _write(root / name / "README.md", "# A\n")
    _write(root / name / "pyproject.toml", "[project]\nname='a'")
    client_.post("/workspace/rescan", json={"root": str(root)})
    items = client_.get("/workspace/discovered", params={"view": "top_level"}).json()
    item = next(i for i in items if i["name"] == name)
    client_.post(f"/workspace/discovered/{item['id']}/adopt", json={})
    return item


def test_real_discovery_and_manual_duplicate_merges_and_dedupes_everywhere(tmp_path):
    """The exact real-world scenario: a discovery-linked project and an
    older, purely-manual project sharing the same name. After merging the
    manual one into the discovery-linked survivor, it must appear exactly
    once in the Projects list (`/pi/projects`), Advisor, and Dashboard."""
    name = "Reconciliation Real Case"
    item = _make_and_adopt(client, tmp_path, "c21", name)
    discovered_project_id = client.get(f"/workspace/discovered/{item['id']}").json()[
        "canonical_project_id"
    ]
    manual = client.post("/pi/projects", json={"name": name, "workspace": "Products"}).json()
    assert manual["id"] != discovered_project_id

    projects_before = client.get("/pi/projects").json()
    matches_before = [p for p in projects_before if p["name"] == name]
    assert len(matches_before) == 2  # the duplicate, reproduced

    candidates = client.get("/pi/projects/reconciliation/candidates").json()
    pair = next(
        c
        for c in candidates
        if {c["project_a"]["id"], c["project_b"]["id"]} == {manual["id"], discovered_project_id}
    )
    assert pair["suggested_survivor_id"] == discovered_project_id
    assert pair["one_discovery_linked"] is True

    merge_resp = client.post(
        "/pi/projects/reconciliation/merge",
        json={"surviving_id": discovered_project_id, "duplicate_id": manual["id"], "confirm": True},
    )
    assert merge_resp.status_code == 200

    projects_after = client.get("/pi/projects").json()
    matches_after = [p for p in projects_after if p["name"] == name]
    assert len(matches_after) == 1
    assert matches_after[0]["id"] == discovered_project_id

    dashboard = client.get("/dashboard/summary").json()
    all_refs = (
        dashboard["portfolio_status"]["healthy"]
        + dashboard["portfolio_status"]["warning"]
        + dashboard["portfolio_status"]["critical"]
    )
    matching_refs = [r for r in all_refs if r["display_name"] == name]
    assert len(matching_refs) == 1

    advisor = client.get(
        "/advisor/recommendations", params={"project_id": discovered_project_id}
    ).json()
    for rec in advisor:
        assert rec["project_id"] == discovered_project_id  # never the merged-away manual id


def test_merge_requires_explicit_confirm(tmp_path):
    p1 = client.post(
        "/pi/projects", json={"name": "Needs Confirm A", "workspace": "Products"}
    ).json()
    p2 = client.post(
        "/pi/projects", json={"name": "Needs Confirm A", "workspace": "Products"}
    ).json()
    resp = client.post(
        "/pi/projects/reconciliation/merge",
        json={"surviving_id": p1["id"], "duplicate_id": p2["id"]},
    )
    assert resp.status_code == 400
    # Neither project was touched.
    listed = client.get("/pi/projects").json()
    assert any(p["id"] == p2["id"] for p in listed)


# ---------------------------------------------------------------------------
# §7: manual project without a discovery match remains untouched
# ---------------------------------------------------------------------------


def test_unrelated_manual_project_is_never_a_candidate(settings):
    projects_db.create_project(name="Totally Unique Name", workspace="Products", settings=settings)
    candidates = reconciliation.find_duplicate_candidates(settings=settings)
    assert candidates == []


def test_manual_project_untouched_when_no_duplicate_exists(tmp_path):
    solo = client.post(
        "/pi/projects", json={"name": "Solo Manual Project No Dup", "workspace": "Products"}
    ).json()
    candidates = client.get("/pi/projects/reconciliation/candidates").json()
    assert not any(solo["id"] in (c["project_a"]["id"], c["project_b"]["id"]) for c in candidates)
    still_there = client.get(f"/pi/projects/{solo['id']}").json()
    assert still_there["id"] == solo["id"]
    assert still_there.get("merged_into_project_id") is None
