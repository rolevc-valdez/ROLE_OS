import os
import sys
import tempfile
from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DASHBOARD_ROOT))

os.environ.setdefault(
    "ROLE_OS_DB_PATH",
    str((DASHBOARD_ROOT.parent / "samples/role_os_sample/00_SYSTEM/role_os.db").resolve()),
)

# Project Intelligence (Epic 1) owns its own SQLite file and auto-creates its
# schema + seeds default workspaces on first use, so tests get a fresh,
# isolated database rather than mutating any committed sample file.
_PROJECTS_DB_DIR = tempfile.mkdtemp(prefix="role_os_projects_test_")
os.environ.setdefault(
    "ROLE_OS_PROJECTS_DB_PATH", str(Path(_PROJECTS_DB_DIR) / "role_os_projects.db")
)

# AI Advisor (Epic 2) also owns its own SQLite file and auto-creates its
# schema on first use, so tests get a fresh, isolated recommendations store.
_ADVISOR_DB_DIR = tempfile.mkdtemp(prefix="role_os_advisor_test_")
os.environ.setdefault("ROLE_OS_ADVISOR_DB_PATH", str(Path(_ADVISOR_DB_DIR) / "role_os_advisor.db"))

# ChatGPT Conversation Importer (Sprint B1) also owns its own SQLite file and
# auto-creates its schema on first use, so tests get a fresh, isolated store
# rather than mutating any committed sample database.
_IMPORTS_DB_DIR = tempfile.mkdtemp(prefix="role_os_imports_test_")
os.environ.setdefault("ROLE_OS_IMPORTS_DB_PATH", str(Path(_IMPORTS_DB_DIR) / "role_os_imports.db"))

# Knowledge Extraction (Sprint 4) also owns its own SQLite file and
# auto-creates its schema on first use, so tests get a fresh, isolated store.
_EXTRACTION_DB_DIR = tempfile.mkdtemp(prefix="role_os_extraction_test_")
os.environ.setdefault(
    "ROLE_OS_EXTRACTION_DB_PATH", str(Path(_EXTRACTION_DB_DIR) / "role_os_extraction.db")
)

# Daily Session (ROLE OS Dashboard MVP) also owns its own SQLite file and
# auto-creates its schema + seeds the default project registry on first
# use, so tests get a fresh, isolated store.
_SESSION_DB_DIR = tempfile.mkdtemp(prefix="role_os_session_test_")
os.environ.setdefault("ROLE_OS_SESSION_DB_PATH", str(Path(_SESSION_DB_DIR) / "role_os_session.db"))

# Workspace Adoption (Discovery Engine Sprint 2) also owns its own SQLite
# file and auto-creates its schema on first use, so tests get a fresh,
# isolated store. Tests always pass an explicit `root` to /workspace/rescan
# pointing at their own tmp_path fixtures, so no default discovery root is
# set here.
_WORKSPACE_DB_DIR = tempfile.mkdtemp(prefix="role_os_workspace_test_")
os.environ.setdefault(
    "ROLE_OS_WORKSPACE_DB_PATH", str(Path(_WORKSPACE_DB_DIR) / "role_os_workspace.db")
)

# Role OS 2.0 Phase 2 Task 1: Assets OS, its thumbnail cache, and the
# Project Ecosystem overlay were the three dashboard-owned path fields
# NOT covered by a session-wide default here -- a handful of individual
# test files (test_assets_os.py, test_executive_decision.py,
# test_impact_analysis.py, test_project_ecosystem.py,
# test_session_intent.py) already isolate these with their own
# `monkeypatch.setenv()` calls inside specific test functions, but any
# other test anywhere in the suite that happened to touch Assets OS or
# Ecosystem code (e.g. Mission Control's shared `request_scope()`
# filesystem walk) with no such per-test override fell through to
# `config.py`'s real default -- the actual, real `var/role_os_dashboard/`
# runtime files, not a fixture. Confirmed repeatedly across Phase 1 (see
# docs/RUNTIME_DATA_MAP.md, docs/PHASE_2_TASK_1_TEST_ISOLATION.md).
# Following the exact same pattern as every other domain above closes
# this gap for the whole test session, not just the five files that
# happened to notice it themselves.
_ASSETS_DB_DIR = tempfile.mkdtemp(prefix="role_os_assets_test_")
os.environ.setdefault("ROLE_OS_ASSETS_DB_PATH", str(Path(_ASSETS_DB_DIR) / "role_os_assets.db"))
os.environ.setdefault(
    "ROLE_OS_ASSET_THUMBNAIL_CACHE_DIR", str(Path(_ASSETS_DB_DIR) / "asset_thumbnails")
)

_ECOSYSTEM_DB_DIR = tempfile.mkdtemp(prefix="role_os_ecosystem_test_")
os.environ.setdefault(
    "ROLE_OS_ECOSYSTEM_DB_PATH", str(Path(_ECOSYSTEM_DB_DIR) / "role_os_ecosystem.db")
)
