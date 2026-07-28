# ROLE OS

**Version 1.0** — a personal Knowledge Operating System built on top of
your own ChatGPT conversation history. No external AI/LLM API is called
anywhere in the system: every extractor, health signal, Advisor rule, and
Graph relationship is rule-based and deterministic.

## What ROLE OS is

ROLE OS turns a ChatGPT conversations export into a structured, searchable
personal knowledge base, and has evolved from a Knowledge Browser into a
Knowledge Operating System: a read-only knowledge API and dashboard, a
first-class Project Intelligence layer (workspaces, projects, capabilities,
dependencies, a Health Score engine), an explainable AI Advisor that
recommends what to work on next, a Knowledge Graph engine that connects
Projects, Knowledge Cards, People, Applications, Vendors, Capabilities,
Workspaces, Decisions, Deliverables, Prompts, Assets, and Conversations
into one queryable relationship graph computed on demand with no separate
graph database, and a **Command Center** UI: a persistent sidebar, a Home
page (Today's Focus, Workspace Overview, an animated Health Dashboard,
Recent Activity, a Knowledge Graph preview, and grouped Quick Search), a
redesigned Project page, a full-screen Graph page with zoom/pan/impact
analysis, an Advisor page, a Dashboard executive summary, a Conversation
Explorer, a second Knowledge Graph over imported conversations, and a
Settings page — built entirely in plain HTML/CSS/vanilla JS on top of the
existing API, with no frontend framework.

## Features

- **Builder** — an offline CLI (`/builder`, no third-party dependencies)
  that turns a ChatGPT export into structured Knowledge Cards (summary,
  decisions, to-dos, deliverables, people, applications, vendors, tags,
  related conversations) and a SQLite database.
- **ChatGPT Conversation Importer** — a dashboard-owned pipeline for
  bringing conversations in directly, without regenerating the whole
  Builder output.
- **Conversation Explorer** — browse, search, filter, inspect, and manage
  every imported conversation.
- **Knowledge Extraction** — deterministic, rule-based extraction of
  Projects, People, Tasks, Decisions, Ideas, Documents, and Assets from
  imported conversations.
- **Knowledge Graph** — two independent graphs: one over Projects/Advisor/
  Builder data (12 node types, 12 relationship types), and a second, smaller
  one over imported conversations and their extracted objects — both
  computed on demand, with no dedicated graph database.
- **Project Intelligence** — first-class Workspaces, Projects,
  Capabilities, Dependencies, and a modular, explainable Health Score.
- **AI Advisor** — eight deterministic rules recommend what to work on
  next, each self-explaining (reason, evidence, suggested action, expected
  impact), plus keyword search ("Search Knowledge") over everything
  imported and extracted.
- **Dashboard** — an executive-summary page with live counts, recent
  activity, system status, and quick actions.
- **Settings** — a read-only, exportable view of configuration, live
  system status, and version/license info, with maintenance actions
  (rebuild graph, clear cache).
- **Command Center UI** — one dark-themed, framework-free single-page app
  over all of the above.

See [`CHANGELOG.md`](CHANGELOG.md) for the full, sprint-by-sprint history
behind each feature.

## Architecture overview

```
ChatGPT export (.zip)
        │
        ▼
   builder/builder.py  ──▶  modular extraction pipeline
        │
        ▼
  ROLE_KNOWLEDGE_OS/ (folder tree + role_os.db)
        │
        ▼
  dashboard (FastAPI): read-only Knowledge API
        │
        ├──▶ Project Intelligence (own SQLite DB)
        ├──▶ AI Advisor (own SQLite DB, reads the above read-only)
        ├──▶ Knowledge Graph (computed on demand, no DB of its own)
        ├──▶ ChatGPT Importer + Conversation Explorer (own SQLite DB)
        ├──▶ Knowledge Extraction (own SQLite DB, reads the Importer's DB)
        ├──▶ second Knowledge Graph (computed on demand from Importer + Extraction)
        ├──▶ Advisor Search (reads the Importer + Extraction DBs)
        ├──▶ Settings (reads all of the above, writes nothing new)
        │
        ▼
  Command Center UI (static HTML/CSS/JS, pure presentation layer)
```

Every domain above owns its own SQLite database or computes on demand from
the others — nothing is ever duplicated into a new store, and no domain
writes to a database it doesn't own. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
for the full write-up of how each part interacts, and
[`docs/architecture/`](docs/architecture/) for the original design
documents.

## Screenshots

Real screenshots of the seeded Alpha demo aren't bundled in this repo yet.
To see the UI for yourself, run the one-command demo below and open
`http://127.0.0.1:8000` — you'll land on a fully populated Home, Projects,
Advisor, Graph, and Project Detail view with realistic seeded data. If
you'd like to add screenshots to this README, drop PNGs into
`docs/screenshots/` named `home.png`, `projects.png`, `advisor.png`,
`graph.png`, and `project_detail.png`, then reference them here with
standard Markdown image syntax.

## Requirements

- Python 3.10+
- Git
- No other services — no Postgres, no Redis, no external AI API. Everything
  runs locally against SQLite files.

See [`INSTALLATION.md`](INSTALLATION.md) for full dependency, environment,
and troubleshooting details.

## Installation

The fastest way to see ROLE OS end to end is the Alpha demo: it seeds
seven realistic sample projects (with real Health Scores, Advisor
recommendations, and a populated Knowledge Graph) and starts the
dashboard, in one command.

```bash
git clone https://github.com/rolevc-valdez/ROLE_OS.git
cd ROLE_OS
./scripts/run_alpha.sh        # or scripts\run_alpha.bat on Windows
```

