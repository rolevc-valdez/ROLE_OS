# Role OS 2.0 Architecture Proposal

Status: proposal only. No runtime behavior, schema, or file layout has been changed as part of this document. All claims below are grounded in the current `dashboard/app/` codebase as of this writing (see file/symbol references throughout) and in `audits/ROLE_OS_1X_AUDIT.md`.

## Design Goal

Role OS must become dramatically simpler. Role Dashboard (the `dashboard/app/` FastAPI application) is the control center; Role OS is the orchestration brain behind it. Every time Role opens the system it must be able to answer, without hunting through chats, files, directories, repos, or apps:

1. ¿Dónde me quedé? (Where did I leave off?)
2. ¿Qué importa ahora? (What matters now?)
3. ¿Qué sigue? (What's next?)

The single most important user action is **CONTINUAR TRABAJANDO / RESUME WORK**. The finding of this analysis is that this loop is already substantially built — the work for 2.0 is mostly demotion, consolidation, and UI promotion, not new engineering.

## Core Mental Model

```
PROJECT  →  CURRENT STATE  →  CURRENT / NEXT ACTION  →  CONTEXT  →  RESUME WORK
```

Each stage already has a real, working implementation in `dashboard/app/`. Role OS 2.0's job is to make this chain the *entire* mental model presented to the user, and to push every other subsystem (ecosystem graphs, impact analysis, advisor, conversation graph, importers) behind it as supporting capabilities rather than parallel front doors.

## Current System vs Role OS 2.0

| Aspect | Current (1.x) | Role OS 2.0 |
|---|---|---|
| Entry points | ~24 routers (`dashboard/app/main.py` `include_router` calls) surfaced roughly as peers: dashboard, explorer, workspace, mission_control, project_ecosystem, impact_analysis, executive_decision, advisor, graph, imports, extraction, conversation_graph, session, launcher, settings, etc. | One landing screen (Mission Control) answering the 3 questions, with everything else reachable *from* it, not beside it. |
| "Where did I leave off" | Answered inconsistently across Mission Control, Project Memory, Daily Session — each with its own partial view | `build_project_memory()` (`app/project_memory/service.py`) is already the single assembler; 2.0 makes it the only one. |
| Data source of truth | Config defaults quietly point the canonical `projects.db` at a **fixture path** (`samples/role_os_sample/00_SYSTEM/`) while real runtime data (workspace, assets, ecosystem, session) already lives under `var/role_os_dashboard/`; a second parallel demo dataset exists under `var/role_os_alpha/` | One documented runtime data root (`var/role_os_dashboard/`), fixtures and demos clearly separated and never a production default. |
| Second dashboard | Untracked `project-dashboard.html` at repo root, a fully independent static app with its own project list and its own image assets (`assets/role-master/`) | Archived once its unique concepts (manual notes/tags, starter-prompt-to-clipboard) are folded into Workspace/Resume Work. |
| Docs | 21 numbered sprint-report files under `docs/architecture/` plus `docs/product/`, append-only, no single current-state file | Small, fixed doc set (see Documentation Source of Truth) where CURRENT_STATE.md and NEXT_ACTIONS.md are living files, not sprint logs. |
| Staleness handling | At least one confirmed silent-look fallback path (decisions log) where the backend *does* tag `source: "fallback"` but no UI surfaces it | Every fallback path's existing `source`/`note`/`as_of` metadata is rendered visibly, everywhere it reaches the user. |

## Minimal Core

Role OS 2.0's minimal core is exactly the five-stage chain, each backed by an already-real implementation:

1. **PROJECT** — `dashboard/app/discovery/models.py: DiscoveredProject` (filesystem-observed truth) + `dashboard/app/projects/db.py: projects` table (the canonical, adopted project) + `dashboard/app/workspace/db.py: adopted_projects` (thin adoption overlay: priority/business_value/status/tags/notes — deliberately does not duplicate discovery metadata, per its own schema and the module's design comments).
2. **CURRENT STATE** — `dashboard/app/project_memory/service.py: build_project_memory()`, specifically its `_where_we_left_off()` helper (prefers a human-authored Session Snapshot's `summary`/`accomplishments` over the last git commit, else "No prior activity recorded.") and the `latest_snapshot` field sourced from `ai_session_snapshots`.
3. **CURRENT / NEXT ACTION** — `_next_action_output()` and `_pending_work()` in the same file, which compose `app/discovery/next_action` (NEXT_ACTION.md → TODO.md → ROADMAP.md), the Operational Intelligence recommendation, and the Executive Decision Engine's scoring — already threaded into one field, computed once per call.
4. **CONTEXT** — `dashboard/app/project_context/builder.py: build_project_context()` / `all_project_contexts()`, the single shared composer that `dashboard`, `explorer`, `executive_decision`, `impact_analysis`, `mission_control`, and `operational_intelligence` all import, backed by one shared filesystem walk per request via `app.assets.service.request_scope()`.
5. **RESUME WORK** — `dashboard/app/workspace/resume.py: resume_work()` (Project → Project Memory → Resume Prompt → best AI Session via `app/project_memory/session_selection.py` → open conversation → copy prompt) plus `dashboard/app/workspace/execution_target.py: classify_execution_target()` (deterministic Claude Code / Claude web / ChatGPT web / user-choice routing based on classification, git status, technology stack, and requested-action keywords — no LLM call).

`dashboard/app/mission_control/service.py: build_mission_control()` (endpoint `GET /mission-control`) is the pre-existing composition of all three questions at once (`primary_focus`, `todays_focus`, `since_last_time`, `needs_attention`, `value_signal`, `daily_session`, `snapshot_continuity`, `quick_actions` including a `resume_work` action) — it is already, functionally, the Role OS 2.0 landing screen.

## Existing Components We Can Reuse

- `app/discovery/models.py: DiscoveredProject`, `app/discovery/detectors/registry.py` and detector pipeline — filesystem project detection needs no redesign.
- `app/projects/db.py` schema (`workspaces`, `projects`, `capabilities`, `capability_consumers`, `dependencies`, `ai_workspace`, `ai_sessions`, `ai_session_snapshots`) — this is already the canonical project/session/snapshot store.
- `app/workspace/db.py: adopted_projects` — correctly scoped as an overlay, not a duplicate project table.
- `app/project_context/builder.py: build_project_context` / `all_project_contexts` — the one shared context composer; every domain module already reuses it instead of recomputing.
- `app/project_memory/service.py: build_project_memory()` — the Current State / Next Action / Context assembler; explicitly designed (see its own docstrings) so fields never collapse into duplicate text.
- `app/workspace/resume.py: resume_work()` / `preview_resume_state()` — the actual Resume Work action, including the no-action guard (`requires_user_objective`) and Context Sufficiency Guard (`context_sufficient`, `missing_context`).
- `app/workspace/execution_target.py: classify_execution_target()` — deterministic execution-environment routing, already dogfooded against a real failure (ROLE Commerce Factory routed to a web assistant despite being a local repo).
- `app/mission_control/service.py: build_mission_control()` — the multi-question landing composition.
- `app/operational_intelligence` and `app/executive_decision` — deterministic, additive-point-table scoring already wired into `_next_action_output()`'s fallback chain; no ML, easy to keep.

## Components That Need Simplification

- **Project identity**: three separate id spaces exist today — Discovery's `item_id` (`app/discovery/models.py`), `adopted_projects.id` (`app/workspace/db.py`), and canonical `projects.id` (`app/projects/db.py`) — joined by soft matching (root path / case-insensitive display name), not a shared key. Additionally, Daily Session (`app/session/db.py: registry_projects`/`sessions`) predates canonical projects and is matched to a project by lower-cased display name in `project_memory/service.py: _current_objective()` ("there is no shared id space to join on," per its own comment). 2.0 should document this join rule explicitly as a known, permanent constraint — not silently patch a fourth id space on top.
- **Runtime data path defaults**: `config.py` defaults the canonical `projects.db` path to a fixture location under `samples/role_os_sample/00_SYSTEM/`, while workspace/assets/ecosystem/session data already correctly default under `var/role_os_dashboard/`. This is the single most load-bearing table pointed at a demo fixture by default — needs to be corrected to point at `var/role_os_dashboard/` before 2.0 ships (see Runtime Data Source of Truth).
- **Silent-fallback surfacing**: `dashboard/app/session/decisions_adapter.py: read_recent_decisions()` already returns `source: "fallback"` and a `note` field when `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH` is unset, falling back to a hardcoded `FALLBACK_DECISIONS` tuple frozen at 2026-07-29/30 dates — but no UI template currently renders that `source`/`note`. This is a UI-layer fix, not a new backend mechanism: render the existing honesty, everywhere a fallback-capable field reaches a screen.
- **Router surface**: ~24 top-level routers is too many parallel entry points for a "simple" system. Should be regrouped so most are reachable only as a drill-down from Mission Control / a Project page, not as independent nav items.

## Supporting Capabilities

- `app/project_ecosystem`, `app/impact_analysis` — feed the small, bounded "Related Projects" / "Potential Impact" sections of Project Memory (`_related_projects_and_impact()`); both already degrade gracefully to empty results when skipped (`include_related_projects=False`). Useful, not required for the 3 core questions to function.
- `app/assets` (Assets OS) — backs the shared filesystem walk (`request_scope()`) and ecosystem's shared-assets detector; real infrastructure utility, not a question-answering engine.
- `app/session` (Daily Session) — predates canonical projects; still feeds `current_objective` and Mission Control's `daily_session` card via a name-based soft match. Kept as supporting because of real legacy coupling, but its id-space mismatch with canonical projects is a wart, not a feature.

## Optional Capabilities

- `app/advisor`, `app/graph`, `app/conversation_graph` — independent recommendation/graph engines; nothing in the Core chain imports from them, only they import Core outputs. Useful exploration tools, not required for the daily resume loop.
- `app/imports`, `app/extraction` — ChatGPT conversation import + rule-based extraction, feeding the Advisor/extraction databases, not consumed by the Core chain.

## Legacy Candidates

- `app/discovery/reporters.py` and its output directory `var/discovery_reports/documents/` — generated report artifacts with no router currently calling them (confirmed: no `reporters` import in `main.py`'s router list). Candidate for removal or explicit re-adoption, not indefinite limbo.
- Root `project-dashboard.html` — see Dashboard Consolidation below.

## Dashboard Consolidation

`project-dashboard.html` is a fully standalone, single-file static HTML app (~129 lines), Spanish UI, using `localStorage` key `role-project-map-v1`, with a hardcoded absolute `ROOT` path constant baked into the file and zero fetch/XHR calls — it shares no code or data with `dashboard/app/`. It depends on a local image folder, `assets/role-master/` (two PNGs: `RM-000.png`, `rolevaldez_official.png`), referenced by relative path from its `roleMasterCard()` function — this resolves the audit's open question about that folder: it is not orphaned, it is `project-dashboard.html`'s own asset folder, unrelated to Assets OS (`dashboard/app/assets/`).

Unique features not in the FastAPI dashboard: manual project-card CRUD with rich-text (contentEditable) description/usage fields; a taxonomy in Role's own vocabulary ("Herramienta"/"Script"/"Repositorio"); JSON export/import backup; a special "ROLE MASTER" card with a copy-prompt-to-clipboard workflow tied to opening ChatGPT; and an "Administrar con Claude Code" button that copies a `cd ... && claude` shell command.

Duplicated functionality: both are fundamentally "list of my projects with status" — FastAPI's Explorer / Mission Control / Workspace already auto-discover the same real projects this file hand-enters.

Recommendation: **archivable**, but only after (a) any manually-curated notes/usage text worth keeping are copied into the matching adopted project's `notes`/`tags` (`adopted_projects` or `projects.notes`), and (b) `assets/role-master/`'s two PNGs are relocated under Assets OS or otherwise preserved — they are currently reachable only through this file. The "copy a starter prompt, then open in the right assistant" pattern is worth preserving conceptually — it is a manually-curated precursor to what `execution_target.py`'s routing already automates.

## Builder Decision

**Recommendation: (B) an import/ingestion subsystem.**

`builder/` is a stdlib-only CLI (`builder.py <chatgpt_export> <destination> [--clean]`, per its own README) that turns a ChatGPT export into a "ROLE Knowledge OS" folder plus a `role_os.db` (`knowledge_cards` table). `dashboard/app/config.py` defaults its `db_path` to read exactly this file's output path (`samples/role_os_sample/00_SYSTEM/role_os.db`). No dashboard code imports `builder/`'s Python directly — the only coupling is dashboard reading builder's *output file* by path. (Note: `app.project_context.builder` inside `dashboard/app/` is an unrelated module that happens to share the bare name "builder" — confirmed via grep that no dashboard code imports the top-level `builder/` CLI package.) This is a clean, decoupled producer for one specific optional data source and should stay a separate ingestion subsystem, not be folded into Core or treated as unrelated/legacy — dashboard's own default configuration depends on its output existing.

## Runtime Data Source of Truth

Current state (verified):
- `var/role_os_dashboard/` — the real, user-generated runtime data: `role_os_workspace.db` (adopted projects, scan cache), `role_os_assets.db` (asset cache/overrides), `role_os_ecosystem.db` (relationship overrides), and the session DB (`role_os_session.db`, per `config.py`'s own path comments, which explicitly warn this must never default into a path `.gitignore` would re-track).
- `samples/role_os_sample/00_SYSTEM/*.db` — fixture/demo data (`role_os.db`, `role_os_projects.db`, `role_os_advisor.db`, `role_os_imports.db`, `role_os_extraction.db`), regenerable via `builder/builder.py`. Also `samples/role_os_sample/04_KNOWLEDGE/*.json` and `samples/chatgpt_export_example/` (an import-pipeline test fixture).
- `var/role_os_alpha/*.db` (`role_os_advisor.db`, `role_os_projects.db`) — a second, parallel demo/alpha dataset, seeded by `scripts/seed_alpha_demo.py` / `scripts/run_alpha.bat`/`.sh`, not documented as distinct from `samples/`.
- `var/discovery_reports/documents/` — generated report artifacts, currently no consumer.
- `var/role_os_dashboard/asset_thumbnails/` — pure cache, explicitly safe-to-delete by the code's own comments.

**Proposal — one canonical runtime data root: `var/role_os_dashboard/`.**

1. `config.py`'s canonical `projects.db` path (currently defaulting into `samples/role_os_sample/00_SYSTEM/`) should default into `var/role_os_dashboard/` alongside workspace/assets/ecosystem/session DBs — today the single most important table is the one pointed at a fixture path by default. (This document proposes the change; it does not make it.)
2. `samples/` becomes exclusively fixtures/demo/test data — never a production default for any DB path.
3. `var/role_os_alpha/` should be either merged into `samples/` (if it's demo data) or deleted (if superseded) — it currently has no documented distinct purpose from `samples/role_os_sample/`.
4. Caches (`asset_thumbnails/`) and generated reports (`discovery_reports/`) are explicitly recreatable and can be pruned/regenerated freely; never treated as data to preserve.
5. Irreplaceable data is exactly what already lives under `var/role_os_dashboard/`: adopted-project decisions, notes, AI session history, snapshots, relationship overrides — anything a human typed in, not anything the Discovery Engine can re-derive by re-scanning the filesystem.

## Documentation Source of Truth

Current state: `docs/architecture/` holds 21 numbered, append-only sprint-report files (`01_VISION.md` through `21_EXECUTIVE_DECISION_SPRINT_C10_REPORT.md`); `docs/product/` holds `CHANGELOG_PRODUCT.md` and `DECISIONS.md`. There is no single "what's true right now" file — understanding current state requires reading the most recent numbered report and trusting it superseded the others.

Proposed small, fixed doc set (each file owns exactly one kind of information; no file repeats another's content):

- **README.md** — what Role OS is, how to run it, links to the rest. Never describes architecture or current state in prose.
- **ROLE_OS.md** — the concept/mental-model document: the five-stage core, the three questions, why they matter. Timeless; changes rarely.
- **ARCHITECTURE.md** — the current, single, living description of the system's structure (modules, data flow, CORE/SUPPORTING/OPTIONAL/LEGACY classification). Replaced in place as the system changes — never appended to. This document (`ROLE_OS_2_ARCHITECTURE_PROPOSAL.md`) is the seed for this file once decisions are made, not itself a permanent doc.
- **CURRENT_STATE.md** — a living snapshot: what's built, what's broken, what's in progress right now. Overwritten, not appended to — this is the machine/human answer to "¿Dónde estamos?" at the doc level, mirroring what Project Memory already does at the data level.
- **NEXT_ACTIONS.md** — the living backlog/roadmap of what's next, replacing the open-ended `07_ROADMAP.md`-style phase tracking. Overwritten as items complete, not appended to.
- **DECISIONS.md** — append-only log of architectural decisions and why (already exists at `docs/product/DECISIONS.md`; keep this one, do not create a second).
- **CHANGELOG.md** — append-only, dated list of what shipped (already exists as `docs/product/CHANGELOG_PRODUCT.md`; keep, rename/relocate only if consolidating locations).
- Specialized docs only where truly necessary (e.g. a data-model reference, this proposal's sibling `ROLE_OS_2_DATA_MODEL_PROPOSAL.md`) — not one file per sprint. The 21 existing sprint-report files should be treated as historical record (kept, not deleted) but not read as current-state truth going forward; `CURRENT_STATE.md` supersedes them for "what's true now."

## Proposed Runtime Flow

```
Discovery scan (filesystem)
        │
        ▼
DiscoveredProject  ──adopt──▶  adopted_projects  ──promote──▶  projects (canonical)
        │                                                          │
        └──────────────────────┬───────────────────────────────────┘
                                ▼
                   build_project_context()  (one shared walk / request_scope())
                                │
                                ▼
                   build_project_memory()   ── Current State / Next Action ──▶ Mission Control
                                │                                                     │
                                ▼                                                     ▼
                       Session Intent guard                                   quick_actions.resume_work
                                │
                                ▼
                          resume_work()  ──▶  classify_execution_target()  ──▶  Claude Code / Claude web / ChatGPT web
```

## Resume Work Flow

Unchanged from the existing, already-correct implementation in `app/workspace/resume.py: resume_work()`:

1. Look up the canonical project (`app/projects/db.py: get_project`).
2. Build Project Memory (`build_project_memory`) — the prompt's source of truth.
3. No-action guard: if Session Intent can't derive a trustworthy instruction, refuse and return `requires_user_objective: True` rather than guessing.
4. Context Sufficiency Guard: if the context package embeds zero real local resources but the target needs them, refuse and return `context_sufficient: False` with `missing_context`.
5. Select or create the best AI Session (`select_best_session`, `create_ai_session`), self-healing any stale "Resume Work"-titled session.
6. Classify the execution target (`classify_execution_target`) — deterministic, no LLM.
7. Build the resume prompt (`build_resume_prompt`) and resolve the conversation URL.

2.0's job here is purely making this the one obvious button on the landing screen — not re-architecting the flow.

## Migration Strategy

This is a proposal document; no migration has been executed. Recommended order once decisions are made:

1. Fix `config.py`'s canonical `projects.db` default path (fixture → `var/role_os_dashboard/`) — highest-leverage, lowest-risk single change.
2. Consolidate/retire `var/role_os_alpha/` once its purpose relative to `samples/` is confirmed with Role.
3. Surface existing `source`/`note`/staleness metadata (e.g. `decisions_adapter.py`'s fallback) in every template that renders a fallback-capable field.
4. Promote Mission Control to the literal landing route; demote the other ~24 routers to drill-downs reachable from it.
5. Copy any worth-keeping content out of `project-dashboard.html` and `assets/role-master/`, then archive both.
6. Replace `docs/architecture/`'s sprint-report-as-current-state pattern with the fixed doc set above; keep old sprint reports as historical record under an explicit `docs/architecture/history/` or similar, not deleted.

## What NOT to Build

- No new project-identity/id system — the existing three-way soft-matched identity (Discovery `item_id` / `adopted_projects.id` / canonical `projects.id`) should be documented and lived with, not replaced by a fourth scheme.
- No LLM-based execution-target classification — the existing deterministic rule in `execution_target.py` already works and is dogfooded; do not replace it with a model call.
- No new "state" or "memory" engine — `build_project_memory()` already is that engine; 2.0 should not stand up a parallel one.
- No enterprise-scale relationship/graph modeling beyond what `project_ecosystem`/`impact_analysis` already provide in bounded form.
- No new documentation sprawl — resist the urge to add a new `.md` file per feature; extend one of the fixed set instead.

## Decisions Required From Role

1. Confirm `var/role_os_dashboard/` as the single canonical runtime data root, and approve fixing `config.py`'s canonical-project DB default away from `samples/`.
2. Decide the fate of `var/role_os_alpha/`: merge into `samples/`, or delete outright.
3. Approve archiving `project-dashboard.html` once its manual content is copied over, and decide where `assets/role-master/`'s two images should live afterward.
4. Approve the router-surface simplification (Mission Control as literal landing route; other routers as drill-downs) — this affects navigation UX, worth Role's sign-off before implementation.
5. Approve the documentation consolidation (fixed file set vs. continuing numbered sprint reports going forward).
6. Decide whether `app/discovery/reporters.py` / `var/discovery_reports/` should be wired to a real consumer or removed as legacy.

## Recommended Phase 1

Scope Phase 1 to changes that are purely corrective/consolidating, not new capability:

1. Fix the canonical-project-DB default path (Migration Strategy step 1).
2. Surface `source`/`note`/staleness fields already returned by fallback-capable functions (e.g. `decisions_adapter.read_recent_decisions`) in the relevant templates.
3. Promote `build_mission_control()`'s existing output to be the literal app landing page.
4. Write `CURRENT_STATE.md` and `NEXT_ACTIONS.md` for the first time, seeded from this proposal and the latest sprint report, then adopt the "overwrite, don't append" discipline going forward.
5. Get Role's decisions on `var/role_os_alpha/`, `project-dashboard.html`, and `discovery/reporters.py` before touching any of them.

No code, schema, or file was created, deleted, or modified as part of producing this document, other than the two files listed as authorized deliverables.
