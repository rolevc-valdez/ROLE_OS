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
- **`dashboard/requirements.txt`** — the FastAPI service:
  - `fastapi`, `uvicorn[standard]` — the web framework and ASGI server
  - `jinja2` — server-rendered page shell (`templates/index.html`)
  - `python-multipart` — multipart file upload support (ChatGPT import,
    Settings import)
  - `pydantic` (pulled in transitively by FastAPI) — request/response models
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

## Troubleshooting

- **Port 8000 already in use** — stop whatever else is using it, or run
  `uvicorn app.main:app --reload --port <other-port>` (or edit the last
  line of `scripts/run_alpha.sh` / `run_alpha.bat` for the Alpha demo
  path).
- **`ModuleNotFoundError: No module named 'fastapi'`** — the dashboard's
  dependencies aren't installed in the active environment; run
  `pip install -r dashboard/requirements.txt` (or the root
  `requirements.txt`) inside your virtual environment.
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
