<#
.SYNOPSIS
    Disables ROLE OS at Windows sign-in for the CURRENT USER.

.DESCRIPTION
    Removes only the "ROLE OS.lnk" shortcut from the current user's Startup
    folder. Does not stop a running server and does not touch the
    repository or any data -- "Start ROLE OS.bat" keeps working as before.

      powershell -ExecutionPolicy Bypass -File scripts\Disable-RoleOSStartup.ps1
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

$status = Disable-RoleOSStartup -RepoRoot $paths.RepoRoot
Show-Status $status
exit 0
