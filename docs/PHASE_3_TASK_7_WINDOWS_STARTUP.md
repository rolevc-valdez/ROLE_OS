# Role OS 2.0 — P3.7 Windows Startup & Daily Launch

**Status: COMPLETE (2026-09-28).** When Role signs into Windows, Role OS starts (or is found already running) and opens the Daily Command Center. Simple, current-user only, reversible, observable. No Windows service, no scheduled task, no registry edits, no administrator rights, no tray app.

**Baseline:** `c613f69` (P3.6 complete), `main == origin/main`. Role's earlier untracked helper file (`Prompt add to workspace en Role OS.txt`) was no longer in the repository at start.

## Existing launch path (inspected first, reused)

| Aspect | Existing behavior (unchanged unless noted) |
|---|---|
| Launcher | `Start ROLE OS.bat` → `scripts/Start-RoleOS.ps1`; shared helpers in `scripts/RoleOS.Common.ps1`; `Stop ROLE OS.bat` → `scripts/Stop-RoleOS.ps1`; optional `CREATE_DESKTOP_SHORTCUT.ps1` |
| Server | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`, working dir `dashboard\`, repo `.venv` preferred; separate process that outlives the launcher |
| Health / already running | `GET /health` → `{"app": "ROLE OS", ...}`; `Test-RoleOSHealth` distinguishes ROLE OS / another app on the port / nothing — real application readiness, not a process name. Already healthy → open browser, **no second server**. Port held by another app → refuse with a clear error |
| Readiness | polls `/health` (was a 30 s inline loop), stops the server and fails clearly on timeout or early exit |
| Browser | `Start-Process http://127.0.0.1:8000` → the user's **default browser**, route `/` → Daily Command Center (`#/home`) |
| Shutdown | `Stop-RoleOS.ps1` stops only the PID in `role_os.pid` after verifying its command line |
| Runtime paths | DB env vars resolved by `Resolve-RoleOSDatabaseEnv` (from `ROLE_OS_WORKSPACE_DIR` when set) |
| Logs | `dashboard\var\role_os_dashboard\launcher.log`, `uvicorn.out.log`, `uvicorn.err.log`; PID file `role_os.pid` there too |

## Startup mechanism — Startup-folder shortcut (why)

One shortcut, `ROLE OS.lnk`, in the **current user's** Startup folder (`shell:startup` = `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`). It runs:

```
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "<repo>\scripts\Start-RoleOS.ps1" -Startup
```

Why: it is the simplest supported per-user mechanism, needs no admin rights, is visible and removable in Explorer / Task Manager → Startup apps, and the launcher already makes the start idempotent and readiness-based. A Scheduled Task would add a second mechanism without a real reliability gain here: the only benefit (a delay after sign-in) is covered by the launcher polling `/health` for up to 90 s in startup mode instead of sleeping.

## `-Startup` mode (same canonical launcher, same single server)

- The server runs with **no visible window** (manual launch keeps its minimized console, unchanged).
- Readiness timeout **90 s** (manual: 30 s) — the machine is busy right after sign-in. No fixed sleep; `/health` is polled every 0.5 s and the wait also ends immediately if the server process exits.
- On failure: logged as before **and** shown once as a Windows message box with the error and the log path (there is no console to read). Quiet when successful, diagnosable when not.

## Idempotent start / already running

Every launch — manual, Startup shortcut, run twice — first probes `/health`:
- ROLE OS healthy → open the Daily Command Center, **no second server**, freshness check, exit.
- Nothing listening → start the one server, wait for `/health`, open the Daily Command Center, freshness check, exit.
- Port used by another app → fail clearly (popup in startup mode).

## Browser

Destination: **`http://127.0.0.1:8000`** (`/` → Daily Command Center). Never `#/dashboard` (Role Dashboard stays one click away inside the Command Center). Opened with the default browser (`Start-Process <url>`), not a hard-coded Chrome. One tab per launch; the sign-in shortcut runs once per sign-in, so a sign-in opens one tab. Server restarts do not open tabs — only launcher runs do. An existing tab cannot be focused from outside the browser, so a *manual* re-launch opens another tab (existing behavior).

## Workspace freshness at launch

New endpoint `POST /workspace/rescan-if-stale` (service `rescan_if_stale`): if the last scan is missing or older than **24 h** it runs the existing `rescan()` with `root=None` — the configured Discovery root(s) only — otherwise it does nothing. Always 200; a scan failure is reported (`rescanned: false`, `error`), never raised.

The launcher calls it **after** opening the browser (`Invoke-RoleOSFreshnessCheck`), so the Command Center is never blocked by a scan. Limitation (documented, no new background architecture): a page opened before the scan finishes still shows the stale banner until refreshed; in a *manual* launch the console window stays open until the scan returns (≈ 15 s here). The call's timeout is 10 minutes and its outcome is logged.

**Discovery safety:** no roots added or changed, `ROLE_OS_DISCOVERY_ROOTS` never set, `C:\Users\rolev` never scanned, no browser/Claude/ChatGPT access, nothing adopted; explicit registrations and external managed work are untouched by `rescan()` by design (tested).

