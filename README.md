# ROLE OS

ROLE OS turns a ChatGPT conversations export into a structured, searchable
personal knowledge base, and has evolved from a Knowledge Browser into a
Knowledge Operating System: a read-only knowledge API and dashboard, a
first-class Project Intelligence layer (workspaces, projects, capabilities,
dependencies, a Health Score engine), an explainable AI Advisor that
recommends what to work on next (Epic 2), and — as of Epic 3 — a Knowledge
Graph engine that connects Projects, Knowledge Cards, People, Applications,
Vendors, Capabilities, Workspaces, Decisions, Deliverables, Prompts,
Assets, and Conversations into one queryable relationship graph, computed
on demand with no separate graph database. No external AI API is required
anywhere in the system.

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

## Quick start

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
(`builder/extractors/`), a plain data-access API and web dashboard
(`dashboard`), a Project Intelligence layer (`dashboard/app/projects/`) with
first-class Workspaces, Projects, Capabilities, Dependencies, and a modular
Health Score engine, an explainable AI Advisor (`dashboard/app/advisor/`)
built from eight independent, deterministic rules plus a shared scoring
toolkit, and a Knowledge Graph engine (`dashboard/app/graph/`) that
consumes the Builder, Project Intelligence, and Advisor databases read-only
to compute 12 node types and 12 relationship types on demand — no data is
duplicated into a new store. No AI/LLM API is called anywhere — every
extractor, health signal, advisor rule, and graph relationship is
rule-based, not model-based. The Advisor's `AdvisorNarrativeProvider`
interface and the Graph Engine's plain, dependency-free query functions are
both designed seams for a future AI provider to build on without replacing
the deterministic core.

## Development

Run the full test suite from the repo root:

```bash
pip install -r dashboard/requirements.txt pytest
python -m pytest
```

See [`CHANGELOG.md`](CHANGELOG.md) for release history.
