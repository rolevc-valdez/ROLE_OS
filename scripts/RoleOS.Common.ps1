<#
.SYNOPSIS
    Shared helpers for Start-RoleOS.ps1, Stop-RoleOS.ps1 and the sign-in
    startup scripts (Enable-/Disable-RoleOSStartup.ps1,
    Get-RoleOSStartupStatus.ps1).

.DESCRIPTION
    Single source of truth for: resolving repository-relative paths, the
    local runtime directory, the health-check probe, and simple logging.
    Dot-sourced by both launcher scripts so path/health-check logic is
    never duplicated (ARCHITECTURE_PRINCIPLES.md, Single Source of Truth).

    All paths are resolved from this file's own location ($PSScriptRoot),
    never hardcoded, so the launcher works regardless of where the
    ROLE_OS repository is cloned -- including a path containing spaces
    and parentheses, e.g.
    "C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS\ROLE_OS".
#>

$RoleOSHost = "127.0.0.1"
$RoleOSPort = 8000
$RoleOSBaseUrl = "http://${RoleOSHost}:${RoleOSPort}"
$RoleOSHealthUrl = "$RoleOSBaseUrl/health"

function Get-RoleOSPaths {
    <#
    .SYNOPSIS
        Resolves every path the launcher needs, relative to this file's
        own location -- scripts\RoleOS.Common.ps1 lives in
        <repo-root>\scripts\, so the repo root is always one level up.
    #>
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $dashboardDir = Join-Path $repoRoot "dashboard"
    # Co-located with the app's own default session database
    # (dashboard\app\config.py's session_db_path defaults to
    # var\role_os_dashboard\... resolved against the working directory
    # uvicorn is started from, which the launcher always sets to
    # $dashboardDir) -- one runtime directory, not two.
    $varDir = Join-Path $dashboardDir "var\role_os_dashboard"

    [PSCustomObject]@{
        RepoRoot      = $repoRoot
        DashboardDir  = $dashboardDir
        VarDir        = $varDir
        PidFile       = Join-Path $varDir "role_os.pid"
        LauncherLog   = Join-Path $varDir "launcher.log"
        UvicornLog    = Join-Path $varDir "uvicorn.out.log"
        UvicornErrLog = Join-Path $varDir "uvicorn.err.log"
    }
}

