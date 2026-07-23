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
os.environ.setdefault("ROLE_OS_PROJECTS_DB_PATH", str(Path(_PROJECTS_DB_DIR) / "role_os_projects.db"))

# AI Advisor (Epic 2) also owns its own SQLite file and auto-creates its
# schema on first use, so tests get a fresh, isolated recommendations store.
_ADVISOR_DB_DIR = tempfile.mkdtemp(prefix="role_os_advisor_test_")
os.environ.setdefault("ROLE_OS_ADVISOR_DB_PATH", str(Path(_ADVISOR_DB_DIR) / "role_os_advisor.db"))
