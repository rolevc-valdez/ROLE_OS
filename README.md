# ROLE OS

**Version 1.2** (the app's own version — see "Role OS 2.0" below for what
that separate name refers to) — a personal Knowledge Operating System and
Project Intelligence layer built on top of your own ChatGPT conversation
history and your own project folders. No external AI/LLM API is called
anywhere in the system: every extractor, health signal, recommendation
rule, and Graph relationship is rule-based and deterministic.

## What ROLE OS is

ROLE OS turns a ChatGPT conversations export into a structured, searchable
personal knowledge base, and has evolved from a Knowledge Browser into a
full Project Intelligence and daily-operating system. Two layers, both
still present and both still real:

- **The original Knowledge/Project Intelligence layer** (v1.x): a
  read-only Knowledge API, first-class Projects/Workspaces/Capabilities/
  Dependencies with a Health Score engine, an explainable AI Advisor
  (eight deterministic rules), a Knowledge Graph engine (12 node/12
  relationship types, computed on demand, no separate graph database), a
  ChatGPT Conversation Importer + Explorer, and a rule-based Knowledge
  Extraction pipeline.
- **Role OS 2.0** (Phase 1 + Phase 2 — the current, actively-developed
  layer, and now the app's real front door): the filesystem itself is
  discovered and classified (**Discovery Engine + Workspace Adoption**:
  scan one or more configured folders, classify what's found, and let you
  explicitly adopt real projects, one at a time — discovery is never
  adoption, and nothing is ever auto-adopted); every adopted project gets
  one canonical shape (**Project Context**, reused by every page so they
  can never disagree with each other); a deterministic recommendation
  layer (**Operational Intelligence** → **Executive Decision**) ranks
  what matters most across your whole adopted portfolio, with full
  evidence and no black box; and **Mission Control** — now the canonical
  landing page at `/` — composes all of it into one screen that answers,
  every time you open ROLE OS: *Where did I leave off? What matters now?
  What should I do next? Can I continue working immediately?* — the last
  question answered by **Resume Work**, which builds a ready-to-paste
  continuation prompt from your project's own real history.

Both layers share one **Command Center** UI shell: a persistent sidebar
and a single-page app, built entirely in plain HTML/CSS/vanilla JS on top
of the existing API, with no frontend framework. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for exactly how the two layers fit
together, and `docs/architecture/` for the original per-sprint design
documents behind each part.

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
- **Daily Session** — a Start/End My Day workflow: pick a date, project,
  and operation mode (PLAN/BUILD/CREATE/LAUNCH/OPERATE/LEARN); get a
  copyable Claude session-initialization prompt; close the day with a
  generated, Obsidian-compatible Markdown daily record (copy, download, or
  optionally save straight into a configured vault folder); plus a small
  local registry of ROLE Ecosystem projects and a Recent Decisions feed
  read live from `role-ecosystem/DECISION_LOG.md` when configured.
- **Command Center UI** — one dark-themed, framework-free single-page app
  over all of the above.

### Role OS 2.0 features (current, actively developed)

- **Mission Control** — the canonical landing page (`/`, `/mission-control`).
  One screen answering, every time: Where I Left Off (Primary Focus +
  Resume Work), What Matters Now (Executive Decision), What's Next
  (Today's Focus) — plus Portfolio Ranking, Needs Attention, Since Last
  Time, Daily Session, and Value Signal, all reusing the same underlying
  data with no second ranking engine.
- **Discovery Engine** — read-only, bounded filesystem scan of one or more
  configured root folders; classifies what it finds (Software Project /
  Documentation Project / Non-project / etc.) and computes a Health Score
  and move-risk per folder. **Multi-Root Discovery** (Phase 2 Task 2.1)
  lets it scan several explicitly-configured roots at once
  (`ROLE_OS_DISCOVERY_ROOTS`), validated and deduplicated before scanning.
- **Workspace Adoption** — discovery is never adoption: a discovered
  folder becomes a first-class ROLE OS Project only when explicitly
  adopted, one at a time, on the Workspace page. Mission Control and every
  other 2.0 view reason only over the adopted portfolio.
- **Project Context** — the one canonical shape for "everything about a
  project" (health, next action, latest AI session/snapshot, resume
  state), reused by Mission Control, Projects, Workspace, and Cockpit so
  they can never disagree with each other.
- **Resume Work** — builds a ready-to-paste continuation prompt from a
  project's own real history (latest snapshot, pending work, next action,
  operational recommendation) — no separate, parallel "what was I doing"
  system.