function Resolve-RoleOSDatabaseEnv {
    <#
    .SYNOPSIS
        Resolves and sets the five ROLE_OS_*_DB_PATH environment variables
        as absolute paths derived from the repository root, for the child
        uvicorn process to inherit.

    .DESCRIPTION
        dashboard\app\config.py defaults every one of these to a path
        *relative to the process's current working directory* (e.g.
        "samples/role_os_sample/00_SYSTEM/role_os.db"). The launcher starts
        uvicorn with dashboard\ as its working directory (per
        Start-RoleOS.ps1's "change safely into the dashboard directory"
        behavior), so those relative defaults would resolve to
        dashboard\samples\...\role_os.db -- which does not exist -- instead
        of the real, repo-root-relative samples\...\role_os.db. This
        function sets each variable explicitly, as an absolute path
        anchored to the repository root, so the resolution is correct
        regardless of the process's working directory.

        An explicit value the user already set in their own environment
        (e.g. from a terminal, before double-clicking the launcher, or via
        ROLE_OS_WORKSPACE_DIR below) is never overwritten -- this function
        only fills in what isn't already set.

        Role OS 2.0 Phase 1 Task 2B: normal startup's own default (no
        ROLE_OS_WORKSPACE_DIR, no explicit ROLE_OS_*_DB_PATH) resolves into
        the repository's canonical runtime data root, <RepoRoot>\var\role_os
        -- the same default dashboard\app\config.py itself uses (Task 2).
        This supersedes the earlier decision documented in
        docs\product\DECISIONS.md ("ROLE_OS_WORKSPACE_DIR is an opt-in
        launcher switch, not automatic workspace detection"), which
        defaulted normal startup into the bundled samples\role_os_sample\
        fixture; see the newer DECISIONS.md entry for why. The bundled
        sample data remains fully available, but only via the same explicit
        ROLE_OS_WORKSPACE_DIR switch as any other real workspace (e.g. set
        it to the repo's own samples\role_os_sample folder) -- never as an
        implicit default.

        If the environment variable ROLE_OS_WORKSPACE_DIR is set, its
        \00_SYSTEM subfolder is used as the source for all five databases
        instead -- this is the opt-in switch to any workspace folder (a
        real one already produced by builder\builder.py, or the bundled
        samples\role_os_sample fixture for a deliberate demo run) without
        ever silently moving or copying data. Setting it is entirely the
        user's choice; this function only reads it.
    #>
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$LogFile
    )

    $workspaceOverride = $env:ROLE_OS_WORKSPACE_DIR
    if ($workspaceOverride) {
        $systemDir = Join-Path $workspaceOverride "00_SYSTEM"
        $source = "user-configured workspace (ROLE_OS_WORKSPACE_DIR=$workspaceOverride)"
    } else {
        $systemDir = Join-Path $RepoRoot "var\role_os"
        $source = "canonical runtime data root (default; var\role_os -- same as dashboard\app\config.py's own default; set ROLE_OS_WORKSPACE_DIR to explicitly use the bundled samples\role_os_sample demo data or a real workspace instead, see INSTALLATION.md)"
    }

    $dbVars = [ordered]@{
        ROLE_OS_DB_PATH            = "role_os.db"
        ROLE_OS_PROJECTS_DB_PATH   = "role_os_projects.db"
        ROLE_OS_ADVISOR_DB_PATH    = "role_os_advisor.db"
        ROLE_OS_IMPORTS_DB_PATH    = "role_os_imports.db"
        ROLE_OS_EXTRACTION_DB_PATH = "role_os_extraction.db"
    }

    Write-RoleOSLog -LogFile $LogFile -Message "Database source: $source"

    $resolved = [ordered]@{}
    foreach ($varName in $dbVars.Keys) {
        $existing = [Environment]::GetEnvironmentVariable($varName, "Process")
        if ($existing) {
            Write-RoleOSLog -LogFile $LogFile -Message "$varName already set in the environment ('$existing') -- leaving it as-is."
            $resolved[$varName] = $existing
            continue
        }
        $absolutePath = Join-Path $systemDir $dbVars[$varName]
        [Environment]::SetEnvironmentVariable($varName, $absolutePath, "Process")
        Write-RoleOSLog -LogFile $LogFile -Message "$varName = $absolutePath"
        $resolved[$varName] = $absolutePath
    }

    [PSCustomObject]$resolved
}