Then open `http://127.0.0.1:8000/`. See [`QUICK_START.md`](QUICK_START.md)
for a first-time walkthrough (clone → install → run → import → explore →
Advisor → Dashboard → Settings), [`DEMO.md`](DEMO.md) for the seeded Alpha
demo walkthrough, and [`INSTALLATION.md`](INSTALLATION.md) for manual
setup and troubleshooting.

### Using your own data

1. **Build the knowledge base** from a ChatGPT export:

   ```bash
   cd builder
   python builder.py "<chatgpt_export.zip>" "<output_dir>" --clean
   ```

   See [`builder/README.md`](builder/README.md) for details.

2. **Serve it** with the dashboard API:

   ```bash
   cd dashboard
   pip install -r requirements.txt
   export ROLE_OS_DB_PATH="<output_dir>/00_SYSTEM/role_os.db"
   uvicorn app.main:app --reload
   ```

   Then open `http://127.0.0.1:8000/` in a browser for the dashboard UI.
   See [`dashboard/README.md`](dashboard/README.md) for endpoint and UI
   details.

## Running locally

```bash
uvicorn app.main:app --reload
```

(from the `dashboard/` directory, with `ROLE_OS_DB_PATH` and friends set —
see [`INSTALLATION.md`](INSTALLATION.md)). Then visit
`http://127.0.0.1:8000/` for the Command Center UI, or
`http://127.0.0.1:8000/health` / `http://127.0.0.1:8000/docs` to check the
API directly.

In addition to the offline Builder pipeline, the dashboard has a
lightweight, dashboard-owned **ChatGPT conversation importer** for bringing
conversations in without regenerating the whole knowledge base, a
**Conversation Explorer** page for browsing/searching/filtering/managing
what was imported, per-conversation **Knowledge Extraction**, a second
**Knowledge Graph** page over imported conversations, a **Search
Knowledge** box on the Advisor page, a **Dashboard** executive-summary
page, and a **Settings** page. All of these stay deliberately AI-free —
normalize, store, search, display, pattern-match, graph, and summarize
only using data already computed elsewhere. See
[`docs/product/CHANGELOG_PRODUCT.md`](docs/product/CHANGELOG_PRODUCT.md)
for supported formats, deduplication behavior, and known limitations per
feature.

## Repository structure

```
ROLE_OS/
  builder/      # CLI tool: builds the ROLE Knowledge OS + SQLite DB from a ChatGPT export
  dashboard/    # FastAPI app: read-only API + web UI over the generated SQLite database(s)
  docs/         # Project documentation (architecture, product decisions, changelog)
  tests/        # Repo-level / integration tests
  scripts/      # Utility and automation scripts (Alpha demo, ChatGPT import CLI)
  samples/      # Sample ChatGPT export + generated output for local testing
  var/          # Local, git-ignored runtime data (e.g. the Alpha demo's databases)
```

## Documentation

- [`QUICK_START.md`](QUICK_START.md) — first-time walkthrough
- [`INSTALLATION.md`](INSTALLATION.md) — dependencies, environment, troubleshooting
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how every domain interacts
- [`CHANGELOG.md`](CHANGELOG.md) — full sprint-by-sprint release history
- [`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md) — v1.0 highlights, known limitations, roadmap
- [`DEMO.md`](DEMO.md) — the seeded Alpha demo walkthrough
- [`LICENSE.md`](LICENSE.md) — license terms
- **Architecture** (`docs/architecture/`):
  [Vision](docs/architecture/01_VISION.md) ·
  [Principles](docs/architecture/02_PRINCIPLES.md) ·
  [Architecture](docs/architecture/03_ARCHITECTURE.md) ·
  [Data Model](docs/architecture/04_DATA_MODEL.md) ·
  [UI Guidelines](docs/architecture/05_UI_GUIDELINES.md) ·
  [Development Rules](docs/architecture/06_DEVELOPMENT_RULES.md) ·
  [Roadmap](docs/architecture/07_ROADMAP.md)
- **Product** (`docs/product/`):
  [Decisions](docs/product/DECISIONS.md) ·
  [Product Changelog](docs/product/CHANGELOG_PRODUCT.md)
- Component READMEs: [`builder/README.md`](builder/README.md) ·
  [`dashboard/README.md`](dashboard/README.md)

## Status

This repository implements a modular knowledge extraction engine
(`builder/extractors/`), a plain data-access API (`dashboard`), a Project
Intelligence layer with first-class Workspaces, Projects, Capabilities,
Dependencies, and a modular Health Score engine, an explainable AI Advisor
built from eight independent, deterministic rules plus a shared scoring
toolkit, a Knowledge Graph engine that computes 12 node types and 12
relationship types on demand from the Builder/Project Intelligence/Advisor
databases, a ChatGPT Conversation Importer and Conversation Explorer, a
Knowledge Extraction pipeline, a second Knowledge Graph over imported
conversations, Advisor Search, a Dashboard executive summary, a Settings
page, and a Command Center web UI that is a pure presentation layer over
all of the above — zero new API surface, database, or backend logic
introduced for the UI itself. No AI/LLM API is called anywhere; every
extractor, health signal, advisor rule, and graph relationship is
rule-based, not model-based. The Advisor's `AdvisorNarrativeProvider`
interface and the Graph Engine's plain, dependency-free query functions
are both designed seams for a future AI provider to build on without
replacing the deterministic core.

## Development

Run the full test suite from the repo root:

```bash
pip install -r requirements.txt
python -m pytest
```

## License

Proprietary — All Rights Reserved. See [`LICENSE.md`](LICENSE.md).