## Startup controls

```
powershell -ExecutionPolicy Bypass -File scripts\Enable-RoleOSStartup.ps1      # create/refresh the shortcut (idempotent)
powershell -ExecutionPolicy Bypass -File scripts\Disable-RoleOSStartup.ps1     # remove only that shortcut
powershell -ExecutionPolicy Bypass -File scripts\Get-RoleOSStartupStatus.ps1   # ENABLED/DISABLED + whether ROLE OS is running
```

Status also warns if the shortcut points at a different repository location (e.g. after moving the repo — re-run Enable). Disable never stops a running server. Functions live in `RoleOS.Common.ps1` (`Enable-RoleOSStartup`, `Disable-RoleOSStartup`, `Get-RoleOSStartupStatus`, `Get-RoleOSStartupFolder`, `Get-RoleOSStartupCommand`, `Wait-RoleOSHealthy`, `Invoke-RoleOSFreshnessCheck`, `Show-RoleOSStartupError`).

## Troubleshooting

1. `Get-RoleOSStartupStatus.ps1` — is startup enabled, does it point at this repo, is the server running?
2. `dashboard\var\role_os_dashboard\launcher.log` — every launch is logged; sign-in launches are marked "(Windows sign-in startup)".
3. `uvicorn.err.log` — server errors (last lines are also quoted in the failure message).
4. Port 8000 busy with another app → the launcher says so; close it and run `Start ROLE OS.bat`.
5. Run `Start ROLE OS.bat` manually to see the same launch with a console.

## Automated tests (not proof of a real sign-in)

`dashboard/tests/test_windows_startup.py` — **13 tests**: fresh scan reused (< 24 h); stale scan (> 24 h) refreshed with roots unchanged, adoption/classification preserved, new folder discovered but not adopted, explicit registration and external tool preserved; never-scanned → scanned; rescan failure reported not raised; endpoint (then fresh on second call); all launcher scripts parse (real PowerShell parser); `Test-RoleOSHealth` distinguishes ROLE OS / other app / nothing (stub HTTP servers); `Wait-RoleOSHealthy` succeeds on real health and times out boundedly; enable / status / idempotent enable / disable / disable-again in a **temporary** Startup folder via real `WScript.Shell`; default Startup folder is current-user scope (not ProgramData); destination is `/` and never `#/dashboard`; health probe precedes any server start and the freshness call follows the browser; `Start ROLE OS.bat` still manual (no `-Startup`).

Broader regression (every Workspace / Discovery / Mission Control / Daily Command Center / registration / ingestion / navigation / config / launcher / dashboard test file, 45 files): **590 passed, 0 failed**. All 15 runtime DB checksums identical before/after.

## Real Windows validation (this machine, 2026-09-28)

| Scenario | Result |
|---|---|
| A. Stopped → manual launch | server healthy in ~2 s, browser opened, then the 80 h-old scan was refreshed (16 s) after the page opened |
| B. Running → manual launch again | "already running", same PID, 1 listener on 8000, no rescan (fresh) |
| C. Enable | `ROLE OS.lnk` created in the current-user Startup folder (other startup items untouched); status ENABLED, pointing at this repo |
| Startup shortcut executed (as Explorer does) while running | "(Windows sign-in startup)", no second server |
| Startup shortcut executed while stopped | server started with **no visible window**, healthy in ~2 s, Daily Command Center opened, 1 listener |
| D. Disable | shortcut removed; running server untouched; manual launch from stopped still works (minimized console as before) |
| E. Re-enable | exactly one shortcut restored; status ENABLED — **left enabled** |
| Actual sign-out / sign-in | **Not performed** (would interrupt Role's session; not authorized). The configured shortcut was executed directly instead. Final confirmation at Role's next sign-in. |

Note: the first scenario's harness call hung only because the detached server inherited the automation's output pipe; the launcher itself had finished (log). Real launches (`.bat`, shortcut) have no such pipe; subsequent scenarios ran the launcher detached.

**Real data after all launches:** all 10 managed rows identical (bolsa-de-trabajo adopted; yt-dlp tool; KONTOOR batch completed; kontoor-fs-new-app-id tool; Desierto Creativo present), registration intact, no adoption; only `role_os_workspace.db`'s scan cache changed (2026-09-25 → 2026-09-28, still 25 folders). External DBs unchanged. Freshness now 0.2 h, not stale.

## Limitations

- Sign-in behavior verified by executing the shortcut, not by a real sign-in.
- The repository lives in Google Drive; if its files are unavailable at sign-in the launcher fails with a message box (logged).
- A manual re-launch opens another browser tab (cannot focus an existing one).
- Stale-scan refresh happens right after the page opens; refresh the page to see the new freshness.
- Fixed port 8000 (unchanged).

## Rollback

`scripts\Disable-RoleOSStartup.ps1` (or delete `ROLE OS.lnk` from `shell:startup`). Everything else is additive: the launcher without `-Startup` behaves as before plus the post-launch freshness check; the endpoint is new and only called by the launcher.