function Write-RoleOSLog {
    <#
    .SYNOPSIS
        Writes a UTF-8 timestamped line to both the console and
        launcher.log. Never throws -- a logging failure must not abort
        the launcher itself.
    #>
    param(
        [Parameter(Mandatory)][string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")][string]$Level = "INFO",
        [Parameter(Mandatory)][string]$LogFile
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"

    switch ($Level) {
        "ERROR" { Write-Host $line -ForegroundColor Red }
        "WARN"  { Write-Host $line -ForegroundColor Yellow }
        default { Write-Host $line }
    }

    try {
        $logDir = Split-Path -Parent $LogFile
        if (-not (Test-Path -LiteralPath $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
    } catch {
        # Logging to disk is best-effort; console output above already happened.
    }
}

function Test-RoleOSHealth {
    <#
    .SYNOPSIS
        Probes the health endpoint and distinguishes three states:
        ROLE OS is up, something else is on the port, or nothing is
        listening. This is what lets the launcher tell "already running"
        apart from "port 8000 occupied by another application" instead
        of guessing from a bare TCP connect.
    .OUTPUTS
        PSCustomObject with: Responding (bool), IsRoleOS (bool),
        StatusCode, Version, Body, Error.
    #>
    param([int]$TimeoutSec = 2)

    try {
        $response = Invoke-WebRequest -Uri $RoleOSHealthUrl -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
        $isRoleOS = $false
        $version = $null
        try {
            $json = $response.Content | ConvertFrom-Json -ErrorAction Stop
            if ($json.app -eq "ROLE OS") {
                $isRoleOS = $true
                $version = $json.version
            }
        } catch {
            # Non-JSON or unexpected shape -- something else is answering on this port.
        }
        return [PSCustomObject]@{
            Responding = $true
            IsRoleOS   = $isRoleOS
            StatusCode = [int]$response.StatusCode
            Version    = $version
            Body       = $response.Content
            Error      = $null
        }
    } catch {
        return [PSCustomObject]@{
            Responding = $false
            IsRoleOS   = $false
            StatusCode = $null
            Version    = $null
            Body       = $null
            Error      = $_.Exception.Message
        }
    }
}

function Find-RoleOSPython {
    <#
    .SYNOPSIS
        Resolves the Python executable to use, per the launcher's
        documented priority order. Returns $null if nothing usable was
        found -- callers are responsible for the "missing Python" error
        message.
    .OUTPUTS
        PSCustomObject with: Path, Source (description of where it came
        from, for logging), or $null.
    #>
    param(
        [Parameter(Mandatory)][string]$DashboardDir,
        [Parameter(Mandatory)][string]$RepoRoot,
        [Parameter(Mandatory)][string]$LogFile
    )

    $venvCandidates = @(
        @{ Path = Join-Path $DashboardDir ".venv\Scripts\python.exe"; Label = "dashboard\.venv" },
        @{ Path = Join-Path $RepoRoot ".venv\Scripts\python.exe"; Label = "repository-root\.venv" },
        @{ Path = Join-Path $DashboardDir "venv\Scripts\python.exe"; Label = "dashboard\venv" },
        @{ Path = Join-Path $RepoRoot "venv\Scripts\python.exe"; Label = "repository-root\venv" }
    )

    foreach ($candidate in $venvCandidates) {
        $venvRoot = Split-Path -Parent (Split-Path -Parent $candidate.Path)
        if (Test-Path -LiteralPath $venvRoot) {
            if (Test-Path -LiteralPath $candidate.Path -PathType Leaf) {
                Write-RoleOSLog -LogFile $LogFile -Message "Using virtual environment: $($candidate.Label) ($($candidate.Path))"
                return [PSCustomObject]@{ Path = $candidate.Path; Source = $candidate.Label }
            } else {
                Write-RoleOSLog -Level WARN -LogFile $LogFile -Message "Found $($candidate.Label) but it has no Scripts\python.exe -- treating as an invalid virtual environment and skipping it."
            }
        }
    }

    foreach ($launcher in @("py", "python", "python3")) {
        $cmd = Get-Command $launcher -ErrorAction SilentlyContinue
        if ($cmd) {
            Write-RoleOSLog -LogFile $LogFile -Message "No local virtual environment found; using '$launcher' on PATH ($($cmd.Source))"
            return [PSCustomObject]@{ Path = $cmd.Source; Source = "PATH ($launcher)" }
        }
    }

    return $null
}

function Get-RoleOSRequiredImports {
    <#
    .SYNOPSIS
        Parses dashboard\requirements.txt -- the single source of truth
        for the dashboard's runtime dependencies -- into a package-name
        -> import-name map, so the launcher's dependency check never
        drifts from what's actually declared there (the bug this function
        exists to prevent: a package added to requirements.txt in a later
        sprint but never added to a separately hand-maintained check
        list).

    .OUTPUTS
        An ordered hashtable: PyPI package name (as written in the file)
        -> the module name Python actually imports it as.
    #>
    param([Parameter(Mandatory)][string]$RequirementsPath)

    # Only where simple normalization (lowercase, hyphens -> underscores)
    # does not match the real importable module name. Everything else
    # (fastapi, uvicorn, pydantic, jinja2, python-multipart -> python_multipart)
    # normalizes correctly without an entry here.
    $importNameOverrides = @{ "pillow" = "PIL" }

    $imports = [ordered]@{}
    if (-not (Test-Path -LiteralPath $RequirementsPath -PathType Leaf)) {
        return $imports
    }

    Get-Content -LiteralPath $RequirementsPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or $line.StartsWith("-r") -or $line.StartsWith("-")) {
            return
        }
        if ($line -match '^([A-Za-z0-9_.\-]+)') {
            $pkgName = $Matches[1]
            $key = $pkgName.ToLowerInvariant()
            if ($importNameOverrides.ContainsKey($key)) {
                $importName = $importNameOverrides[$key]
            } else {
                $importName = $key.Replace('-', '_')
            }
            if (-not $imports.Contains($pkgName)) {
                $imports[$pkgName] = $importName
            }
        }
    }
    return $imports
}

function Test-RoleOSDependencies {
    <#
    .SYNOPSIS
        Verifies the interpreter can import every package declared in
        dashboard\requirements.txt -- never a second, hand-maintained
        list here that can drift from what the project actually requires
        (the exact bug that let Sprint C4's Pillow dependency go
        unverified: this check used to hardcode "fastapi, uvicorn,
        pydantic, jinja2" and was simply never updated when Pillow was
        added). Checks each package individually (never a single combined
        `import a, b, c`, which only ever reports the *first* missing
        package and hides the rest) so every missing package is named.

    .OUTPUTS
        Hashtable: @{ Success = <bool>; Missing = <string[]> } -- Missing
        holds the PyPI package name(s) (not the Python import name), ready
        to show the user. Never throws -- a missing package's stderr
        traceback is expected output here, not a launcher error, so it
        must not surface as a PowerShell NativeCommandError even when
        $ErrorActionPreference is Stop.
    #>
    param(
        [Parameter(Mandatory)][string]$PythonPath,
        [Parameter(Mandatory)][string]$RequirementsPath
    )

    $requiredImports = Get-RoleOSRequiredImports -RequirementsPath $RequirementsPath
    if ($requiredImports.Count -eq 0) {
        return @{ Success = $true; Missing = @() }
    }

    # Built with single-quoted Python string literals, never double
    # quotes: PowerShell's argument reconstruction for native executables
    # (the `&` call operator) can silently drop embedded double quotes
    # from a multi-line string argument, turning `"fastapi"` into the
    # bareword `fastapi` and breaking the script with a NameError --
    # single quotes survive the same round-trip intact. Every import name
    # here is already a plain identifier (from `.Replace('-', '_')` or a
    # fixed override), so it can never itself contain a quote character.
    $importNamesLiteral = ($requiredImports.Values | ForEach-Object { "'$_'" }) -join ','
    $checkScript = @"
import importlib.util, sys
names = [$importNamesLiteral]
missing = [n for n in names if importlib.util.find_spec(n) is None]
for n in missing:
    print(n)
sys.exit(1 if missing else 0)
"@

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        $output = & $PythonPath -c $checkScript 2>&1
    } finally {
        $ErrorActionPreference = $previousPreference
    }

    if ($LASTEXITCODE -eq 0) {
        return @{ Success = $true; Missing = @() }
    }

    $missingImportNames = @($output | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ })
    $missingPackages = @()
    foreach ($pkgName in $requiredImports.Keys) {
        if ($missingImportNames -contains $requiredImports[$pkgName]) {
            $missingPackages += $pkgName
        }
    }
    if ($missingPackages.Count -eq 0) {
        # find_spec() itself couldn't run (e.g. a broken interpreter) --
        # surface the raw output rather than silently reporting success.
        $missingPackages = @("(unable to verify -- interpreter output: $($missingImportNames -join ' '))")
    }
    return @{ Success = $false; Missing = $missingPackages }
}

