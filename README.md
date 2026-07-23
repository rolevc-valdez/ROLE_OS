# ROLE OS

ROLE OS turns a ChatGPT conversations export into a structured, searchable
personal knowledge base, and has evolved from a Knowledge Browser into a
Knowledge Operating System: a read-only knowledge API and dashboard, a
first-class Project Intelligence layer (workspaces, projects, capabilities,
dependencies, a Health Score engine), an explainable AI Advisor that
recommends what to work on next (Epic 2), a Knowledge Graph engine that
connects Projects, Knowledge Cards, People, Applications, Vendors,
Capabilities, Workspaces, Decisions, Deliverables, Prompts, Assets, and
Conversations into one queryable relationship graph computed on demand
with no separate graph database (Epic 3), and — as of Epic 4 — a
redesigned **Command Center** UI: a persistent sidebar, a Home page
(Today's Focus, Workspace Overview, an animated Health Dashboard, Recent
Activity, a Knowledge Graph preview, and grouped Quick Search), a
redesigned Project page, a full-screen Graph page with zoom/pan/impact
analysis, and an Advisor page — built entirely in plain HTML/CSS/vanilla
JS on top of the existing API, with no backend changes. No external AI API
is required anywhere in the system.

## Repository layout

```
ROLE_OS/
  builder/      # CLI tool: builds the ROLE Knowledge OS + SQLite DB from a ChatGPT export
  dashboard/    # FastAPI app: read-only API + web UI over the generated SQLite database
  docs/         # Project documentation
  tests/        # Repo-level / integration tests
  scripts/      # Utility and automation scripts
  samples/      # Sample ChatGPT export + generated output for local testing
```

## Documentation

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

## Try the Alpha demo (one command)

The fastest way to see ROLE OS end to end is the Alpha demo: it seeds
seven realistic sample projects (with real Health Scores, Advisor
recommendations, and a populated Knowledge Graph) and starts the
dashboard, in one command.

```bash
git clone https://github.com/rolevc-valdez/ROLE_OS.git
cd ROLE_OS
./scripts/run_alpha.sh        # or scripts\run_alpha.bat on Windows
```

Then open `http://127.0.0.1:8000/`. See [`DEMO.md`](DEMO.md) for a full
walkthrough, feature list, and troubleshooting.

## Quick start (your own data)

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
   See [`dashboard/README.md`](dashboard/README.md) for endpoint and UI details.

## Status

This repository currently implements a modular knowledge extraction engine
(`builder/extractors/`), a plain data-access API (`dashboard`), a Project
Intelligence layer (`dashboard/app/projects/`) with first-class
Workspaces, Projects, Capabilities, Dependencies, and a modular Health
Score engine, an explainable AI Advisor (`dashboard/app/advisor/`) built
from eight independent, deterministic rules plus a shared scoring toolkit,
a Knowledge Graph engine (`dashboard/app/graph/`) that consumes the
Builder, Project Intelligence, and Advisor databases read-only to compute
12 node types and 12 relationship types on demand — no data is duplicated
into a new store — and a Command Center web UI (`dashboard/app/static/`,
`dashboard/app/templates/index.html`) that is a pure presentation layer
over all of the above: a persistent sidebar, hash-routed pages (Home,
Projects, Project detail, Knowledge, Advisor, Graph, Assets, Settings),
and a small reusable design system (`colors.css`, `layout.css`,
`components.css`, `animations.css`), with zero new API surface, database,
or backend logic introduced for it. No AI/LLM API is called anywhere —
every extractor, health signal, advisor rule, and graph relationship is
rule-based, not model-based. The Advisor's `AdvisorNarrativeProvider`
interface and the Graph Engine's plain, dependency-free query functions are
both designed seams for a future AI provider to build on without replacing
the deterministic core.

## Screenshots

Real screenshots of the seeded Alpha demo aren't bundled in this repo yet. To see the UI for
yourself, run the one-command demo below and open `http://127.0.0.1:8000` — you'll land on a
fully populated Home, Projects, Advisor, Graph, and Project Detail view with realistic seeded
data. If you'd like to add screenshots to this README, drop PNGs into `docs/screenshots/` named
`home.png`, `projects.png`, `advisor.png`, `graph.png`, and `project_detail.png`, then reference
them here with standard Markdown image syntax.

## Development

Run the full test suite from the repo root:

```bash
pip install -r dashboard/requirements.txt pytest
python -m pytest
```

See [`CHANGELOG.md`](CHANGELOG.md) for release history.
