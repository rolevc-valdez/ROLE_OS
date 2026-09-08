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
