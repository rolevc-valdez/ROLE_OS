# Installation

## Python version

Python **3.10 or later** (`requires-python = ">=3.10"` in
[`pyproject.toml`](pyproject.toml)). The Builder (`/builder`) uses only
the standard library and has no minimum beyond this. The test suite is
run in CI/local development against Python 3.10+.

## Dependencies

Two independent dependency sets, matching the repository's two halves:

- **`builder/requirements.txt`** — empty. The Builder is standard-library
  only, by design (see [`builder/README.md`](builder/README.md)).
- **`dashboard/requirements.txt`** — the FastAPI service, and the single
  source of truth the Windows launcher's own dependency check reads from
  (see below) rather than a separately maintained list:
  - `fastapi`, `uvicorn[standard]` — the web framework and ASGI server
  - `jinja2` — server-rendered page shell (`templates/index.html`)
  - `python-multipart` — multipart file upload support (ChatGPT import,
    Settings import)
  - `pydantic` (pulled in transitively by FastAPI) — request/response models
  - `Pillow` — Assets image preview/thumbnail generation and dimension
    reading (`app/assets/image_meta.py`, `app/assets/preview.py`)
- **Root [`requirements.txt`](requirements.txt)** — aggregates
  `dashboard/requirements.txt` plus test-only dependencies (`pytest`,
  `httpx`), for running the full repo-wide test suite from one place.

## Virtual environment

A virtual environment is strongly recommended, to keep ROLE OS's
dependencies isolated from your system Python.

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (cmd.exe)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

The Alpha demo scripts (`scripts/run_alpha.sh` / `run_alpha.bat`) create
and manage their own `.venv` automatically — no manual venv setup is
needed if you're using that path.

## Requirements summary

