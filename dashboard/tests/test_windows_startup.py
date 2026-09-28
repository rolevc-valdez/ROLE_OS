"""Phase 3 Task 7 (Windows startup & daily launch) tests.

AUTOMATED TESTS ONLY -- these exercise the launch-time freshness rule and the
real PowerShell helper functions (run through powershell.exe against a local
stub HTTP server and a temporary Startup folder). They are NOT proof of a
real Windows sign-in; that is validated separately and recorded in
docs/PHASE_3_TASK_7_WINDOWS_STARTUP.md.

Nothing here touches the real Startup folder, the real port 8000 server, or
any canonical runtime database.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from app.config import Settings, get_settings
from app.main import app
from app.workspace import db, registration, service
from fastapi.testclient import TestClient

client = TestClient(app)
_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO / "scripts"
_COMMON = _SCRIPTS / "RoleOS.Common.ps1"
_START = _SCRIPTS / "Start-RoleOS.ps1"
_POWERSHELL = shutil.which("powershell")
windows_only = pytest.mark.skipif(
    platform.system() != "Windows" or not _POWERSHELL, reason="needs Windows PowerShell"
)


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("ROLE_OS_WORKSPACE_DB_PATH", str(tmp_path / "ws" / "workspace.db"))
    monkeypatch.setenv("ROLE_OS_PROJECTS_DB_PATH", str(tmp_path / "pi" / "projects.db"))
    monkeypatch.delenv("ROLE_OS_DISCOVERY_ROOTS", raising=False)
    root = tmp_path / "configured-root"
    (root / "found-project").mkdir(parents=True)
    (root / "found-project" / "pyproject.toml").write_text("[project]\nname='f'", encoding="utf-8")
    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOT", str(root))
    get_settings.cache_clear()
    yield Settings()
    get_settings.cache_clear()


def _age_scan(settings, hours: float) -> None:
    cache = db.load_scan_cache(settings)
    old = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    db.save_scan_cache(
        root=cache["root"], scanned_at=old, duration_seconds=cache["duration_seconds"],
        projects=cache["projects"], settings=settings,
    )


# ---------------------------------------------------------------------------
# Launch-time Workspace freshness (backend rule)
# ---------------------------------------------------------------------------


def test_fresh_scan_is_reused(settings):
    service.rescan(settings=settings)
    before = db.load_scan_cache(settings)["scanned_at"]
    result = service.rescan_if_stale(settings)
    assert result["rescanned"] is False and result["reason"] == "fresh"
    assert db.load_scan_cache(settings)["scanned_at"] == before


def test_scan_older_than_24h_is_refreshed_safely(settings, tmp_path):
    service.rescan(settings=settings)
    [found] = service.list_workspace_items(settings=settings)
    service.adopt_item(found["id"], domain="ROLE PERSONAL", settings=settings)
    isolated = tmp_path / "elsewhere" / "registered-one"
    isolated.mkdir(parents=True)
    reg = registration.register_path(str(isolated), settings)
    ext = service.create_external_work({"name": "ext tool", "kind": "tool", "source": "web"}, settings=settings)["item"]
    (tmp_path / "configured-root" / "new-unadopted").mkdir()
    (tmp_path / "configured-root" / "new-unadopted" / "package.json").write_text("{}", encoding="utf-8")
    roots_before = Settings().get_discovery_roots()
    _age_scan(settings, 30)

    result = service.rescan_if_stale(settings)

    assert result["rescanned"] is True and result["reason"] == "stale"
    assert result["freshness"]["is_stale"] is False
    assert Settings().get_discovery_roots() == roots_before  # roots never widened
    items = {i["name"]: i for i in service.list_workspace_items(settings=settings)}
    assert items["found-project"]["adopted"] is True and items["found-project"]["domain"] == "ROLE PERSONAL"
    assert items["new-unadopted"]["adopted"] is False  # discovered, never auto-adopted
    assert "registered-one" in items and items["registered-one"]["adopted"] is False
    assert items["ext tool"]["kind"] == "tool" and items["ext tool"]["id"] == ext["id"]
    assert [r["item_id"] for r in registration.list_registered(settings)] == [reg["item_id"]]


def test_never_scanned_workspace_is_scanned(settings):
    result = service.rescan_if_stale(settings)
    assert result["rescanned"] is True and result["reason"] == "never_scanned"


def test_rescan_failure_is_reported_not_raised(settings, monkeypatch, tmp_path):
    monkeypatch.setenv("ROLE_OS_DISCOVERY_ROOT", str(tmp_path / "does-not-exist"))
    result = service.rescan_if_stale(Settings())
    assert result["rescanned"] is False and result["reason"] == "rescan_failed" and result["error"]


def test_rescan_if_stale_endpoint(settings):
    resp = client.post("/workspace/rescan-if-stale")
    assert resp.status_code == 200
    assert resp.json()["rescanned"] is True
    again = client.post("/workspace/rescan-if-stale").json()
    assert again["rescanned"] is False and again["reason"] == "fresh"


# ---------------------------------------------------------------------------
# PowerShell launcher logic (real powershell.exe, stub server, temp folder)
# ---------------------------------------------------------------------------


def _ps(script: str, timeout: int = 60) -> str:
    wrapped = f"$ErrorActionPreference = 'Stop'; . '{_COMMON}'; {script}"
    proc = subprocess.run(
        [_POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", wrapped],
        capture_output=True, text=True, timeout=timeout,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


class _Stub:
    """A tiny local HTTP server standing in for /health on a free port."""

    def __init__(self, body: dict | str):
        payload = (json.dumps(body) if isinstance(body, dict) else body).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/health"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


def _free_port_url() -> str:
    s = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = s.server_port
    s.server_close()
    return f"http://127.0.0.1:{port}/health"


@windows_only
def test_all_launcher_scripts_parse():
    for script in sorted(_SCRIPTS.glob("*.ps1")):
        out = _ps(
            f"$e = $null; $null = [System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$e); $e.Count"
        )
        assert out == "0", script.name


@windows_only
def test_health_probe_distinguishes_role_os_other_app_and_nothing():
    role = _Stub({"status": "ok", "app": "ROLE OS", "version": "9.9"})
    other = _Stub("<html>something else</html>")
    try:
        probe = "$h = Test-RoleOSHealth -TimeoutSec 2; \"$($h.Responding)|$($h.IsRoleOS)|$($h.Version)\""
        assert _ps(f"$RoleOSHealthUrl = '{role.url}'; {probe}") == "True|True|9.9"
        assert _ps(f"$RoleOSHealthUrl = '{other.url}'; {probe}") == "True|False|"
        assert _ps(f"$RoleOSHealthUrl = '{_free_port_url()}'; {probe}") == "False|False|"
    finally:
        role.close()
        other.close()


@windows_only
def test_readiness_wait_succeeds_on_real_health_and_times_out_otherwise():
    role = _Stub({"status": "ok", "app": "ROLE OS", "version": "1"})
    try:
        assert _ps(f"$RoleOSHealthUrl = '{role.url}'; $null -ne (Wait-RoleOSHealthy -TimeoutSeconds 5)") == "True"
    finally:
        role.close()
    started = time.monotonic()
    out = _ps(f"$RoleOSHealthUrl = '{_free_port_url()}'; $null -eq (Wait-RoleOSHealthy -TimeoutSeconds 2 -IntervalMs 200)")
    assert out == "True"
    assert time.monotonic() - started < 30  # bounded, never loops forever


@windows_only
def test_startup_enable_status_disable_in_a_temp_startup_folder(tmp_path):
    folder = tmp_path / "Startup"
    repo = str(_REPO)
    status = "$s = Get-RoleOSStartupStatus -RepoRoot $repo -StartupFolder $f; \"$($s.Enabled)|$($s.PointsToThisRepo)|$($s.Arguments)\""
    prefix = f"$repo = '{repo}'; $f = '{folder}';"

    assert _ps(prefix + status).startswith("False|False|")
    enabled = _ps(prefix + "$null = Enable-RoleOSStartup -RepoRoot $repo -StartupFolder $f;" + status)
    flag, points, args = enabled.split("|", 2)
    assert (flag, points) == ("True", "True")
    assert "-WindowStyle Hidden" in args and args.endswith("-Startup")
    assert str(_START) in args
    _ps(prefix + "$null = Enable-RoleOSStartup -RepoRoot $repo -StartupFolder $f")  # idempotent
    assert [p.name for p in folder.iterdir()] == ["ROLE OS.lnk"]

    assert _ps(prefix + "$null = Disable-RoleOSStartup -RepoRoot $repo -StartupFolder $f;" + status).startswith("False|")
    assert list(folder.iterdir()) == []
    _ps(prefix + "$null = Disable-RoleOSStartup -RepoRoot $repo -StartupFolder $f")  # already disabled: fine


@windows_only
def test_default_startup_folder_is_current_user_scope():
    folder = _ps("Get-RoleOSStartupFolder")
    assert folder.lower().endswith(r"\microsoft\windows\start menu\programs\startup")
    assert "programdata" not in folder.lower()  # never the machine-wide All Users folder


# ---------------------------------------------------------------------------
# Launcher wiring (static checks -- the real behavior is validated live)
# ---------------------------------------------------------------------------


def test_destination_is_the_daily_command_center():
    common = _COMMON.read_text(encoding="utf-8-sig")
    assert '$RoleOSBaseUrl = "http://${RoleOSHost}:${RoleOSPort}"' in common
    for script in _SCRIPTS.glob("*.ps1"):
        assert "#/dashboard" not in script.read_text(encoding="utf-8-sig")
    start = _START.read_text(encoding="utf-8-sig")
    assert start.count("Start-Process $RoleOSBaseUrl") == 2  # already-running + freshly started


def test_launcher_is_idempotent_and_refresh_never_blocks_the_page():
    start = _START.read_text(encoding="utf-8-sig")
    probe = start.index("$health = Test-RoleOSHealth")
    already = start.index("if ($health.Responding -and $health.IsRoleOS) {")
    spawn = start.index("$proc = Start-Process -FilePath $python.Path")
    assert probe < already < spawn  # health checked before any server is started
    last_browser = start.rindex("Start-Process $RoleOSBaseUrl")
    assert start.rindex("Invoke-RoleOSFreshnessCheck") > last_browser  # browser first, scan after
    assert "param([switch]$Startup)" in start
    assert "Wait-RoleOSHealthy -TimeoutSeconds $timeoutSeconds -Process $proc" in start


def test_manual_launcher_unchanged():
    bat = (_REPO / "Start ROLE OS.bat").read_text(encoding="utf-8")
    assert r'-File "%SCRIPT_DIR%scripts\Start-RoleOS.ps1"' in bat
    assert "-Startup" not in bat  # manual launch keeps its visible, interactive behavior
