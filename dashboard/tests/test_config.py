"""Role OS 2.0 Phase 1 Task 2: normal runtime must never silently default
into the bundled samples/ fixture tree. These tests exercise `Settings()`
directly (bypassing `get_settings()`'s cache) so each case controls its own
environment precisely, regardless of what `conftest.py` has already set for
the rest of the suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings

_SAMPLE_DB_ENV_VARS = [
    "ROLE_OS_DB_PATH",
    "ROLE_OS_PROJECTS_DB_PATH",
    "ROLE_OS_ADVISOR_DB_PATH",
    "ROLE_OS_IMPORTS_DB_PATH",
    "ROLE_OS_EXTRACTION_DB_PATH",
]

_ALL_DASHBOARD_DB_ENV_VARS = _SAMPLE_DB_ENV_VARS + [
    "ROLE_OS_SESSION_DB_PATH",
    "ROLE_OS_WORKSPACE_DB_PATH",
    "ROLE_OS_ASSETS_DB_PATH",
    "ROLE_OS_ASSET_THUMBNAIL_CACHE_DIR",
    "ROLE_OS_ECOSYSTEM_DB_PATH",
]


@pytest.fixture
def no_db_env_overrides(monkeypatch: pytest.MonkeyPatch):
    """Simulate a clean environment where nothing has set any of the five
    ROLE_OS_*_DB_PATH variables -- i.e. what `conftest.py`'s own
    `setdefault()` calls stand in for the rest of the suite, but here
    explicitly removed so the *true* default (not the test session's
    already-set value) is what `Settings()` resolves.
    """
    for name in _SAMPLE_DB_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def no_dashboard_db_env_overrides(monkeypatch: pytest.MonkeyPatch):
    """Same as `no_db_env_overrides`, but clears all ten dashboard-owned
    path variables (the Task 2 `var/role_os/` family plus the Task 3B
    `var/role_os_dashboard/` family) -- used by the CWD-independence
    tests below, which need every default path visible at once.
    """
    for name in _ALL_DASHBOARD_DB_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _all_default_paths(settings: Settings) -> dict[str, Path]:
    return {
        "db_path": settings.db_path,
        "projects_db_path": settings.projects_db_path,
        "advisor_db_path": settings.advisor_db_path,
        "imports_db_path": settings.imports_db_path,
        "extraction_db_path": settings.extraction_db_path,
        "session_db_path": settings.session_db_path,
        "workspace_db_path": settings.workspace_db_path,
        "assets_db_path": settings.assets_db_path,
        "asset_thumbnail_cache_dir": settings.asset_thumbnail_cache_dir,
        "ecosystem_db_path": settings.ecosystem_db_path,
    }


def test_normal_runtime_default_does_not_point_into_samples(no_db_env_overrides):
    settings = Settings()
    for path in (
        settings.db_path,
        settings.projects_db_path,
        settings.advisor_db_path,
        settings.imports_db_path,
        settings.extraction_db_path,
    ):
        assert "samples" not in path.parts, f"{path} still defaults into samples/"


def test_knowledge_db_normal_default_is_under_var_role_os(no_db_env_overrides):
    settings = Settings()
    assert settings.db_path.parent.name == "role_os"
    assert "var" in settings.db_path.parts
    assert settings.db_path.name == "role_os.db"


def test_projects_db_normal_default_is_under_var_role_os(no_db_env_overrides):
    settings = Settings()
    assert settings.projects_db_path.parent.name == "role_os"
    assert "var" in settings.projects_db_path.parts
    assert settings.projects_db_path.name == "role_os_projects.db"


def test_advisor_imports_extraction_db_defaults_are_under_var_role_os(no_db_env_overrides):
    """Same defect family as Projects DB: these three also own a real,
    dashboard-written SQLite file and must not default into samples/."""
    settings = Settings()
    for path, expected_name in (
        (settings.advisor_db_path, "role_os_advisor.db"),
        (settings.imports_db_path, "role_os_imports.db"),
        (settings.extraction_db_path, "role_os_extraction.db"),
    ):
        assert path.parent.name == "role_os"
        assert "var" in path.parts
        assert path.name == expected_name


def test_explicit_db_path_override_still_works(monkeypatch: pytest.MonkeyPatch, tmp_path):
    override = tmp_path / "custom_knowledge.db"
    monkeypatch.setenv("ROLE_OS_DB_PATH", str(override))
    settings = Settings()
    assert settings.db_path == override.resolve()


def test_explicit_projects_db_path_override_still_works(monkeypatch: pytest.MonkeyPatch, tmp_path):
    override = tmp_path / "custom_projects.db"
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(override))
    settings = Settings()
    assert settings.projects_db_path == override.resolve()


def test_tests_and_demos_can_explicitly_select_the_sample_knowledge_db(
    monkeypatch: pytest.MonkeyPatch,
):
    """Explicit sample selection (what conftest.py itself does for the whole
    suite) must keep working -- samples/ is not removed or blocked, only no
    longer reached by accident."""
    sample_path = "samples/role_os_sample/00_SYSTEM/role_os.db"
    monkeypatch.setenv("ROLE_OS_DB_PATH", sample_path)
    settings = Settings()
    assert settings.db_path == Path(sample_path).resolve()


def test_no_silent_fallback_to_samples_when_normal_runtime_db_path_is_unset(
    no_db_env_overrides,
):
    """The regression this task exists to prevent: previously, simply not
    setting any ROLE_OS_*_DB_PATH env var caused normal runtime to silently
    read/write the bundled samples/ fixture tree."""
    settings = Settings()
    for path in (
        settings.db_path,
        settings.projects_db_path,
        settings.advisor_db_path,
        settings.imports_db_path,
        settings.extraction_db_path,
    ):
        assert "samples" not in str(path)


def test_projects_db_still_auto_creates_at_the_new_default_location(
    no_db_env_overrides, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Existing DB initialization behavior (CREATE TABLE IF NOT EXISTS +
    mkdir(parents=True)) is unchanged -- only the default location moved."""
    from app.projects.db import get_connection

    fake_var_role_os = tmp_path / "var" / "role_os"
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(fake_var_role_os / "role_os_projects.db"))
    settings = Settings()
    assert not settings.projects_db_path.exists()
    with get_connection(settings) as conn:
        conn.execute("SELECT 1")
    assert settings.projects_db_path.exists()