| Requirement | Version / notes |
|---|---|
| Python | 3.10+ |
| Git | any recent version (for cloning; also used by Settings' "About" panel to report the current commit) |
| OS | Windows, macOS, or Linux — no OS-specific code paths beyond the two convenience launcher scripts (`.sh` / `.bat`) |
| External services | None. No Postgres, no Redis, no external AI/LLM API. Everything runs against local SQLite files. |

## Running the application

### Option A — one-command Alpha demo (recommended for first-time setup)

```bash
git clone https://github.com/rolevc-valdez/ROLE_OS.git
cd ROLE_OS
./scripts/run_alpha.sh        # or scripts\run_alpha.bat on Windows
```

Creates `.venv`, installs dependencies, seeds demo data into
`var/role_os_alpha/`, and starts the server at
`http://127.0.0.1:8000/`. See [`DEMO.md`](DEMO.md) for the full walkthrough.

### Option B — manual setup with your own data

```bash
# 1. Build the knowledge base from a ChatGPT export
cd builder
python builder.py "<chatgpt_export.zip>" "<output_dir>" --clean

# 2. Install and run the dashboard
cd ../dashboard
python -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -r requirements.txt
export ROLE_OS_DB_PATH="<output_dir>/00_SYSTEM/role_os.db"
uvicorn app.main:app --reload
```

Then open `http://127.0.0.1:8000/`.

### Environment variables

All optional — each has a sensible default. See
[`dashboard/README.md`](dashboard/README.md#configuration) for the full
table: six separate SQLite database paths (one per domain — five pointing
at the bundled sample data under `samples/role_os_sample/00_SYSTEM/`, plus
the Daily Session database under the git-ignored `var/`, since session
data is personal, not a fixture), `ROLE_OS_DEFAULT_IMPORT_PATH` and
`ROLE_OS_SEARCH_RESULT_LIMIT` (Sprint 8), and
`ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR` /
`ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` (ROLE OS Dashboard MVP) — both
optional, never hardcoded.

### Running the test suite

```bash
pip install -r requirements.txt
python -m pytest
```

Runs every test under `tests/` (repo-level), `dashboard/tests/`, and
`builder/tests/` (configured via `[tool.pytest.ini_options]` in
`pyproject.toml`).

## One-Click Windows Startup

Windows users don't need a terminal, a virtual environment activation
step, or to remember the `uvicorn` command at all.

### Start ROLE OS

Double-click **`Start ROLE OS.bat`** in the repository root. It:

1. Resolves the repository directory from its own location (works from
   any path, including one with spaces and parentheses).
2. Checks `http://127.0.0.1:8000/health` — if ROLE OS is already
   running, it just opens your browser and exits; it never starts a
   second server.
3. Otherwise, finds a Python interpreter (preferring, in order,
   `dashboard\.venv`, the repository root's `.venv`, `dashboard\venv`,
   `repository-root\venv`, then `py` / `python` / `python3` on `PATH`),
   verifies the required packages are installed, and starts
   `uvicorn app.main:app --host 127.0.0.1 --port 8000` in a separate,
   minimized window from the `dashboard\` directory.
4. Waits (up to 30 seconds) for `/health` to respond, then opens
   `http://127.0.0.1:8000` in your default browser.

If anything goes wrong (missing Python, missing dependencies, the port
already used by something else, or the server not becoming healthy in
time), the window stays open with a clear, specific message — including
the exact command to run if a dependency is missing.

### Optional: Desktop shortcut

Run once, from a terminal (see the execution-policy note below if
double-clicking it does nothing):

```powershell
powershell -ExecutionPolicy Bypass -File "CREATE_DESKTOP_SHORTCUT.ps1"
```

This creates a **ROLE OS** shortcut on your Desktop (resolved via
Windows' own Desktop special folder, so it works correctly even if your
Desktop is redirected, e.g. by OneDrive) that launches `Start ROLE OS.bat`
with the repository as its working directory. No Administrator privileges
are required.

### Stop ROLE OS

Double-click **`Stop ROLE OS.bat`**. It stops only the specific process
`Start ROLE OS.bat` started (tracked by PID and double-checked against
that process's own command line before anything is killed) — it will
never stop an unrelated Python or uvicorn process, even one that happens
to reuse the same PID. If ROLE OS isn't running, it says so and exits
cleanly.

### Default URL

`http://127.0.0.1:8000`

### Where logs and the PID file are stored

`dashboard\var\role_os_dashboard\` (git-ignored; co-located with the
Daily Session domain's own database, so all of ROLE OS's local runtime
state lives in one place):

- `role_os.pid` — the running server's process ID
- `launcher.log` — what the launcher itself detected and did
- `uvicorn.out.log` / `uvicorn.err.log` — the server's own stdout/stderr,
  useful when a startup failure needs more detail than the launcher's
  own error message

### Which database does the launcher use? Is the bundled sample data my permanent workspace?

**No — `samples\role_os_sample\` is demo data only.** It's a bundled
demo/testing fixture, checked into the repository (`.gitignore`
explicitly excepts `samples\**\*.db` from its general `*.db` rule
specifically so *this fixture* stays committed) — it's what the launcher
uses **by default** so ROLE OS runs out of the box with no setup, but it
is not meant to accumulate your real data, and nothing about it should be
treated as durable storage for anything you'd mind losing.

**`ROLE_OS_WORKSPACE_DIR` is the recommended configuration for real use.**
Your permanent workspace is whatever folder `builder\builder.py`
generates when you run it against your own ChatGPT export (see
"Using your own data" in [`README.md`](README.md)) — a folder containing
a `00_SYSTEM\` subfolder with `role_os.db` and friends, conventionally
named `ROLE_KNOWLEDGE_OS\` and typically kept *outside* this repository
(so it isn't tied to the repo's own git history or `samples\` fixture).
Once you have one, point the launcher at it — see "Configuring your
workspace" below — rather than continuing to run against the sample data.

**Auto-created domain databases belong in your real workspace, not in the
committed sample fixture.** Project Intelligence (`role_os_projects.db`)
and AI Advisor (`role_os_advisor.db`) are dashboard-owned: they create
their own schema automatically the first time the app runs against a
given `00_SYSTEM\` folder, regardless of whether that folder is the
sample fixture or your real workspace. If the launcher is ever pointed at
`samples\role_os_sample\00_SYSTEM\` (its default), those two files will
be recreated there as an empty starting point — this is expected, and
`.gitignore` deliberately re-excludes exactly those two filenames inside
`samples\` (while still allowing the curated `role_os.db` fixture itself
to be committed) specifically so this normal auto-create behavior can
never end up staged for a commit. If you notice either file present and
untracked inside `samples\role_os_sample\00_SYSTEM\`, that's a sign the
launcher ran against the sample workspace rather than
`ROLE_OS_WORKSPACE_DIR` — configure your workspace (below) rather than
committing or manually curating those files.

#### Configuring your workspace

Set **`ROLE_OS_WORKSPACE_DIR`** to your workspace folder (the one
*containing* `00_SYSTEM\`, not `00_SYSTEM\` itself) before running
`Start ROLE OS.bat`. The simplest reliable way to do this on Windows,
so it's set every time without editing any file or repeating a step:

```powershell
setx ROLE_OS_WORKSPACE_DIR "C:\path\to\your\ROLE_KNOWLEDGE_OS"
```

Run that once, in any terminal (`setx` does not require Administrator
rights and needs no elevation). It writes the variable to your Windows
user profile — every *new* process started after that (including a fresh
double-click of `Start ROLE OS.bat`) will see it automatically. It does
**not** affect a terminal/session that was already open when you ran
`setx`; open a new one (or just double-click the launcher fresh) to pick
it up.

The launcher derives all five database paths from
`%ROLE_OS_WORKSPACE_DIR%\00_SYSTEM\`, logs exactly which paths it
resolved to `launcher.log`, and refuses to start if the Knowledge
database isn't there — it never copies, moves, or otherwise migrates
data between the sample workspace and your real one; switching is purely
a matter of which folder the environment variable points at.

To change it later: run `setx ROLE_OS_WORKSPACE_DIR "C:\new\path"` again
(it overwrites the previous value), or remove it entirely with
`[Environment]::SetEnvironmentVariable("ROLE_OS_WORKSPACE_DIR", $null,
"User")` in PowerShell to go back to the bundled sample data. Either way,
`launcher.log`'s "Database source:" line always tells you which one is
actually in effect.

If you already run ROLE OS from a terminal with `ROLE_OS_DB_PATH` (and
the other four `ROLE_OS_*_DB_PATH` variables) set yourself, the launcher
respects that and does not override any variable you've already set.

### Troubleshooting the launcher

- **Double-clicking a `.ps1` file does nothing, or shows a security
  warning** — Windows doesn't run PowerShell scripts by double-click by
  default. Use `Start ROLE OS.bat` / `Stop ROLE OS.bat` instead (they
  invoke PowerShell with `-ExecutionPolicy Bypass` for that one process
  only — no system-wide policy change, no Administrator rights needed).
  For `CREATE_DESKTOP_SHORTCUT.ps1`, run it via the command in the
  section above.
- **"Port 8000 is already in use by a different application"** — some
  other program is listening on 8000. Close it, or stop whatever it is,
  then run `Start ROLE OS.bat` again. The launcher deliberately refuses
  to guess that a non-ROLE-OS response on that port is safe to treat as
  "already running."
- **"No usable Python interpreter was found"** — install Python 3.10+
  from [python.org](https://www.python.org/downloads/), or create a
  virtual environment: `py -m venv .venv` from the repository root.
- **"is missing required Python package(s)"** — the launcher checks
  every package declared in `dashboard/requirements.txt` (not a fixed
  short list), names exactly which one(s) are missing, and prints the
  exact `pip install -r ...` command to fix it; run it, then try again.
- **"The Knowledge database was not found at: ..."** — the launcher
  checks for the Knowledge database (`role_os.db`) before starting the
  server, using an absolute path anchored to the repository root (or to
  `ROLE_OS_WORKSPACE_DIR`, if you've set it) — never relative to
  `dashboard\`. If you see this, either the repository's
  `samples\role_os_sample\00_SYSTEM\` folder was moved or deleted, or
  `ROLE_OS_WORKSPACE_DIR` points at a folder with no `00_SYSTEM\role_os.db`
  inside it. `launcher.log` records exactly which path it checked.
- **Server never becomes healthy** — check
  `dashboard\var\role_os_dashboard\uvicorn.err.log` for the real
  traceback; the launcher prints its last lines automatically.
- **Stale PID file** — handled automatically: if the recorded PID is no
  longer running (or isn't a ROLE OS process), the launcher removes the
  file and proceeds normally.

## Troubleshooting

- **Port 8000 already in use** — stop whatever else is using it, or run
  `uvicorn app.main:app --reload --port <other-port>` (or edit the last
  line of `scripts/run_alpha.sh` / `run_alpha.bat` for the Alpha demo
  path).
- **`ModuleNotFoundError: No module named 'fastapi'` (or `'PIL'`, or any
  other dashboard dependency)** — the dashboard's dependencies aren't
  installed in the active environment; run
  `pip install -r dashboard/requirements.txt` (or the root
  `requirements.txt`) inside your virtual environment. The Windows
  launcher (`Start ROLE OS.bat`) checks for this itself before starting
  `uvicorn` — every package declared in `dashboard/requirements.txt`, not
  just `fastapi` — so this traceback should only appear if you're running
  `uvicorn` directly rather than through the launcher.
- **Starting the Alpha demo fresh** — stop the server and delete
  `var/role_os_alpha/`, then re-run the launch script. The bundled sample
  knowledge database under `samples/` is never modified, so nothing there
  needs to be reset.
- **Re-seeding manually** — `python scripts/seed_alpha_demo.py` (with the
  same `ROLE_OS_*` environment variables the launch script sets) is safe
  to run any time; it exits immediately if the demo projects already
  exist.
- **Pointing at a different knowledge database** — set `ROLE_OS_DB_PATH`
  (and the other five `ROLE_OS_*_DB_PATH` variables, if you want the other
  domains isolated too) before starting `uvicorn`.
- **Windows line-ending warnings from git** (`LF will be replaced by CRLF`)
  — informational only; they do not affect test results or application
  behavior.
- **Interactive API docs** — once the app is running, `/docs` (Swagger UI)
  and `/redoc` are available for exploring every endpoint directly.
