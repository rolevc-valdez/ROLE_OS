"""Phase 3 Task 4 (Explicit Project Registration) tests.

Every test gets its own workspace database (`ROLE_OS_WORKSPACE_DB_PATH` under
`tmp_path`) and only registers folders it creates under `tmp_path` -- the
real user profile is never used as a path or a scan root.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from app.config import Settings, get_settings
from app.main import app
from app.workspace import db, registration, service
from fastapi.testclient import TestClient

client = TestClient(app)
GIT_AVAILABLE = shutil.which("git") is not None
_APP_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "app.js"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # `get_settings` is lru-cached, so the API tests below only see this
    # test's own workspace DB once the cache is cleared -- and it is cleared
    # again afterwards so no later test module inherits it.
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    get_settings.cache_clear()
    yield Settings()
    get_settings.cache_clear()


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_project(tmp_path: Path, name: str = "isolated-project") -> Path:
    project = tmp_path / "home-like" / name
    _write(project / "README.md", "# Isolated\n")
    _write(project / "pyproject.toml", "[project]\nname='iso'")
    _write(project / "main.py", "print(1)\n")
    return project


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@example.com:someone/isolated.git"], cwd=str(path), check=True
    )
    subprocess.run(["git", "add", "."], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=str(path), check=True)


def _tree_snapshot(root: Path) -> dict[str, tuple[int, float]]:
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime)
        for p in root.rglob("*")
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def test_valid_explicit_path_inspects_without_persisting(settings, tmp_path):
    project = _make_project(tmp_path)
    review = registration.inspect_path(str(project), settings)
    assert review["valid"] is True
    assert review["name"] == "isolated-project"
    assert review["registration_status"] == "not_registered"
    assert review["adoption_status"] == "not_adopted"
    assert "pyproject.toml" in review["manifests"]
    assert "README.md" in review["manifests"]
    assert db.list_registrations(settings) == []


def test_nonexistent_path_is_reported_honestly(settings, tmp_path):
    review = registration.inspect_path(str(tmp_path / "does-not-exist"), settings)
    assert review["valid"] is False
    assert review["error"]["code"] == "not_found"
    with pytest.raises(registration.RegistrationError) as exc:
        registration.register_path(str(tmp_path / "does-not-exist"), settings)
    assert exc.value.code == "not_found"


def test_file_instead_of_directory_is_rejected(settings, tmp_path):
    f = tmp_path / "a-file.txt"
    _write(f)
    review = registration.inspect_path(str(f), settings)
    assert review["error"]["code"] == "not_directory"


def test_empty_and_relative_paths_are_rejected(settings):
    assert registration.inspect_path("   ", settings)["error"]["code"] == "empty"
    assert registration.inspect_path("some\\relative\\folder", settings)["error"]["code"] == "not_absolute"


def test_user_profile_and_drive_root_are_too_broad(settings):
    home = Path.home()
    assert registration.inspect_path(str(home), settings)["error"]["code"] == "too_broad"
    assert registration.inspect_path(str(home.parent), settings)["error"]["code"] == "too_broad"
    assert registration.inspect_path(home.anchor, settings)["error"]["code"] == "too_broad"


def test_quoted_path_is_accepted(settings, tmp_path):
    project = _make_project(tmp_path)
    assert registration.inspect_path(f'"{project}"', settings)["valid"] is True


def test_duplicate_registration_is_rejected(settings, tmp_path):
    project = _make_project(tmp_path)
    registration.register_path(str(project), settings)
    with pytest.raises(registration.RegistrationError) as exc:
        registration.register_path(str(project), settings)
    assert exc.value.code == "already_registered"
    assert len(db.list_registrations(settings)) == 1


def test_trailing_slash_and_case_variants_are_the_same_folder(settings, tmp_path):
    project = _make_project(tmp_path)
    registration.register_path(str(project) + "\\", settings)
    for variant in (str(project), str(project) + "/", str(project).upper(), str(project).lower() + "\\"):
        with pytest.raises(registration.RegistrationError) as exc:
            registration.register_path(variant, settings)
        assert exc.value.code == "already_registered"
        assert registration.inspect_path(variant, settings)["registration_status"] == "registered"
    assert len(db.list_registrations(settings)) == 1


def test_windows_path_normalization_uses_real_folder_path(settings, tmp_path):
    project = _make_project(tmp_path)
    messy = str(project.parent) + "\\.\\" + project.name.upper() + "\\"
    review = registration.register_path(messy, settings)
    assert review["path"] == str(project.resolve())
    assert review["name"] == project.name


def test_path_already_found_by_discovery_is_not_double_registered(settings, tmp_path):
    root = tmp_path / "scan-root"
    _write(root / "found" / "pyproject.toml", "[project]\nname='f'")
    service.rescan(settings=settings, root=str(root))
    review = registration.inspect_path(str(root / "found"), settings)
    assert review["registration_status"] == "discovered_via_root"
    with pytest.raises(registration.RegistrationError) as exc:
        registration.register_path(str(root / "found"), settings)
    assert exc.value.code == "already_discovered"


# ---------------------------------------------------------------------------
# Git / non-Git
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git not installed")
def test_git_project_metadata_is_reused(settings, tmp_path):
    project = _make_project(tmp_path)
    _init_git_repo(project)
    review = registration.register_path(str(project), settings)
    assert review["is_git_repo"] is True
    assert review["git_remote"] == "git@example.com:someone/isolated.git"
    assert review["git_last_commit_message"] == "initial commit"
    assert review["git_branch"]


def test_non_git_folder_is_supported(settings, tmp_path):
    project = tmp_path / "home-like" / "plain-notes"
    _write(project / "notes.txt", "hello")
    review = registration.register_path(str(project), settings)
    assert review["is_git_repo"] is False
    item = service.get_item(review["item_id"], settings)
    assert item is not None
    assert item["effective_is_top_level_project"] is True
    assert "explicitly registered by Role as a project folder" in item["boundary_evidence"]


# ---------------------------------------------------------------------------
# Persistence / Discovery independence
# ---------------------------------------------------------------------------


def test_registration_survives_reload_and_rescan(settings, tmp_path, monkeypatch):
    project = _make_project(tmp_path)
    review = registration.register_path(str(project), settings)

    reloaded = Settings()  # a fresh process would build a fresh Settings
    assert [r["item_id"] for r in registration.list_registered(reloaded)] == [review["item_id"]]

    other_root = tmp_path / "unrelated-root"
    _write(other_root / "x" / "pyproject.toml", "[project]\nname='x'")
    service.rescan(settings=reloaded, root=str(other_root))
    ids = {i["id"] for i in service.list_workspace_items(settings=reloaded)}
    assert review["item_id"] in ids


def test_registration_does_not_widen_discovery_roots(settings, tmp_path):
    before = settings.get_discovery_roots()
    project = _make_project(tmp_path)
    _write(project.parent / "sibling-project" / "pyproject.toml", "[project]\nname='s'")
    registration.register_path(str(project), settings)

    assert Settings().get_discovery_roots() == before
    names = {i["name"] for i in service.list_workspace_items(settings=settings)}
    assert "isolated-project" in names
    assert "sibling-project" not in names  # the parent folder was never scanned
    assert "home-like" not in names


def test_refresh_keeps_registration_when_folder_disappears(settings, tmp_path):
    project = _make_project(tmp_path)
    review = registration.register_path(str(project), settings)
    shutil.rmtree(project)
    registration.refresh_all(settings)
    [row] = registration.list_registered(settings)
    assert row["item_id"] == review["item_id"]
    assert row["last_error"]


# ---------------------------------------------------------------------------
# Registration vs adoption
# ---------------------------------------------------------------------------


def test_registration_does_not_auto_adopt_or_classify(settings, tmp_path):
    project = _make_project(tmp_path)
    review = registration.register_path(str(project), settings)
    item = service.get_item(review["item_id"], settings)
    assert item["adopted"] is False
    assert item["registration_source"] == "explicit"
    assert item["domain"] is None and item["client_name"] is None
    assert db.get_overlay(review["item_id"], settings) is None
    assert service.get_summary(settings)["projects_adopted"] == 0
    assert service.get_summary(settings)["projects_registered"] == 1


def test_registered_item_can_be_adopted_through_existing_flow(settings, tmp_path):
    project = _make_project(tmp_path)
    review = registration.register_path(str(project), settings)
    adopted = service.adopt_item(review["item_id"], settings=settings)
    assert adopted["adopted"] is True
    assert registration.inspect_path(str(project), settings)["adoption_status"] == "adopted"


# ---------------------------------------------------------------------------
# Unregister
# ---------------------------------------------------------------------------


def test_unregister_never_touches_the_filesystem(settings, tmp_path):
    project = _make_project(tmp_path)
    before = _tree_snapshot(project)
    review = registration.register_path(str(project), settings)
    result = registration.unregister(review["item_id"], settings)
    assert result["unregistered"] is True
    assert db.list_registrations(settings) == []
    assert project.is_dir()
    assert _tree_snapshot(project) == before
    assert review["item_id"] not in {i["id"] for i in service.list_workspace_items(settings=settings)}


@pytest.mark.skipif(not GIT_AVAILABLE, reason="git not installed")
def test_unregister_keeps_git_history(settings, tmp_path):
    project = _make_project(tmp_path)
    _init_git_repo(project)
    review = registration.register_path(str(project), settings)
    registration.unregister(review["item_id"], settings)
    log = subprocess.run(["git", "log", "--format=%s"], cwd=str(project), capture_output=True, text=True)
    assert log.stdout.strip() == "initial commit"


def test_unregister_is_blocked_for_adopted_project(settings, tmp_path):
    project = _make_project(tmp_path)
    review = registration.register_path(str(project), settings)
    service.adopt_item(review["item_id"], settings=settings)
    with pytest.raises(registration.RegistrationError) as exc:
        registration.unregister(review["item_id"], settings)
    assert exc.value.code == "has_workspace_data"
    assert len(db.list_registrations(settings)) == 1
    assert service.get_item(review["item_id"], settings)["adopted"] is True


def test_unregister_is_blocked_when_notes_exist(settings, tmp_path):
    project = _make_project(tmp_path)
    review = registration.register_path(str(project), settings)
    service.add_note(review["item_id"], "keep me", settings=settings)
    with pytest.raises(registration.RegistrationError) as exc:
        registration.unregister(review["item_id"], settings)
    assert exc.value.code == "has_workspace_data"


def test_unregister_unknown_id(settings):
    with pytest.raises(registration.RegistrationError) as exc:
        registration.unregister("0000000000000000", settings)
    assert exc.value.code == "not_registered"


# ---------------------------------------------------------------------------
# API + Mission Control
# ---------------------------------------------------------------------------


def test_api_inspect_register_list_unregister(settings, tmp_path):
    project = _make_project(tmp_path)

    inspect = client.post("/workspace/registrations/inspect", json={"path": str(project)})
    assert inspect.status_code == 200
    assert inspect.json()["valid"] is True
    assert client.get("/workspace/registrations").json() == []

    bad = client.post("/workspace/registrations/inspect", json={"path": str(tmp_path / "nope")})
    assert bad.status_code == 200 and bad.json()["valid"] is False

    created = client.post("/workspace/registrations", json={"path": str(project)})
    assert created.status_code == 201, created.text
    item_id = created.json()["item_id"]

    dup = client.post("/workspace/registrations", json={"path": str(project) + "\\"})
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "already_registered"

    missing = client.post("/workspace/registrations", json={"path": str(tmp_path / "nope")})
    assert missing.status_code == 400

    listed = client.get("/workspace/registrations").json()
    assert [r["item_id"] for r in listed] == [item_id]

    discovered = client.get(f"/workspace/discovered/{item_id}")
    assert discovered.status_code == 200
    assert discovered.json()["registration_source"] == "explicit"

    gone = client.delete(f"/workspace/registrations/{item_id}")
    assert gone.status_code == 200
    assert client.delete(f"/workspace/registrations/{item_id}").status_code == 404
    assert project.is_dir()


def test_api_unregister_adopted_returns_409(settings, tmp_path):
    project = _make_project(tmp_path)
    item_id = client.post("/workspace/registrations", json={"path": str(project)}).json()["item_id"]
    assert client.post(f"/workspace/discovered/{item_id}/adopt", json={}).status_code == 200
    resp = client.delete(f"/workspace/registrations/{item_id}")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "has_workspace_data"


def test_registered_project_excluded_from_mission_control_until_adopted(settings, tmp_path):
    project = _make_project(tmp_path, name="registered-but-not-adopted-zq")
    item_id = client.post("/workspace/registrations", json={"path": str(project)}).json()["item_id"]

    mc = client.get("/mission-control")
    assert mc.status_code == 200
    assert "registered-but-not-adopted-zq" not in json.dumps(mc.json())

    client.post(f"/workspace/discovered/{item_id}/adopt", json={})
    work = client.get("/mission-control").json()["work"]
    assert "registered-but-not-adopted-zq" in {e["display_name"] for e in work["active_projects"]}


def test_existing_discovery_workspace_flow_unchanged(settings, tmp_path):
    root = tmp_path / "scan-root"
    _write(root / "alpha-app" / "pyproject.toml", "[project]\nname='alpha'")
    _write(root / "beta-docs" / "README.md", "hello")
    _write(root / "beta-docs" / "ROADMAP.md", "plans")
    summary = service.rescan(settings=settings, root=str(root))
    assert summary["projects_found"] == 2
    assert summary["projects_registered"] == 0
    items = service.list_workspace_items(settings=settings)
    assert {i["registration_source"] for i in items} == {"discovery"}


# ---------------------------------------------------------------------------
# UI (string-level, same convention as the other *_ui tests)
# ---------------------------------------------------------------------------


def test_workspace_page_has_register_project_entry_point():
    js = _APP_JS.read_text(encoding="utf-8")
    assert "Register Project" in js
    assert "/workspace/registrations/inspect" in js
    assert 'method: "DELETE"' in js or "method: 'DELETE'" in js
    assert "Validate" in js
    assert "Unregister" in js