def test_missing_knowledge_db_at_new_default_fails_clearly_not_silently(
    no_db_env_overrides, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Existing failure behavior for the read-only Knowledge DB (Option B:
    raise a clear error / report disconnected) is unchanged -- Task 2 does
    not copy the sample DB as an implicit initialization mechanism."""
    from app.db import DatabaseUnavailableError, database_exists, get_connection

    monkeypatch.setenv("ROLE_OS_DB_PATH", str(tmp_path / "var" / "role_os" / "role_os.db"))
    settings = Settings()
    assert database_exists(settings) is False
    with pytest.raises(DatabaseUnavailableError):
        with get_connection(settings):
            pass


# --- Phase 1 Task 3B: CWD-independent path resolution -----------------
#
# Task 3 discovered that real launcher runs (CWD=dashboard/) and this
# session's own pytest runs (CWD=repo root) had been resolving
# `var/role_os_dashboard/...` to two different absolute locations,
# silently splitting real runtime data. These tests prove every
# dashboard-owned default now resolves to the exact same absolute path
# no matter what the process's current working directory is. None of
# them open or write any SQLite file -- only `Settings()` field values
# are compared.

_CWD_CANDIDATES = ["repo_root", "dashboard", "scripts", "unrelated_tmp_dir"]


def _resolve_cwd_candidate(name: str, tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    if name == "repo_root":
        return repo_root
    if name == "dashboard":
        return repo_root / "dashboard"
    if name == "scripts":
        return repo_root / "scripts"
    if name == "unrelated_tmp_dir":
        return tmp_path
    raise ValueError(name)


@pytest.mark.parametrize("cwd_name", _CWD_CANDIDATES)
def test_normal_runtime_paths_are_identical_regardless_of_launch_directory(
    cwd_name, no_dashboard_db_env_overrides, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """The core Task 3B guarantee: starting Role OS from the repository
    root, dashboard/, scripts/, or a completely unrelated directory must
    resolve every normal-runtime default to the same absolute path."""
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root)
    baseline = _all_default_paths(Settings())

    monkeypatch.chdir(_resolve_cwd_candidate(cwd_name, tmp_path))
    from_other_cwd = _all_default_paths(Settings())

    assert from_other_cwd == baseline, (
        f"Settings() resolved different paths when launched from '{cwd_name}': "
        f"{from_other_cwd} != {baseline}"
    )


def test_dashboard_family_defaults_are_anchored_under_repo_root_var_role_os_dashboard(
    no_dashboard_db_env_overrides, monkeypatch: pytest.MonkeyPatch
):
    """Session/workspace/assets/ecosystem/thumbnail-cache defaults
    (Task 3's investigated family) resolve under <repo_root>/var/
    role_os_dashboard/, not a CWD-relative guess -- verified by starting
    from dashboard/, the one real launcher CWD that previously diverged.
    """
    repo_root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo_root / "dashboard")
    settings = Settings()
    expected_dir = repo_root / "var" / "role_os_dashboard"
    assert settings.session_db_path == expected_dir / "role_os_session.db"
    assert settings.workspace_db_path == expected_dir / "role_os_workspace.db"
    assert settings.assets_db_path == expected_dir / "role_os_assets.db"
    assert settings.ecosystem_db_path == expected_dir / "role_os_ecosystem.db"
    assert settings.asset_thumbnail_cache_dir == expected_dir / "asset_thumbnails"


def test_explicit_overrides_still_take_precedence_from_any_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """An explicit ROLE_OS_*_DB_PATH always wins, regardless of which
    directory the process was started from -- overrides are used as
    given (resolved as any absolute path is), never re-anchored."""
    override = tmp_path / "explicit_workspace.db"
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(override))

    monkeypatch.chdir(Path(__file__).resolve().parents[2] / "scripts")
    settings = Settings()
    assert settings.workspace_db_path == override.resolve()


def test_sample_and_demo_paths_remain_explicit_after_cwd_fix(
    monkeypatch: pytest.MonkeyPatch,
):
    """Explicit sample/demo selection (e.g. run_alpha.*, or a deliberate
    ROLE_OS_WORKSPACE_DIR-style override) is untouched by the CWD fix --
    only defaults changed, not override semantics."""
    repo_root = Path(__file__).resolve().parents[2]
    sample_path = repo_root / "samples" / "role_os_sample" / "00_SYSTEM" / "role_os.db"
    monkeypatch.setenv("ROLE_OS_DB_PATH", str(sample_path))
    monkeypatch.chdir(repo_root / "dashboard")
    settings = Settings()
    assert settings.db_path == sample_path.resolve()
