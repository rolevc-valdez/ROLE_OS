# ROLE OS Alpha — Demo Guide

This is the first Alpha build of ROLE OS: the Builder, Knowledge Engine,
Project Intelligence, AI Advisor, Knowledge Graph, and Command Center UI,
seeded with a realistic set of demo projects so the whole system can be
explored end to end without bringing your own data first.

## Installation

Prerequisites: Python 3.10+ and Git. No other services (no Postgres, no
Redis, no external AI API) are required — everything runs locally against
SQLite files.

```bash
git clone https://github.com/rolevc-valdez/ROLE_OS.git
cd ROLE_OS
```

## First run

Everything — virtual environment, dependencies, demo data, and the server
— is handled by one script:

**macOS / Linux:**
```bash
./scripts/run_alpha.sh
```

**Windows:**
```bat
scripts\run_alpha.bat
```

The first run will:

1. Create a local `.venv` and install `dashboard/requirements.txt`.
2. Seed the Alpha demo data (see below) into `var/role_os_alpha/` — this
   step is idempotent, so re-running the script later won't duplicate
   data or reset anything you've done in the UI (dismissed
   recommendations, edited projects, etc.).
3. Start the dashboard at **http://127.0.0.1:8000/**.

Open that URL in a browser once the terminal prints
`Uvicorn running on http://127.0.0.1:8000`.

To reset the demo back to its original seeded state, stop the server and
delete the `var/role_os_alpha/` folder, then run the script again.

## Demo walkthrough

The seed data (`scripts/seed_alpha_demo.py`) populates seven projects
across five workspaces, with realistic collections, capabilities,
dependencies, and activity history — real Health Scores and Advisor
recommendations are then computed from that data, not hard-coded.

| Project | Workspace | What it represents |
|---|---|---|
| **ROLE OS** | Products | The platform itself — Builder, Dashboard, Project Intelligence, Advisor, Knowledge Graph |
| **ROLE MASTER** | Products | The master brand/character system (identity, avatar, prompts) other projects build on |
| **SUPER FACIL** | Products | A consumer app that depends on ROLE MASTER's brand and ROLE OS's engine |
| **RoleValdez** | Personal | Personal brand and public presence |
| **Kontoor** | Kontoor | Day-job IT service management work — deliberately backdated and overloaded with open to-dos so it shows up **critical** |
| **Unger** | Unger | Day-job IT operations/reporting work — moderately behind, shows up **warning** |
| **Charcos** | Ideas | A low-priority creative side project, stale but not urgent |

A good walkthrough order:

1. **Home** — see the Today's Focus cards (top Advisor recommendations),
   the Workspace Overview (healthy/warning/critical at a glance), the
   animated Health Dashboard, Recent Activity, and the Knowledge Graph
   preview.
2. **Projects** → open **Kontoor** to see a critical Health Score with a
   real breakdown, then open **ROLE MASTER** to see a healthy one.
3. **Advisor** — recommendations grouped by workspace: try dismissing one
   and marking another completed.
4. **Graph** — open the full-screen Knowledge Graph, click the **ROLE
   MASTER** node, expand its neighbors, then try **Impact analysis** to
   see what depends on it (SUPER FACIL and Charcos both do).
5. **Project Detail** (e.g. ROLE MASTER) — the three-column layout:
   Health Ring / status / Advisor summary on the left, notes/decisions/
   to-dos/deliverables in the center, capabilities/dependencies/related
   projects/graph preview on the right.

## Features

- **Builder** — turns a ChatGPT conversations export into structured
  Knowledge Cards (summary, decisions, to-dos, deliverables, people,
  applications, vendors, tags, related conversations).
- **Project Intelligence** — Workspaces, Projects, Capabilities,
  Dependencies, and a modular, explainable Health Score.
- **AI Advisor** — eight deterministic rules recommend what to work on
  next, each with a reason, evidence, suggested action, and expected
  impact. No external AI API is called.
- **Knowledge Graph** — 12 node types and 12 relationship types, computed
  on demand from the other three databases (no duplicated storage), with
  neighbor traversal, shortest-path, and impact-analysis queries.
- **Command Center UI** — a single dark-themed, framework-free dashboard:
  Home, Projects, Knowledge, Advisor, Graph, Assets, and Settings, all
  built on the API above.

## Keyboard shortcuts

The Alpha does not define any custom keyboard shortcuts yet — every
interaction (search, filters, expand/collapse, dismiss/complete) is
click-driven. Standard browser shortcuts (e.g. `Ctrl/Cmd+F` for
in-page find) work as normal since there's no shortcut layer intercepting
them.

## Screenshots

See [`docs/screenshots/`](docs/screenshots/) and the embedded previews in
the root [`README.md`](README.md#screenshots) for Home, Projects, Advisor,
Graph, and Project Detail.

## Troubleshooting

- **Port 8000 already in use**: stop whatever else is using it, or edit
  the last line of `scripts/run_alpha.sh` / `run_alpha.bat` to use a
  different `--port`.
- **Starting fresh**: delete `var/role_os_alpha/` and re-run the launch
  script — the knowledge database under `samples/` is never modified, so
  nothing there needs to be reset.
- **Re-seeding manually**: `python scripts/seed_alpha_demo.py` (with the
  same `ROLE_OS_*` environment variables the launch script sets) is safe
  to run any time; it exits immediately if the demo projects already
  exist.
