"""Regression test for the Windows launcher's dependency check.

Sprint C4 added a `from PIL import Image` runtime dependency (Pillow) but
the launcher's `Test-RoleOSDependencies` function only ever verified a
separately hand-maintained list (`fastapi, uvicorn, pydantic, jinja2`),
so a missing Pillow install was never caught before `uvicorn` was
started -- it crashed instead, mid-import, well after the launcher
declared success. This test proves, without needing Pester or a second
test framework, that `scripts\\RoleOS.Common.ps1`'s dependency check:

1. Derives what to verify from `dashboard/requirements.txt` itself (the
   single source of truth), including the Pillow -> PIL import-name
   mapping specifically.
2. Correctly reports success when every declared package is importable
   (the current, real environment).
3. Correctly detects and names a missing package -- proven with a
   synthetic requirements file naming a package that cannot possibly be
   installed, standing in for "Pillow got uninstalled/never installed"
   without mutating the real environment Pillow install this session
   depends on.
4. `Start-RoleOS.ps1` performs this check strictly before it starts
   `uvicorn` -- so a missing dependency is caught before any server
   process (and therefore any PID file) exists.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_SCRIPT = REPO_ROOT / "scripts" / "RoleOS.Common.ps1"
START_SCRIPT = REPO_ROOT / "scripts" / "Start-RoleOS.ps1"
REAL_REQUIREMENTS = REPO_ROOT / "dashboard" / "requirements.txt"

POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")

pytestmark = pytest.mark.skipif(
    POWERSHELL is None, reason="No PowerShell interpreter available on PATH"
)


def _run_powershell(script: str) -> dict:
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"PowerShell harness itself failed (not the check under test):\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    return json.loads(result.stdout)


def test_pillow_maps_to_its_real_import_name():
    """`Get-RoleOSRequiredImports` must map the PyPI name `Pillow` to the
    module it actually imports as, `PIL` -- simple lowercase/hyphen
    normalization alone (which the launcher uses for every other package)
    would incorrectly produce `pillow`, which does not exist."""
    script = f"""
$ErrorActionPreference = "Stop"
. "{COMMON_SCRIPT}"
$imports = Get-RoleOSRequiredImports -RequirementsPath "{REAL_REQUIREMENTS}"
$imports | ConvertTo-Json -Compress
"""
    imports = _run_powershell(script)
    assert imports["Pillow"] == "PIL"


def test_all_declared_packages_are_importable_in_the_current_environment():
    """Sanity check for the environment this test suite actually runs in:
    every package `dashboard/requirements.txt` declares (including
    Pillow) is importable for `sys.executable`."""
    script = f"""
$ErrorActionPreference = "Stop"
. "{COMMON_SCRIPT}"
$result = Test-RoleOSDependencies -PythonPath "{sys.executable}" -RequirementsPath "{REAL_REQUIREMENTS}"
$result | ConvertTo-Json -Compress
"""
    result = _run_powershell(script)
    assert result["Success"] is True, f"Unexpectedly missing: {result['Missing']}"


def test_missing_dependency_is_detected_and_named(tmp_path):
    """The exact regression: a package declared in requirements.txt but
    not importable must be caught -- named explicitly, not just a bare
    pass/fail -- before uvicorn would ever be started. Uses a synthetic,
    guaranteed-nonexistent package name rather than actually uninstalling
    Pillow, so this test never mutates the real dev environment."""
    fake_requirements = tmp_path / "requirements.txt"
    fake_requirements.write_text(
        "fastapi>=0.111,<1.0\n" "totally-fake-package-that-cannot-exist-c9-regression>=1.0\n",
        encoding="utf-8",
    )
    script = f"""
$ErrorActionPreference = "Stop"
. "{COMMON_SCRIPT}"
$result = Test-RoleOSDependencies -PythonPath "{sys.executable}" -RequirementsPath "{fake_requirements}"
$result | ConvertTo-Json -Compress
"""
    result = _run_powershell(script)
    assert result["Success"] is False
    missing = result["Missing"]
    if isinstance(missing, str):
        missing = [missing]
    assert "totally-fake-package-that-cannot-exist-c9-regression" in missing
    assert "fastapi" not in missing


def test_dependency_check_runs_strictly_before_uvicorn_is_started():
    """A static ordering guard: if a future edit ever moved the
    dependency check after the `uvicorn` `Start-Process` call, a missing
    package would crash the server process instead of being caught
    first, and could leave a stale PID file behind. Asserts the check
    call appears earlier in the file than the process start."""
    text = START_SCRIPT.read_text(encoding="utf-8")
    dependency_check_pos = text.index("Test-RoleOSDependencies")
    uvicorn_start_pos = text.index("Start-Process -FilePath $python.Path")
    assert dependency_check_pos < uvicorn_start_pos
