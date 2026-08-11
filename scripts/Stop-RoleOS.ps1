<#
.SYNOPSIS
    Stops the ROLE OS server started by Start-RoleOS.ps1 -- and only that
    process.

.DESCRIPTION
    Uses the repository-specific PID file (dashboard\var\role_os_dashboard\
    role_os.pid) as the sole source of truth for which process to stop.
    Before killing anything, it confirms the PID is still alive AND that
    its command line actually looks like our uvicorn invocation --
    protecting against an unrelated process that happens to have reused
    the same PID after a reboot. It never searches for or kills Python/
    uvicorn processes by name alone.

    Intended to be run via "Stop ROLE OS.bat", but works standalone:
      powershell -ExecutionPolicy Bypass -File scripts\Stop-RoleOS.ps1
#>

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "RoleOS.Common.ps1")

$paths = Get-RoleOSPaths

# Guard against silently recreating an empty "dashboard" stub via
# New-Item's intermediate-directory creation if the folder is missing or
# the repository was moved/corrupted -- same reasoning as Start-RoleOS.ps1.
if (-not (Test-Path -LiteralPath $paths.DashboardDir -PathType Container)) {
    Write-Host "[INFO] Dashboard folder not found at '$($paths.DashboardDir)'; ROLE OS cannot be running from a missing repository." -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Path $paths.VarDir -Force | Out-Null

Write-RoleOSLog -LogFile $paths.LauncherLog -Message "---- Stop ROLE OS ----"

if (-not (Test-Path -LiteralPath $paths.PidFile -PathType Leaf)) {
    Write-RoleOSLog -LogFile $paths.LauncherLog -Message "ROLE OS does not appear to be running (no PID file at '$($paths.PidFile)')."
    exit 0
}

$rawPid = (Get-Content -LiteralPath $paths.PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
$targetPid = 0
if (-not [int]::TryParse($rawPid, [ref]$targetPid) -or $targetPid -le 0) {
    Write-RoleOSLog -Level WARN -LogFile $paths.LauncherLog -Message "PID file is unreadable or invalid ('$rawPid'). Removing it."
    Remove-Item -LiteralPath $paths.PidFile -Force -ErrorAction SilentlyContinue
    Write-RoleOSLog -LogFile $paths.LauncherLog -Message "ROLE OS does not appear to be running."
    exit 0
}

$proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue
if (-not $proc) {
    Write-RoleOSLog -LogFile $paths.LauncherLog -Message "PID $targetPid from the PID file is no longer running. Removing the stale PID file."
    Remove-Item -LiteralPath $paths.PidFile -Force -ErrorAction SilentlyContinue
    Write-RoleOSLog -LogFile $paths.LauncherLog -Message "ROLE OS is not running."
    exit 0
}

# Confirm this PID is genuinely our uvicorn process before touching it --
# never kill a process just because a PID file says so.
$commandLine = $null
try {
    $wmiProc = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction Stop
    $commandLine = $wmiProc.CommandLine
} catch {
    $commandLine = $null
}

$looksLikeOurs = $commandLine -and ($commandLine -match "uvicorn") -and ($commandLine -match [regex]::Escape("app.main:app"))

if (-not $looksLikeOurs) {
    Write-RoleOSLog -Level WARN -LogFile $paths.LauncherLog -Message "PID $targetPid is running, but its command line doesn't look like ROLE OS's uvicorn process (command line: '$commandLine'). Not stopping it -- removing the stale/mismatched PID file instead."
    Remove-Item -LiteralPath $paths.PidFile -Force -ErrorAction SilentlyContinue
    Write-RoleOSLog -LogFile $paths.LauncherLog -Message "ROLE OS does not appear to be running under a PID this launcher recognizes."
    exit 0
}

Write-RoleOSLog -LogFile $paths.LauncherLog -Message "Stopping ROLE OS (PID $targetPid)..."
Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue

$stopped = $false
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Milliseconds 300
    if (-not (Get-Process -Id $targetPid -ErrorAction SilentlyContinue)) {
        $stopped = $true
        break
    }
}

Remove-Item -LiteralPath $paths.PidFile -Force -ErrorAction SilentlyContinue

if ($stopped) {
    Write-RoleOSLog -LogFile $paths.LauncherLog -Message "ROLE OS stopped."
    exit 0
} else {
    Write-RoleOSLog -Level ERROR -LogFile $paths.LauncherLog -Message "Sent a stop signal to PID $targetPid but it did not exit within 3 seconds. It may still be shutting down; check Task Manager if it persists."
    exit 1
}