- **Operational Intelligence → Executive Decision** — a deterministic,
  evidence-based ranking of every adopted project (Operational
  Intelligence), topped by one explainable "what to do today" pick
  (Executive Decision) — both fully rule-based, reused by every card that
  needs a recommendation instead of each computing its own.
- **Project Ecosystem / Impact Analysis** — detects real cross-project
  relationships (shared assets, dependencies) and estimates "what else
  might this change affect," feeding Project Memory's related-projects
  section.
- **Assets OS** — a shared, cached, read-only index of real project files
  (images, documents, design files) with preview thumbnails — the
  filesystem stays the source of truth; nothing is ever copied, moved, or
  edited.
- **Freshness / fallback honesty** — every recommendation that depends on
  a Discovery scan or an external file discloses, visibly, when its
  underlying data is stale or a fallback was used — never a silent,
  indistinguishable-from-live snapshot.

See [`CHANGELOG.md`](CHANGELOG.md) for the full, sprint-by-sprint history
behind each feature, and `docs/PHASE_1_COMPLETION.md` /
`docs/PHASE_2_*.md` for how and when each Role OS 2.0 feature was built
and verified.

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

That is the original v1.x Knowledge/Project Intelligence layer, and it
still runs unmodified. Role OS 2.0 layers a second, independent chain on
top, over your own project *folders* rather than a ChatGPT export:

```
your project folders (one or more configured roots)
        │
        ▼
  Discovery Engine  ──▶  scan ▶ classify ▶ score (read-only, never adopts)
        │
        ▼
  Workspace Adoption  ──▶  explicit, one-at-a-time adopt/ignore (own SQLite DB)
        │
        ▼
  Project Context  ──▶  the one canonical shape for an adopted project
        │
        ├──▶ Resume Work (continuation prompt from real history)
        ├──▶ Assets OS / Project Ecosystem / Impact Analysis
        ▼
  Operational Intelligence  ──▶  Executive Decision  (deterministic ranking)
        │
        ▼
  Mission Control  ──▶  the canonical landing page (`/`, `/mission-control`)
        │
        ▼
  Command Center UI (same shell as above — one sidebar, one single-page app)
```

Every domain in both chains owns its own SQLite database or computes on
demand from the others — nothing is ever duplicated into a new store, and
no domain writes to a database it doesn't own. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the full write-up of how each
part interacts, [`docs/RUNTIME_DATA_MAP.md`](docs/RUNTIME_DATA_MAP.md)
for the canonical runtime data locations, and
[`docs/architecture/`](docs/architecture/) for the original per-sprint
design documents.

## Screenshots

