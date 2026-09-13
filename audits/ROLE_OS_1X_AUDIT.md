# Role OS 1.x Audit

Read-only forensic audit performed 2026-09-07. Scope: full repository at
`C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS\ROLE_OS`. No files
were modified; this document is the only file created.

## Executive Summary

Role OS today is a single FastAPI application (`dashboard/`) plus an offline
CLI (`builder/`) that has grown, sprint by sprint, from a "ChatGPT export
browser" into a genuinely deep, deterministic project-intelligence system —
20+ internal domains (`app/discovery`, `app/workspace`, `app/project_memory`,
`app/project_ecosystem`, `app/impact_analysis`, `app/executive_decision`,
`app/operational_intelligence`, `app/advisor`, `app/graph`, `app/mission_control`,
etc.), each with its own SQLite file or computed-on-demand logic, wired
together through `dashboard/app/main.py`. The engineering discipline is
unusually high for a solo project: every module's docstring states what it
does *and does not* do ("no LLM," "no new persisted store," "additive
only"), and the code backs this up — there is genuinely no AI/LLM API call
anywhere in the runtime.

The most important finding is **documentation drift, not code rot**: the
code is ahead of the docs. `README.md` and root `ARCHITECTURE.md` describe
the system as of roughly Sprint 8/Epic 4 (Settings, Command Center UI) and
never mention Project Memory, Resume Work, Mission Control, Assets OS,
Project Ecosystem, Impact Analysis, Executive Decision, Dashboard 2.0, or
Explorer 2.0 — six-plus major subsystems that already exist, are wired into
`main.py`, and are covered by tests. `docs/architecture/*.md` (numbered
sprint reports 09–21) is the accurate, current record; the polished
top-level docs were simply never re-synced.

The second most important finding is that **`project-dashboard.html`
(untracked, at repo root) is a completely independent, self-contained,
localStorage-only "project map" web page** — not part of the FastAPI app,
sharing no code, no data, and no route with `dashboard/`. It is a second,
competing idea of what "the dashboard" is, built for a different purpose
(a manual, hand-edited catalog of ROLE projects/tools) than the Python
dashboard (an automated intelligence system over discovered projects).

Role OS 2.0's three target questions ("¿Dónde me quedé?", "¿Qué importa
ahora?", "¿Qué sigue?") are **already substantially answered by existing
code** — `app.project_memory` (session/session-intent/resume prompt),
`app.executive_decision` (what to work on next), and `app.mission_control`
(the daily composed view) — but none of this is surfaced in the docs a
newcomer (or Role, months later) would read first.

## Repository Overview

- 488 tracked/working files (excluding `.git`, `.venv`, `.pytest_cache`,
  `.ruff_cache`, `__pycache__`), spanning two independently runnable Python
  components (`builder/`, `dashboard/`), a scripts layer, docs, samples,
  and one standalone static HTML file.
- Git history shows five consecutive commits (`71e8aa0`…`28736ec`) each
  adding one full domain (Operational Intelligence → Project Ecosystem →
  Impact Analysis → Executive Decision → wiring/Dashboard 2.0), consistent
  with the sprint-report naming in `docs/architecture/19_*`–`21_*`.
- Working tree currently has 9 modified files and 3 new untracked items
  (`operational_manifest.py` detector + its test, `assets/`,
  `project-dashboard.html`) — an in-progress feature to let *other*
  repositories publish a `.role-os/project-status.json` manifest that Role
  OS's Discovery Engine can read (see `dashboard/app/discovery/detectors/
  operational_manifest.py`).

## Directory Structure

```
ROLE_OS/
├── builder/              # offline CLI: ChatGPT export -> Knowledge Cards + role_os.db (stdlib only)
├── dashboard/             # FastAPI app — the real system
│   ├── app/
│   │   ├── main.py                 # single entrypoint, ~20 routers mounted
│   │   ├── config.py                # env-driven Settings, one path per SQLite store
│   │   ├── discovery/                # filesystem scanner: finds/classifies real projects
│   │   ├── workspace/                # "adopted projects" overlay + Resume Work orchestration
│   │   ├── project_memory/           # session intent, resume prompt, context package (the "¿Dónde me quedé?" engine)
│   │   ├── project_context/          # single builder that assembles a project's full page
│   │   ├── project_ecosystem/        # inter-project relationship graph (deterministic evidence)
│   │   ├── impact_analysis/          # "if X changes, what else breaks" over the ecosystem graph
│   │   ├── executive_decision/       # "what should I work on next" — the "¿Qué sigue?" engine
│   │   ├── operational_intelligence/ # per-project priority/urgency signals
│   │   ├── mission_control/          # composed daily-view endpoint (the "¿Qué importa ahora?" engine)
│   │   ├── advisor/, graph/, conversation_graph/  # earlier (Epic 2/3) recommendation + graph engines
│   │   ├── imports/, extraction/     # ChatGPT conversation importer + rule-based knowledge extraction
│   │   ├── assets/                   # asset index/classification/preview ("Assets OS")
│   │   ├── session/, services/       # daily session + cross-cutting transport helpers (resume/launcher)
│   │   ├── routers/                  # one router module per domain, incl. routers/pi/* (Project Intelligence)
│   │   └── static/, templates/       # server-rendered Jinja UI + vanilla-JS "Command Center"
│   ├── requirements.txt              # FastAPI/uvicorn/pydantic/jinja2/python-multipart/Pillow
│   └── tests/                        # ~90 test files, one roughly per domain
├── docs/
│   ├── architecture/01–21           # numbered vision/principles/architecture/data-model + per-sprint reports (current)
│   └── product/                     # CHANGELOG_PRODUCT.md, DECISIONS.md
├── samples/role_os_sample/          # fixture data (Builder-generated sample DB) — default DB path in config.py
├── scripts/                         # Start/Stop PowerShell + .bat launchers, chatgpt import CLI, alpha seed script
├── var/                              # gitignored runtime state: real SQLite DBs + generated thumbnails + discovery report cache
├── tests/                            # 3 top-level smoke tests (builder, importer CLI, launcher dependency check)
├── assets/role-master/               # 2 PNGs, untracked — appears to be brand asset input, unrelated to app code
├── project-dashboard.html            # untracked, standalone static HTML "project map" — NOT part of dashboard/
├── "New folder"                      # empty directory, no files — junk
├── README.md / ARCHITECTURE.md / QUICK_START.md / INSTALLATION.md / DEMO.md / CHANGELOG.md  # stale top-level docs (see below)
└── RELEASE_NOTES_v1.0.md / RELEASE_NOTES_v1.1.0.md / FINAL_RELEASE_CHECKLIST.md / CONTRIBUTING.md / LICENSE.md
```

## Current Architecture

`dashboard/app/main.py` is a flat FastAPI app: one `FastAPI()` instance,
~24 `app.include_router(...)` calls, each preceded by a multi-line comment
documenting the sprint that added it, what it's namespaced under, what it
reuses, and — critically — what new persistence (if any) it introduces.
Every comment repeats the same invariant: "additive only," "no new
persisted store," reuse of an existing domain's already-computed output
rather than recomputing it. This is a real architectural discipline, not
just a comment style — verified by reading `config.py` (one path per store,
each with a paragraph justifying why it exists and where it lives) and
`dashboard/app/workspace/resume.py`/`app/services/resume.py` (a genuine
layering: `services.resume` = pure transport lookup, `workspace.resume` =
orchestration that calls into `project_memory` for the actual prompt).

Storage is intentionally fragmented: 8+ separate SQLite files
(`role_os.db`, `role_os_projects.db`, `role_os_advisor.db`,
`role_os_imports.db`, `role_os_extraction.db`, `role_os_session.db`,
`role_os_workspace.db`, `role_os_assets.db`, `role_os_ecosystem.db`), each
owned by exactly one domain, several domains computing everything on
demand with no database at all (Graph, Conversation Graph, Project
Context, Project Ecosystem, Impact Analysis, Executive Decision, Mission
Control). Verified directly: `var/role_os_dashboard/role_os_workspace.db`
contains `workspace_scan_cache`/`adopted_projects`; `role_os_assets.db`
contains `asset_cache`/`asset_overrides`; `role_os_ecosystem.db` contains
only `relationship_overrides` (an overlay, not the graph itself) — exactly
matching what the docstrings claim.

## How Role OS Actually Works Today

1. **Discovery** (`app/discovery/`) scans a filesystem root (default:
   the repo's parent directory, i.e. `1 - IA PROJECTS`) via a pipeline of
   independent detectors (`detectors/registry.py` lists ~14: git, tests,
   CI, Docker, docs, markers, assets, absolute-paths, obsidian,
   vscode_workspace, environment, scripts, databases, and the new
   `operational_manifest`) and classifies each folder as a real
   project/non-project/etc.
2. **Workspace** (`app/workspace/`) lets the user "adopt" discovered
   folders into a persistent overlay (priority, tags, status, notes) —
   the filesystem stays the source of truth; the workspace DB is a thin
   cache + user annotations only.
3. **Project Context** (`app/project_context/builder.py`) assembles
   everything one project page needs by composing Discovery + Workspace +
   Project Intelligence (`/pi/*`) + Advisor.
4. **Project Memory** (`app/project_memory/`) is the "¿Dónde me quedé?"
   engine: `session_intent.py`, `session_selection.py`,
   `context_package.py` (bounded reads + regex heading extraction from
   README/ROADMAP/DECISION_LOG-style files, redacting secrets — see the
   "OpenAI/Anthropic-style bearer secrets" redaction regex in
   `context_package.py:119`), `prompt.py` (builds the actual resume
   prompt text), and `naming.py` (auto-titles sessions as `<Project> --
   <Objective>`, never "Untitled").
5. **Resume Work** (`app/workspace/resume.py`) is the single primary
   action every project page exposes: Project → Project Memory → Resume
   Prompt → locate/auto-create best AI Session → open conversation → copy
   prompt. `execution_target.py` classifies where that work should
   physically happen (derived from fields Project Memory already
   computed — no second lookup).
6. **Operational Intelligence** → **Project Ecosystem** →
   **Impact Analysis** → **Executive Decision** form a computation chain:
   each reads the previous layer's already-computed output (never
   recomputing relationships or scores), culminating in
   `GET /executive-decision` — a single deterministic answer to "¿Qué
   sigue?" with a fixed, documented, additive point table (see
   `executive_decision/scoring.py`), never a learned or hidden weight.
7. **Mission Control** (`GET /mission-control`) composes Project
   Context + Workspace Advisor + Recent Activity + Daily Session +
   Executive Decision into the single "today" screen — this is the
   closest thing in the codebase to the target "answer all three
   questions immediately" experience, and it already exists.

## Role Dashboard

The real Dashboard is the FastAPI app under `dashboard/app`, served via
`uvicorn app.main:app` and rendered as a server-side Jinja UI (`app/
templates`, `app/static`) described in the docs as a "Command Center":
persistent sidebar, Home, Project page, Graph page, Advisor page, plus
newer additions (Mission Control, Explorer 2.0, Assets gallery) that are
not yet reflected in the written UI description in README.md.

Separately, **`project-dashboard.html`** at the repo root is a fully
self-contained single HTML file (128 lines, inline `<style>` + inline
`<script>`, Spanish-language UI: "Mapa de proyectos") that stores its own
project catalog in the browser's `localStorage`, with hardcoded seed data
including a literal path `C:\Users\rolev\My Drive (rolevc@gmail.com)\1 -
IA PROJECTS` baked into a JS constant (`const ROOT=...`). It has no
connection whatsoever to the Python app: no shared data, no shared code,
no link between the two in any doc or router. It reads as a quick,
hand-built "index card wall" for Role's own use, built independently of
(and perhaps before or in parallel with) the FastAPI Dashboard's Mission
Control/Explorer, which increasingly cover the same conceptual ground
("what are all my projects/tools and what do I do with them") through
automated discovery instead of manual entry.

## State and Context Management

- **Discovery state**: not persisted as "truth" — Workspace caches the
  last scan (`workspace_scan_cache`) purely to avoid re-scanning on every
  request; Discovery itself is stateless and re-derives everything from
  the filesystem each run.
- **Session/context state**: `app/session/` owns "Start/End My Day" and
  the project registry (its own SQLite file, `role_os_session.db`, under
  `var/` — explicitly excluded from `samples/` because it's real user
  data, per `config.py`'s inline comment).
- **AI Sessions + Snapshots + Resume Engine + Project Timeline**
  (`routers/pi/ai_sessions.py`, described in `main.py` as "ROLE OS v1.4
  Context Engine") is the actual persistent record of "which
  conversation/tool a project's work lives in" — one new table added on
  top of the existing `role_os_projects.db`, migrated from v1.3's AI
  Workspace data by a tracked migration in `app/projects/db.py`.
- **Cross-repo context** (other Role Ecosystem projects' own decisions)
  is deliberately *not* imported or duplicated: `app/session/
  decisions_adapter.py` only reads a sibling repo's `DECISION_LOG.md`
  live if `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` is explicitly set, else it
  falls back to a hardcoded, explicitly-labeled snapshot of five decisions
  as of 2026-07-30 (`FALLBACK_DECISIONS` in that file) — meaning the
  "recent ecosystem decisions" card can silently show eight-week-old,
  frozen data if that env var was never configured for the current
  machine/session.

## Project Management

"Projects" exist at two levels that are explicitly kept separate:
1. **Discovered projects** — anything Discovery finds on disk, no
   persistence beyond the scan cache.
2. **Adopted/Project-Intelligence projects** — `app/projects/db.py` +
   `routers/pi/projects.py`, with Workspaces, Capabilities, Dependencies,
   a Health Score engine, and (v1.3/v1.4) an AI Workspace + AI Sessions
   layer, all in `role_os_projects.db`.
Project Ecosystem (`app/project_ecosystem/`) then computes a relationship
graph across adopted projects from deterministic evidence only (shared
assets, PI dependencies, documentation cross-references) — with a small
manual-override table (`relationship_overrides`) for dismissing false
positives or confirming missed relationships, never storing the graph
itself.

## AI / Agent / Automation Components

There is **no AI/agent runtime in this codebase** — no Anthropic/OpenAI
SDK usage, no HTTP calls to any LLM provider, confirmed by grep across
`dashboard/`, `builder/`, `scripts/`, `tests/`. The word "Claude" appears
only as: (a) the *destination* the Resume Work / AI Launcher features open
a browser tab to (`https://claude.ai`, alongside ChatGPT and Gemini, in
`app/services/resume.py`'s `ASSISTANT_HOMEPAGES` and `app/routers/
launcher.py`); (b) a dependency check for the `claude` CLI binary in
`app/workspace/launcher.py` (checks `where.exe claude` resolves, per its
own comment referencing `@anthropic-ai/claude-code`); and (c) test fixture
data referencing "Anthropic" as a vendor entity in the Knowledge Graph
(`builder/extractors/entities.py`'s hardcoded vendor list, `test_graph_
builders.py`). Every module's own docstring independently asserts "no
LLM/no AI API call" — this is a stated, deliberate, and (per grep)
actually-honored product decision, not an oversight.

## Data Storage

Two families of SQLite databases exist side by side and must not be
confused:
- **`samples/role_os_sample/00_SYSTEM/*.db`** — fixture data, the
  *default* path `config.py` points at when no env var overrides it
  (`role_os.db` here contains just one table, `knowledge_cards`).
- **`var/role_os_alpha/*.db`** and **`var/role_os_dashboard/*.db`** — real
  runtime data from actually running the app (`role_os_alpha` holds
  `workspaces/projects/capabilities/capability_consumers/dependencies`;
  `role_os_dashboard` holds the workspace/assets/ecosystem overlay DBs
  plus generated asset thumbnails under `asset_thumbnails/`).
`var/discovery_reports/documents/` also holds a pre-generated
`documents_audit.json`/`.md` pair from a prior Discovery run — evidence
the Discovery Engine has a reporting/export mode not obviously wired to a
current router (see UNKNOWN below).

## External Integrations

None at the network level. The only "integration" points are filesystem
reads of sibling repositories, and all are optional/env-var-gated:
`ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` (reads `role-ecosystem/
DECISION_LOG.md`), `ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR` (writes a generated
Markdown daily note into an Obsidian vault), and the brand-new
`.role-os/project-status.json` manifest convention (in-flight,
uncommitted) that lets *any* sibling repo publish structured status for
Discovery to read without Role OS needing to know that repo's internal
layout in advance.

## Startup / Runtime Flow

`Start ROLE OS.bat` → resolves its own directory → calls
`scripts/Start-RoleOS.ps1`, which: checks whether `http://127.0.0.1:8000`
is already healthy (avoids double-starting); resolves a Python
interpreter (prefers a local venv); resolves all five
`ROLE_OS_*_DB_PATH` variables as absolute paths anchored to the repo root
(explicitly *not* to `dashboard/`, even though uvicorn's cwd is
`dashboard/` — called out in the script's own header comment as a
deliberate gotcha); refuses to start if the Knowledge DB is missing;
starts `uvicorn app.main:app --host 127.0.0.1 --port 8000` as a minimized
background process; waits for health; opens the browser. `Stop ROLE OS.bat`
/`scripts/Stop-RoleOS.ps1` presumably reverses this (not read in full, but
consistent with the shared `scripts/RoleOS.Common.ps1` helper).
`CREATE_DESKTOP_SHORTCUT.ps1` at the repo root creates a shortcut to the
`.bat`. `scripts/run_alpha.bat`/`.sh` and `scripts/seed_alpha_demo.py`
appear to be a second, "alpha demo" startup path pointed at
`var/role_os_alpha/*.db` instead of the sample DBs — its exact relationship
to the primary Start/Stop scripts was not fully traced (see UNKNOWN).

## Dependencies

- Root `requirements.txt` aggregates `dashboard/requirements.txt` plus
  `pytest>=8.0,<9.0` and `httpx>=0.27,<1.0` for the test suite.
- `dashboard/requirements.txt`: `fastapi>=0.111`, `uvicorn[standard]>=0.30`,
  `pydantic>=2.7`, `jinja2>=3.1`, `python-multipart>=0.0.9`,
  `Pillow>=10.0,<12.0` (image handling — used by Assets OS thumbnails).
  No ORM, no async task queue, no external DB driver: everything is
  stdlib `sqlite3`.
- `builder/requirements.txt`: none — standard library only, by design
  (stated in `builder/README.md`).
- `pyproject.toml` declares `testpaths = ["tests", "dashboard/tests",
  "builder/tests"]` and `pythonpath = ["dashboard", "builder"]` — the test
  suite genuinely spans all three roots; `black`/`ruff` are configured
  (line-length 100, target py310), consistent with `.ruff_cache/` present
  at repo root.

## Documentation vs Reality

- **Confirmed gap**: `README.md` and root `ARCHITECTURE.md` describe the
  system through roughly "Epic 4 / Sprint 8" (Command Center UI,
  Settings) and list "Features" that stop at the Knowledge Graph/Advisor/
  Command Center. Grep for "Mission Control", "Project Memory", "Resume
  Work", "Assets OS", "Project Ecosystem", "Impact Analysis", "Executive
  Decision", "Operational Intelligence" across `README.md`,
  `ARCHITECTURE.md`, `QUICK_START.md`, `INSTALLATION.md` returns **zero
  hits** in README/QUICK_START/INSTALLATION, and only incidental hits in
  `ARCHITECTURE.md`/`DEMO.md`/`CHANGELOG.md`. `config.py`'s own
  `app_version = "1.1.0"` has not been bumped despite five subsequent
  major domains shipping — version numbering has stopped tracking reality.
- **Docs that *are* accurate**: `docs/architecture/09`–`21` (per-sprint
  reports) and `CHANGELOG.md`'s `[Unreleased]` section are current and
  detailed — e.g. the Executive Decision Engine's scoring table,
  Mission Control's new fields, and Explorer's new result type are all
  documented there in the same level of detail as the code comments.
  This means the *authoritative* docs exist, they're simply not the ones
  a first-time reader (README) or a returning Role (top-level
  ARCHITECTURE.md) would see first.
- **`docs/architecture/01_VISION.md`** still frames "done" as Builder →
  Dashboard → Command Center with Project Intelligence/Advisor/Graph —
  i.e. it is the same stale generation as README, not the newer sprint
  reports.
- No contradiction found where docs claim behavior the code doesn't have
  (the opposite problem — code outpacing docs — is the actual pattern
  here).

## Technical Debt

- **Version/doc synchronization has no enforced process**: nothing in CI
  or `CONTRIBUTING.md` (not fully verified) appears to force README/
  ARCHITECTURE.md/`app_version` updates alongside new domains, which is
  exactly how six domains went undocumented at the top level while
  per-sprint docs stayed perfect.
- **Two "alpha" vs "sample" data paths** (`var/role_os_alpha/*` vs
  `samples/role_os_sample/00_SYSTEM/*`) with separate seeding scripts
  (`scripts/seed_alpha_demo.py`, `scripts/run_alpha.bat/.sh`) alongside the
  primary `Start-RoleOS.ps1` flow — their exact relationship/lifecycle
  wasn't fully traceable from static inspection alone (flagged under
  UNKNOWN).
- **`ecosystem_decision_log_path` fallback staleness**: `FALLBACK_DECISIONS`
  in `decisions_adapter.py` is a hand-maintained snapshot dated
  2026-07-30; if the env var is never set (the default), the Session
  page's "recent ecosystem decisions" card will silently show
  increasingly outdated information with no staleness warning visible to
  the user in the code reviewed.
- **`var/discovery_reports/documents/documents_audit.{json,md}`** exists
  as generated output with no obviously corresponding current router —
  possible leftover from an earlier reporting feature or CLI invocation
  (`app/discovery/reporters.py`/`__main__.py` exist and likely produced
  it) not otherwise exposed in `main.py`'s router list.
- Heavy `__pycache__` presence throughout (`.pyc` for both cpython-312 and
  cpython-314) suggests the dev environment has been run under two
  different Python minor versions — not a bug, but worth noting for
  reproducibility.

## Duplication

- **`project-dashboard.html` vs the FastAPI Dashboard**: the clearest
  duplication in the repo — two independent systems both trying to be
  "the map of Role's projects," one manual/static (localStorage, hand
  entered), one automated (Discovery + Workspace + Mission Control).
  No shared code or data path between them was found.
- **`app/services/resume.py` vs `app/workspace/resume.py`**: *not*
  duplication despite similar names — verified by reading both:
  `services.resume` is pure conversation-URL-resolution transport,
  `workspace.resume` is the higher-level orchestration that calls into
  it plus `project_memory`. This is intentional layering, explicitly
  explained in both files' docstrings (the refactor history is spelled
  out: "Sprint C7.1... the prompt-building half of this module moved to
  `app.project_memory.prompt`").
- **`app/graph/` (Epic 3) vs `app/conversation_graph/` (Sprint 5)**: two
  separate, deliberately independent knowledge-graph engines over
  different data (Project/Advisor/Builder data vs. imported-conversation
  data) — documented in `main.py`'s comments as intentionally separate,
  not accidental duplication.
- **`builder/` vs `dashboard/`**: not duplicative — `builder/` is the
  offline, stdlib-only CLI that *produces* `role_os.db`; `dashboard/`
  only ever reads it. Confirmed via `ARCHITECTURE.md`'s explicit "two
  halves that never run as the same process" framing and by builder's
  own `README.md`.

## Obsolete or Abandoned Components

- **`New folder`** at repo root — empty, no files, clearly stray/junk
  (likely created accidentally in Explorer and never cleaned up).
- **`RELEASE_NOTES_v1.0.md`** — superseded by `RELEASE_NOTES_v1.1.0.md`;
  kept for history, not obsolete exactly, but not linked from README's
  current narrative.
- **`FINAL_RELEASE_CHECKLIST.md`** — reads as a one-time pre-release
  artifact; unclear if it is still consulted for future releases or was
  a checklist for the v1.0/v1.1 cut specifically (UNKNOWN).
- **`var/discovery_reports/documents/`** — likely stale generated output
  from a past manual run of a reporting path not wired into the current
  UI (see Technical Debt above).

## Risks

- **Silent staleness in cross-ecosystem data**: the `DECISION_LOG.md`
  fallback and the general pattern of "read live if configured, else
  show an honest but frozen snapshot" is good engineering, but if Role
  never sets the env vars on a new machine, the Dashboard will quietly
  show months-old ecosystem context indefinitely with no visible warning
  in what was reviewed.
- **Two dashboards create ambiguity about where new project entries
  belong**: if Role continues hand-editing `project-dashboard.html`
  while the Python Dashboard's Discovery Engine also auto-finds the same
  projects, the two can diverge (one says a project is "Active," the
  other's Health Score says it's stale) with no reconciliation.
- **Version number (`1.1.0`) undersells the system**: anyone (including
  future Role or a new collaborator) reading `app_version`/README first
  will materially underestimate what exists, which is itself a "¿Dónde
  me quedé?" failure at the meta level — the docs don't know where the
  project left off either.
- **`New folder` and other stray root-level artifacts** signal the repo
  root is not being kept as tightly curated as `dashboard/app/` — a
  minor but real signal of drift risk as the ecosystem scales.

## KEEP

- `dashboard/app/main.py` and its router-registration comment style —
  the single best piece of institutional memory in the repo; every future
  domain should keep writing "what sprint, what it reuses, what new
  storage" inline exactly like this.
- `dashboard/app/config.py` — same discipline applied to storage; the
  best single file to read to understand the entire persistence model.
- `app/project_memory/`, `app/executive_decision/`, `app/mission_control/`
  — these three together already implement Role OS 2.0's three target
  questions; this is the core to build 2.0 around, not replace.
- `builder/` — stable, stdlib-only, self-contained; no reason to touch.
- `docs/architecture/*` numbered sprint reports — the accurate history;
  keep the numbering convention going forward.
- The deterministic/no-LLM constraint itself (`01_VISION.md`, enforced
  throughout) — a genuine, verified product decision, not aspirational.

## SIMPLIFY

- **README.md / ARCHITECTURE.md**: not wrong, just six sprints behind;
  needs a pass that pulls forward Mission Control/Project Memory/
  Ecosystem/Impact/Executive Decision from the sprint reports into the
  top-level narrative docs, and bumps `app_version`.
- **The `samples/` vs `var/role_os_alpha/` vs `var/role_os_dashboard/`
  three-way data split**: functionally justified per-file, but a single
  short doc naming which one is "the real one for daily use" would remove
  ambiguity for anyone else touching the repo.
- **`app/services/` (2 files) vs domain-owned modules**: works, but as a
  catch-all namespace it risks becoming a dumping ground as more
  "transport-only" helpers get added — worth a one-line rule in
  `06_DEVELOPMENT_RULES.md` (not verified whether one already exists)
  about what belongs there.

## KILL

- **`New folder`** — empty, no content, no references found anywhere in
  code or docs; safe to remove once Role confirms it isn't a placeholder
  for something not yet checked in.
- **`var/discovery_reports/documents/`** generated artifacts — if
  confirmed to be a one-off manual run's output with no current consumer,
  safe to delete (regenerable by design, per the assets/discovery
  "always safe to delete, regenerated on demand" convention already used
  elsewhere in `config.py`).

## UNKNOWN

- **`assets/role-master/` (untracked, 2 PNGs)** — purpose not determinable
  from code; no router or module references this path. Likely brand
  assets Role dropped in manually; relationship to Assets OS
  (`dashboard/app/assets/`) not established.
- **`project-dashboard.html`'s authorship intent** — was it meant to be
  temporary scratch work, a deliberate lightweight alternative to the
  Python Dashboard, or an early prototype that predates Discovery/Mission
  Control and was simply never retired? Not determinable from the repo
  alone.
- **`scripts/run_alpha.bat/.sh` + `seed_alpha_demo.py`** — exact
  relationship to the primary `Start-RoleOS.ps1` flow (alternate demo
  environment? deprecated? actively used for onboarding?) not fully
  traced.
- **`FINAL_RELEASE_CHECKLIST.md`** — whether this is a living document
  reused per release or a one-time v1.0/1.1 artifact.
- **`.role-os/project-status.json` manifest convention** (in-flight,
  uncommitted `operational_manifest.py`) — whether any sibling repo
  (ROLE Commerce Factory, RoleValdez.com, ROLE_MASTER_FACTORY) already
  publishes one, or whether this is being built ahead of any producer.

## MISSING

- **A single, current "what exists today" document** that lists every
  domain/router actually mounted in `main.py` — today that list only
  exists implicitly, spread across `main.py`'s comments and 13 sprint
  report files.
- **A visible staleness indicator** on any data sourced from an
  optional/unset env var (ecosystem decision log, Obsidian vault) — the
  fallback exists, but nothing surfaces "this is a frozen snapshot from
  2026-07-30" to the end user in the UI layer (not verified in templates,
  flagged as likely missing).
- **Any explicit "which of these two dashboards is canonical" statement**
  — nothing in any doc addresses `project-dashboard.html`'s existence at
  all, let alone its relationship to the Python app.
- **Machine-readable manifest producers** on the sibling repos the
  Discovery Engine's new `operational_manifest` detector is designed to
  read — the consumer exists in this repo; whether any producer exists
  elsewhere in the Role Ecosystem is unknown (see UNKNOWN).

## Recommended Role OS 2.0 Core

Keep the FastAPI app and its layering exactly as-is; do not rewrite. The
minimal 2.0 core, grounded in what already works, is:
1. **Discovery** (filesystem truth) → **Workspace** (adoption/overlay) →
   **Project Context** (assembly) as the input layer — already stable,
   already covers "find every project without re-entering anything."
2. **Project Memory** as the canonical "¿Dónde me quedé?" answer — it
   already builds the resume prompt and picks the right AI session; 2.0
   should make this the *only* path into any project, deprecating manual
   catalogs like `project-dashboard.html` in favor of it.
3. **Operational Intelligence → Project Ecosystem → Impact Analysis →
   Executive Decision** as the canonical "¿Qué importa ahora?"/"¿Qué
   sigue?" chain — already deterministic, already scored, already
   surfaced through Mission Control's "TODAY" card.
4. **Mission Control** as the single landing screen answering all three
   questions at once — this literally already exists; 2.0's UI work is
   to make it the *first thing rendered*, not one endpoint among many.
5. **The `.role-os/project-status.json` manifest seam** (in-flight) as
   the integration point for the rest of the Role Ecosystem (ROLE
   Commerce Factory, RoleValdez.com, ROLE_MASTER_FACTORY, etc.) — finish
   this before building anything more elaborate for cross-repo awareness,
   since the consumer side is already built.
6. Retire or explicitly fold `project-dashboard.html`'s content (the
   hand-curated project list) into Workspace's adopted-projects overlay,
   so there is exactly one place Role edits "what is this project and how
   do I use it."

## Questions Requiring Role's Decision

- Is `project-dashboard.html` still in active use, or can its content be
  migrated into the Workspace overlay and the file retired?
- What is `assets/role-master/` for, and should it live under Assets OS's
  scanned/managed paths instead of sitting untracked at repo root?
- Is the `var/role_os_alpha/` "alpha demo" data path still needed, or was
  it a one-time onboarding/demo setup that can be removed alongside
  `scripts/run_alpha.*`?
- Should `README.md`/`ARCHITECTURE.md`/`app_version` be updated now (a
  documentation-only pass) before or after the in-flight
  `operational_manifest` detector work lands?
- Does any other Role Ecosystem repository (ROLE Commerce Factory,
  RoleValdez.com, ROLE_MASTER_FACTORY) already need to be taught to write
  `.role-os/project-status.json`, or is that still on Role's to-do list?
- Is `FINAL_RELEASE_CHECKLIST.md` meant to be reused for future releases,
  and if so, does it need updating for everything shipped since v1.1.0?

## Proposed Next Step

Do a **documentation-only pass** (no code changes): update `README.md`
and root `ARCHITECTURE.md`'s feature/domain lists to include Project
Memory, Resume Work, Mission Control, Project Ecosystem, Impact Analysis,
Executive Decision, Operational Intelligence, Dashboard 2.0, and Explorer
2.0 (all already implemented and tested), and bump `app_version` in
`dashboard/app/config.py` to match. This is low-risk, additive, and
immediately closes the single largest gap this audit found — the system
being materially ahead of what anyone reading the front door would
believe it can do.
