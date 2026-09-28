<#
.SYNOPSIS
    Enables ROLE OS at Windows sign-in for the CURRENT USER.

.DESCRIPTION
    Creates one shortcut, "ROLE OS.lnk", in the current user's Startup
    folder (shell:startup). At sign-in it runs the canonical launcher,
    scripts\Start-RoleOS.ps1, in -Startup mode: if ROLE OS is already
    healthy it just opens the Daily Command Center; otherwise it starts the
    single server, waits for /health, opens the Daily Command Center, then
    refreshes a stale (> 24 h) Workspace scan.

    No administrator rights, no Windows service, no scheduled task, no
    registry edits. Idempotent. Undo with Disable-RoleOSStartup.ps1.

      powershell -ExecutionPolicy Bypass -File scripts\Enable-RoleOSStartup.ps1
#>

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

. (Join-Path $PSScriptRoot "RoleOS.Common.ps1")

$paths = Get-RoleOSPaths

function Show-Status($status) {
    if ($status.Enabled) {
        Write-Host "ROLE OS sign-in startup: ENABLED" -ForegroundColor Green
        Write-Host "  Shortcut:  $($status.ShortcutPath)"
        Write-Host "  Runs:      $($status.Target) $($status.Arguments)"
        if (-not $status.PointsToThisRepo) {
            Write-Host "  WARNING: the shortcut does not point at this repository's launcher ($($status.Launcher)). Run Enable-RoleOSStartup.ps1 to refresh it." -ForegroundColor Yellow
        }
    } else {
        Write-Host "ROLE OS sign-in startup: DISABLED" -ForegroundColor Yellow
        Write-Host "  (no shortcut at $($status.ShortcutPath))"
    }
}

$status = Enable-RoleOSStartup -RepoRoot $paths.RepoRoot
Show-Status $status
exit 0
