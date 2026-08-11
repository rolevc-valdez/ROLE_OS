<#
.SYNOPSIS
    Shared helpers for Start-RoleOS.ps1 and Stop-RoleOS.ps1.

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

        If the environment variable ROLE_OS_WORKSPACE_DIR is set, its
        \00_SYSTEM subfolder is used as the source for all five databases
        instead of the bundled samples\role_os_sample\00_SYSTEM\ fixture --
        this is the opt-in switch to a real, permanent workspace (e.g. one
        already produced by builder\builder.py) without ever silently
        moving or copying data. Setting it is entirely the user's choice;
        this function only reads it.
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
        $systemDir = Join-Path $RepoRoot "samples\role_os_sample\00_SYSTEM"
        $source = "bundled sample workspace (default; see INSTALLATION.md for how to point at your own data)"
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