# ---------------------------------------------------------------------
# Role OS 2.0 Phase 3 Task 7: readiness, launch-time freshness, and
# Windows sign-in startup (current user only). The startup mechanism is a
# single shortcut in the current user's Startup folder that runs the SAME
# canonical launcher (Start-RoleOS.ps1) in -Startup mode -- no service, no
# scheduled task, no registry edits, no administrator rights.
# ---------------------------------------------------------------------

$RoleOSStartupShortcutName = "ROLE OS.lnk"

function Wait-RoleOSHealthy {
    <#
    .SYNOPSIS
        Polls the real /health endpoint until ROLE OS answers, the given
        process exits, or the timeout elapses. Returns the last health
        probe when healthy, $null otherwise -- never loops forever.
    #>
    param(
        [int]$TimeoutSeconds = 30,
        [int]$IntervalMs = 500,
        [System.Diagnostics.Process]$Process = $null
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process -and $Process.HasExited) {
            return $null
        }
        $check = Test-RoleOSHealth -TimeoutSec 1
        if ($check.Responding -and $check.IsRoleOS) {
            return $check
        }
        Start-Sleep -Milliseconds $IntervalMs
    }
    return $null
}

function Invoke-RoleOSFreshnessCheck {
    <#
    .SYNOPSIS
        Asks the running server to rescan the Workspace only if the last
        scan is older than 24 hours (POST /workspace/rescan-if-stale). The
        server uses its configured Discovery roots only and never adopts
        anything. Called AFTER the browser is opened, so the Daily Command
        Center never waits for a scan. Never throws -- a failed or slow
        refresh is logged, not fatal.
    #>
    param(
        [Parameter(Mandatory)][string]$LogFile,
        [int]$TimeoutSec = 600
    )
    try {
        $result = Invoke-RestMethod -Method Post -Uri "$RoleOSBaseUrl/workspace/rescan-if-stale" -TimeoutSec $TimeoutSec -ErrorAction Stop
        if ($result.rescanned) {
            Write-RoleOSLog -LogFile $LogFile -Message "Workspace scan was stale ($($result.reason)); rescanned the configured Discovery roots. Last scan now: $($result.freshness.last_scan)"
        } elseif ($result.error) {
            Write-RoleOSLog -Level WARN -LogFile $LogFile -Message "Workspace scan is stale but the rescan failed: $($result.error)"
        } else {
            Write-RoleOSLog -LogFile $LogFile -Message "Workspace scan is fresh ($($result.freshness.hours_since_scan) h old); no rescan needed."
        }
        return $result
    } catch {
        Write-RoleOSLog -Level WARN -LogFile $LogFile -Message "Workspace freshness check did not complete: $($_.Exception.Message)"
        return $null
    }
}