Real screenshots of the seeded Alpha demo aren't bundled in this repo yet.
To see the UI for yourself, run the one-command demo below and open
`http://127.0.0.1:8000` — the seeded data populates the v1.x
Projects/Advisor/Graph/Project Detail views (real Health Scores, Advisor
recommendations, a populated Knowledge Graph). **Note:** `/` now lands on
Mission Control (Role OS 2.0's canonical landing page — see "Role OS 2.0
features" above), which reasons over *adopted* Workspace projects, a
separate mechanism the Alpha demo does not seed; expect an honest empty
state there unless you've also run Discovery/Workspace Adoption
(`/workspace`) against real folders. If you'd like to add screenshots to
this README, drop PNGs into `docs/screenshots/` named `home.png`,
`projects.png`, `advisor.png`, `graph.png`, `project_detail.png`, and
`mission_control.png`, then reference them here with standard Markdown
image syntax.

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

## One-Click Windows Startup

On Windows, you don't need a terminal at all:

1. Double-click **`Start ROLE OS.bat`** in the repository root. It finds
   a Python environment (preferring a local `.venv`), starts the server
   in a minimized window, waits for it to become healthy, and opens
   `http://127.0.0.1:8000` in your default browser. If ROLE OS is already
   running, it just opens the browser — it never starts a second server.
2. *(Optional, once)* Run **`CREATE_DESKTOP_SHORTCUT.ps1`** to add a
   **ROLE OS** shortcut to your Desktop that does the same thing.
3. To stop it, double-click **`Stop ROLE OS.bat`**. It only ever stops
   the ROLE OS process it started — never an unrelated Python process.

See [`INSTALLATION.md`](INSTALLATION.md#one-click-windows-startup) for
the full walkthrough, where logs and the PID file are stored, and
troubleshooting.

## Repository structure

```
ROLE_OS/
  Start ROLE OS.bat, Stop ROLE OS.bat   # One-click Windows launcher (see above)
  CREATE_DESKTOP_SHORTCUT.ps1            # Optional: adds a Desktop shortcut
  builder/      # CLI tool: builds the ROLE Knowledge OS + SQLite DB from a ChatGPT export
  dashboard/    # FastAPI app: read-only API + web UI over the generated SQLite database(s)
  docs/         # Project documentation (architecture, product decisions, changelog)
  tests/        # Repo-level / integration tests
  scripts/      # Utility and automation scripts: Alpha demo, ChatGPT import CLI, and
                #   Start-RoleOS.ps1 / Stop-RoleOS.ps1 / RoleOS.Common.ps1 (launcher implementation)
  samples/      # Sample ChatGPT export + generated output for local testing
  var/          # Local, git-ignored runtime data (e.g. the Alpha demo's databases)
```

## Documentation

- [`QUICK_START.md`](QUICK_START.md) — first-time walkthrough
- [`INSTALLATION.md`](INSTALLATION.md) — dependencies, environment, troubleshooting, and [One-Click Windows Startup](INSTALLATION.md#one-click-windows-startup)
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
  [`dashboard/README.md`](dashboard/README.md) — the dashboard README also
  documents every Role OS 2.0 domain, endpoint, and environment variable
  (Discovery, Workspace, Mission Control, Multi-Root Discovery, etc.)
- **Role OS 2.0** (Phase 1 + Phase 2, current): `docs/PHASE_1_COMPLETION.md`
  (what Phase 1 built and verified) and `docs/PHASE_2_*.md` (each
  completed Phase 2 task's own report) are the authoritative history of
  *how* each 2.0 feature was built — read `CURRENT_STATE.md` first for
  *what's true right now*.

## Current State & Continuity

This repository is under active, iterative development, tracked through
two living files that are overwritten (not appended to) at the end of
every completed task rather than left to go stale like a traditional
changelog:

- **[`CURRENT_STATE.md`](CURRENT_STATE.md)** — the current phase, what's
  working right now (with evidence), the canonical runtime data model,
  and every open decision explicitly deferred to Role.
- **[`NEXT_ACTIONS.md`](NEXT_ACTIONS.md)** — the next task, in the
  approved execution order, plus explicit "do not do yet" guardrails.

**A developer or a fresh AI session resuming this project should read
these two files first, before any historical task report** — they're
designed to be sufficient on their own, verified against `git log`, to
understand the current phase, what changed last, and what's next, without
reading dozens of historical sprint/task documents.

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
conversations, Advisor Search, and a Settings page — all still real,
still unmodified, still reachable via navigation.

**On top of that** (Role OS 2.0, Phase 1 + Phase 2, current), the same
repository now also implements: a read-only Discovery Engine that scans
one or more explicitly-configured root folders and classifies what it
finds; Workspace Adoption, an explicit, one-at-a-time gate between
"discovered" and "a real ROLE OS Project"; a canonical Project Context
shape reused by every project-facing page; Resume Work (a real
continuation-prompt builder, not a stub); Operational Intelligence and
Executive Decision (a deterministic, evidence-based, fully-explained
ranking of the adopted portfolio); Project Ecosystem and Impact Analysis
(detected cross-project relationships); Assets OS (a shared, cached
filesystem asset index); and Mission Control, the canonical landing
page composing all of the above into one screen. The Command Center web
UI remains a pure presentation layer over every API above — zero new
frontend framework, zero client-side ranking or joining logic of its own.

No AI/LLM API is called anywhere in either layer; every extractor, health
signal, advisor rule, Operational Intelligence/Executive Decision score,
and graph relationship is rule-based, not model-based. The Advisor's
`AdvisorNarrativeProvider` interface and the Graph Engine's plain,
dependency-free query functions remain designed seams for a future AI
provider to build on without replacing the deterministic core — still
not implemented in this release, in either layer.

## Development

Run the full test suite from the repo root:

```bash
pip install -r requirements.txt
python -m pytest
```

## License

Proprietary — All Rights Reserved. See [`LICENSE.md`](LICENSE.md).
