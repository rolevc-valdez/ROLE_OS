<#
.SYNOPSIS
    Starts the ROLE OS dashboard and opens it in the default browser.

.DESCRIPTION
    1. Resolves the repository directory from this script's own location.
    2. Checks whether ROLE OS is already healthy on http://127.0.0.1:8000
       -- if so, just opens the browser and exits (no second server).
    3. Otherwise, resolves a Python interpreter (preferring a local
       virtual environment) and verifies dependencies.
    4. Resolves the five ROLE_OS_*_DB_PATH database variables as absolute
       paths anchored to the repository root (not to dashboard\, even
       though that's the working directory uvicorn runs from) and refuses
       to start if the Knowledge database is missing.
    5. Starts `uvicorn app.main:app --host 127.0.0.1 --port 8000` as a
       separate, minimized process from the dashboard directory, waits
       for it to become healthy, then opens the browser.

    Intended to be run via "Start ROLE OS.bat" (a thin double-click
    wrapper), but works standalone:
      powershell -ExecutionPolicy Bypass -File scripts\Start-RoleOS.ps1
#>

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "RoleOS.Common.ps1")

$paths = Get-RoleOSPaths

# ---------------------------------------------------------------------
# 1. Missing dashboard folder -- checked, and failed, BEFORE creating
#    $paths.VarDir (which lives under dashboard\). Creating that
#    directory first would silently recreate an empty "dashboard" stub
#    via New-Item's intermediate-directory creation, masking the real
#    problem. Console-only output here, deliberately: the log file also
#    lives under dashboard\, so it isn't safe to write to yet either.
# ---------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $paths.DashboardDir -PathType Container)) {
    Write-Host "[ERROR] Dashboard folder not found at '$($paths.DashboardDir)'. Is this launcher still inside the ROLE_OS repository (it must stay in the repo root, next to the 'dashboard' folder)?" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $paths.DashboardDir "app\main.py") -PathType Leaf)) {
    Write-Host "[ERROR] '$($paths.DashboardDir)' does not look like the ROLE OS dashboard (missing app\main.py). Check that the repository wasn't partially moved or corrupted." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Path $paths.VarDir -Force | Out-Null

function Fail([string]$Message) {
    Write-RoleOSLog -Level ERROR -LogFile $paths.LauncherLog -Message $Message
    exit 1
}

Write-RoleOSLog -LogFile $paths.LauncherLog -Message "---- Start ROLE OS ----"
Write-RoleOSLog -LogFile $paths.LauncherLog -Message "Repository root: $($paths.RepoRoot)"

# ---------------------------------------------------------------------
# 2. Already running? Probe first, before touching Python/venv at all.
# ---------------------------------------------------------------------
Write-RoleOSLog -LogFile $paths.LauncherLog -Message "Checking whether ROLE OS is already running at $RoleOSHealthUrl ..."
$health = Test-RoleOSHealth

if ($health.Responding -and $health.IsRoleOS) {
    Write-RoleOSLog -LogFile $paths.LauncherLog -Message "ROLE OS is already running (version $($health.Version)). Opening browser without starting a second server."
    Start-Process $RoleOSBaseUrl
    exit 0
}

if ($health.Responding -and -not $health.IsRoleOS) {
    Fail "Port $RoleOSPort is already in use by a different application (it responded, but not with a ROLE OS health payload). Close whatever is using port $RoleOSPort and run this launcher again. Response received: $($health.Body)"
}

Write-RoleOSLog -LogFile $paths.LauncherLog -Message "Nothing responding yet ($($health.Error)); starting a new server."

# ---------------------------------------------------------------------
# 3. Resolve Python (venv preferred, then py/python/python3)
# ---------------------------------------------------------------------
$python = Find-RoleOSPython -DashboardDir $paths.DashboardDir -RepoRoot $paths.RepoRoot -LogFile $paths.LauncherLog
if (-not $python) {
    Fail @"
No usable Python interpreter was found.

Checked, in order: dashboard\.venv, repository-root\.venv, dashboard\venv,
repository-root\venv, then 'py', 'python', and 'python3' on PATH.

Install Python 3.10 or later from https://www.python.org/downloads/
(or create a virtual environment: py -m venv .venv) and try again.
"@
}

$previousPreference = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try {
    $null = & $python.Path --version 2>&1
} finally {
    $ErrorActionPreference = $previousPreference
}
if ($LASTEXITCODE -ne 0) {
    Fail "Found a Python interpreter at '$($python.Path)' but it failed to run ('--version' exited with code $LASTEXITCODE). The virtual environment may be broken -- try deleting it and running: py -m venv .venv"
}

# ---------------------------------------------------------------------
# 4. Verify dependencies -- every package declared in
#    dashboard\requirements.txt (the single source of truth), not a
#    separately hand-maintained list that can silently fall behind it.
# ---------------------------------------------------------------------
$reqPath = Join-Path $paths.DashboardDir "requirements.txt"
Write-RoleOSLog -LogFile $paths.LauncherLog -Message "Verifying required packages (from dashboard\requirements.txt)..."
$depCheck = Test-RoleOSDependencies -PythonPath $python.Path -RequirementsPath $reqPath
if (-not $depCheck.Success) {
    $missingList = $depCheck.Missing -join ", "
    Fail @"
ROLE OS is missing required Python package(s) for '$($python.Path)':
    $missingList

Install them with:
    "$($python.Path)" -m pip install -r "$reqPath"

Then run this launcher again.
"@
}

# ---------------------------------------------------------------------
# 5. Resolve database paths as absolutes anchored to the repository
#    root -- NOT relative to dashboard\, even though that's the working
#    directory uvicorn is about to be started from. See
#    Resolve-RoleOSDatabaseEnv's own doc comment for why this is
#    necessary (dashboard\app\config.py's own defaults are CWD-relative).
# ---------------------------------------------------------------------
$dbEnv = Resolve-RoleOSDatabaseEnv -RepoRoot $paths.RepoRoot -LogFile $paths.LauncherLog

if (-not (Test-Path -LiteralPath $dbEnv.ROLE_OS_DB_PATH -PathType Leaf)) {
    Fail @"
The Knowledge database was not found at:
    $($dbEnv.ROLE_OS_DB_PATH)

Refusing to start with a broken Knowledge page. This file is generated by
the Builder (see builder\README.md) and is not created automatically.

If you're using the bundled sample data, check that the repository's
samples\role_os_sample\00_SYSTEM\ folder wasn't moved, renamed, or
deleted. If you meant to point at your own workspace, set
ROLE_OS_WORKSPACE_DIR to its folder (the one containing 00_SYSTEM\) before
running this launcher again -- see INSTALLATION.md for details.
"@
}
Write-RoleOSLog -LogFile $paths.LauncherLog -Message "Knowledge database confirmed present at $($dbEnv.ROLE_OS_DB_PATH)"

# ---------------------------------------------------------------------
# 6. Start uvicorn as a separate, minimized process
# ---------------------------------------------------------------------
Write-RoleOSLog -LogFile $paths.LauncherLog -Message "Starting uvicorn from '$($paths.DashboardDir)' using '$($python.Path)' ($($python.Source))..."

if (Test-Path -LiteralPath $paths.PidFile) {
    Write-RoleOSLog -Level WARN -LogFile $paths.LauncherLog -Message "Removing stale PID file before starting a new server."
    Remove-Item -LiteralPath $paths.PidFile -Force -ErrorAction SilentlyContinue
}

$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", $RoleOSHost, "--port", "$RoleOSPort")

try {
    $proc = Start-Process -FilePath $python.Path `
        -ArgumentList $uvicornArgs `
        -WorkingDirectory $paths.DashboardDir `
        -WindowStyle Minimized `
        -RedirectStandardOutput $paths.UvicornLog `
        -RedirectStandardError $paths.UvicornErrLog `
        -PassThru
} catch {
    Fail "Failed to launch the server process: $($_.Exception.Message)"
}

Set-Content -LiteralPath $paths.PidFile -Value $proc.Id -Encoding ASCII
Write-RoleOSLog -LogFile $paths.LauncherLog -Message "Server process started (PID $($proc.Id)). Waiting for it to become healthy..."

# ---------------------------------------------------------------------
# 7. Wait for /health, with a reasonable timeout
# ---------------------------------------------------------------------
$timeoutSeconds = 30
$intervalMs = 500
$elapsedMs = 0
$healthy = $false

while ($elapsedMs -lt ($timeoutSeconds * 1000)) {
    if ($proc.HasExited) {
        Fail "The server process exited immediately (exit code $($proc.ExitCode)) before becoming healthy. Check the log for details: $($paths.UvicornErrLog)`n`nLast lines:`n$((Get-Content -LiteralPath $paths.UvicornErrLog -Tail 15 -ErrorAction SilentlyContinue) -join [Environment]::NewLine)"
    }
    $check = Test-RoleOSHealth -TimeoutSec 1
    if ($check.Responding -and $check.IsRoleOS) {
        $healthy = $true
        break
    }
    Start-Sleep -Milliseconds $intervalMs
    $elapsedMs += $intervalMs
}

if (-not $healthy) {
    Write-RoleOSLog -Level ERROR -LogFile $paths.LauncherLog -Message "Server did not become healthy within $timeoutSeconds seconds. Stopping it and cleaning up."
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $paths.PidFile -Force -ErrorAction SilentlyContinue
    Fail "ROLE OS failed to become healthy in time. Check the log for details: $($paths.UvicornErrLog)`n`nLast lines:`n$((Get-Content -LiteralPath $paths.UvicornErrLog -Tail 15 -ErrorAction SilentlyContinue) -join [Environment]::NewLine)"
}

Write-RoleOSLog -LogFile $paths.LauncherLog -Message "ROLE OS is healthy (version $($check.Version)). Opening browser at $RoleOSBaseUrl"
Start-Process $RoleOSBaseUrl
exit 0