function Get-RoleOSStartupFolder {
    <#
    .SYNOPSIS
        The CURRENT USER's Startup folder (shell:startup). Never the
        machine-wide "All Users" folder.
    #>
    return [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
}

function Get-RoleOSStartupShortcutPath {
    param([string]$StartupFolder = (Get-RoleOSStartupFolder))
    return Join-Path $StartupFolder $RoleOSStartupShortcutName
}

function Get-RoleOSStartupCommand {
    <#
    .SYNOPSIS
        The exact command the sign-in shortcut runs: the canonical launcher
        in -Startup mode, hidden console, no profile.
    #>
    param([Parameter(Mandatory)][string]$RepoRoot)
    $launcher = Join-Path $RepoRoot "scripts\Start-RoleOS.ps1"
    $powershell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    [PSCustomObject]@{
        FilePath  = $powershell
        Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`" -Startup"
        Launcher  = $launcher
    }
}

function Get-RoleOSStartupStatus {
    <#
    .SYNOPSIS
        Reports whether sign-in startup is enabled, and whether the
        shortcut still points at THIS repository's canonical launcher.
    .OUTPUTS
        PSCustomObject: Enabled, ShortcutPath, Target, Arguments,
        PointsToThisRepo, Launcher.
    #>
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [string]$StartupFolder = (Get-RoleOSStartupFolder)
    )
    $shortcutPath = Get-RoleOSStartupShortcutPath -StartupFolder $StartupFolder
    $expected = Get-RoleOSStartupCommand -RepoRoot $RepoRoot
    if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) {
        return [PSCustomObject]@{
            Enabled = $false; ShortcutPath = $shortcutPath; Target = $null; Arguments = $null
            PointsToThisRepo = $false; Launcher = $expected.Launcher
        }
    }
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcutPath)
    [PSCustomObject]@{
        Enabled          = $true
        ShortcutPath     = $shortcutPath
        Target           = $link.TargetPath
        Arguments        = $link.Arguments
        PointsToThisRepo = ($link.Arguments -eq $expected.Arguments)
        Launcher         = $expected.Launcher
    }
}

function Enable-RoleOSStartup {
    <#
    .SYNOPSIS
        Creates (or refreshes) the current user's Startup-folder shortcut.
        Idempotent: running it again just rewrites the same single shortcut.
    #>
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [string]$StartupFolder = (Get-RoleOSStartupFolder)
    )
    $command = Get-RoleOSStartupCommand -RepoRoot $RepoRoot
    if (-not (Test-Path -LiteralPath $command.Launcher -PathType Leaf)) {
        throw "Canonical launcher not found at '$($command.Launcher)'."
    }
    if (-not (Test-Path -LiteralPath $StartupFolder -PathType Container)) {
        New-Item -ItemType Directory -Path $StartupFolder -Force | Out-Null
    }
    $shortcutPath = Get-RoleOSStartupShortcutPath -StartupFolder $StartupFolder
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcutPath)
    $link.TargetPath = $command.FilePath
    $link.Arguments = $command.Arguments
    $link.WorkingDirectory = $RepoRoot
    $link.WindowStyle = 7  # minimized
    $link.Description = "Start ROLE OS at Windows sign-in and open the Daily Command Center"
    $link.Save()
    return Get-RoleOSStartupStatus -RepoRoot $RepoRoot -StartupFolder $StartupFolder
}

function Disable-RoleOSStartup {
    <#
    .SYNOPSIS
        Removes ONLY the Role OS Startup-folder shortcut. Never touches the
        running server, the repository, or anything else in the folder.
    #>
    param(
        [Parameter(Mandatory)][string]$RepoRoot,
        [string]$StartupFolder = (Get-RoleOSStartupFolder)
    )
    $shortcutPath = Get-RoleOSStartupShortcutPath -StartupFolder $StartupFolder
    if (Test-Path -LiteralPath $shortcutPath -PathType Leaf) {
        Remove-Item -LiteralPath $shortcutPath -Force
    }
    return Get-RoleOSStartupStatus -RepoRoot $RepoRoot -StartupFolder $StartupFolder
}

function Show-RoleOSStartupError {
    <#
    .SYNOPSIS
        In -Startup mode there is no console to read, so a failure is shown
        once as a Windows message box pointing at the log. Best-effort.
    #>
    param(
        [Parameter(Mandatory)][string]$Message,
        [Parameter(Mandatory)][string]$LogFile
    )
    try {
        $shell = New-Object -ComObject WScript.Shell
        $text = "ROLE OS could not start at sign-in.`n`n$Message`n`nLog: $LogFile`n`nYou can start it manually with 'Start ROLE OS.bat'."
        $null = $shell.Popup($text, 0, "ROLE OS", 0x10)
    } catch {
        # No desktop session (e.g. automated run) -- the log already has it.
    }
}
