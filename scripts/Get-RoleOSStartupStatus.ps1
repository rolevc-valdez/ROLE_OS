<#
.SYNOPSIS
    Shows whether ROLE OS starts at Windows sign-in for the CURRENT USER,
    and whether ROLE OS is running right now.

      powershell -ExecutionPolicy Bypass -File scripts\Get-RoleOSStartupStatus.ps1
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

$status = Get-RoleOSStartupStatus -RepoRoot $paths.RepoRoot
Show-Status $status

$health = Test-RoleOSHealth
if ($health.Responding -and $health.IsRoleOS) {
    Write-Host "ROLE OS server: RUNNING at $RoleOSBaseUrl (version $($health.Version))" -ForegroundColor Green
} elseif ($health.Responding) {
    Write-Host "ROLE OS server: port $RoleOSPort is used by a different application" -ForegroundColor Red
} else {
    Write-Host "ROLE OS server: NOT RUNNING"
}
Write-Host "Launcher log: $($paths.LauncherLog)"
exit 0
