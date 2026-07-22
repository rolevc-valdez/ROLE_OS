import os
import sys
from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DASHBOARD_ROOT))

os.environ.setdefault(
    "ROLE_OS_DB_PATH",
    str((DASHBOARD_ROOT.parent / "samples/role_os_sample/00_SYSTEM/role_os.db").resolve()),
)
