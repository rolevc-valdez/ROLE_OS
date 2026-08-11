<#
.SYNOPSIS
    Creates a "ROLE OS" Desktop shortcut that launches Start ROLE OS.bat.

.DESCRIPTION
    Run once, from anywhere:
        powershell -ExecutionPolicy Bypass -File "CREATE_DESKTOP_SHORTCUT.ps1"

    (If double-clicking or "Run with PowerShell" is blocked by your
    system's execution policy, use the command above from a terminal --
    no change to any system-wide policy is required; -ExecutionPolicy
    Bypass only applies to this one process.)

    Does not require Administrator privileges: writing a .lnk file to the
    current user's own Desktop and reading it back via WScript.Shell are
    both standard-user operations.
#>

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repoRoot = $PSScriptRoot
$targetBat = Join-Path $repoRoot "Start ROLE OS.bat"

if (-not (Test-Path -LiteralPath $targetBat -PathType Leaf)) {
    Write-Host "Could not find '$targetBat'." -ForegroundColor Red
    Write-Host "Run this script from inside the ROLE_OS repository root (where 'Start ROLE OS.bat' lives)." -ForegroundColor Red
    exit 1
}

$wshShell = New-Object -ComObject WScript.Shell
$desktopPath = $wshShell.SpecialFolders("Desktop")
$shortcutPath = Join-Path $desktopPath "ROLE OS.lnk"

$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetBat
$shortcut.WorkingDirectory = $repoRoot
$shortcut.Description = "Start ROLE OS (opens http://127.0.0.1:8000)"
$shortcut.WindowStyle = 7  # Minimized, so the console window doesn't steal focus

# Use an existing project icon if one exists; otherwise fall back to a
# standard Windows application icon; if even that fails for any reason,
# fall back to the .bat file's own (always-valid) icon.
$projectIcon = Get-ChildItem -Path $repoRoot -Filter "*.ico" -File -ErrorAction SilentlyContinue | Select-Object -First 1
if ($projectIcon) {
    $shortcut.IconLocation = $projectIcon.FullName
    $iconSource = "project icon: $($projectIcon.FullName)"
} else {
    try {
        $shell32 = Join-Path $env:SystemRoot "System32\shell32.dll"
        if (Test-Path -LiteralPath $shell32) {
            $shortcut.IconLocation = "$shell32,220"
            $iconSource = "standard Windows icon (shell32.dll)"
        } else {
            $shortcut.IconLocation = $targetBat
            $iconSource = "batch file's default icon"
        }
    } catch {
        $shortcut.IconLocation = $targetBat
        $iconSource = "batch file's default icon"
    }
}

$shortcut.Save()

Write-Host "Desktop shortcut created:" -ForegroundColor Green
Write-Host "  $shortcutPath"
Write-Host "  Target:      $targetBat"
Write-Host "  Start in:    $repoRoot"
Write-Host "  Icon:        $iconSource"
Write-Host ""
Write-Host "Double-click 'ROLE OS' on your Desktop to start ROLE OS."
