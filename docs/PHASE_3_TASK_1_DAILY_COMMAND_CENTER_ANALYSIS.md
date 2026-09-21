# Role OS 2.0 — P3.1 Daily Command Center Analysis

*Analysis / design only. No application code, runtime database, schema, Discovery root, adoption, or legacy component was changed. Canonical DBs were opened read-only (`mode=ro&immutable=1`); size/mtime of `role_os_workspace.db`, `role_os_session.db` and the external `role_os_projects.db` were identical before and after inspection.*

**Baseline verified:** Phase 2 COMPLETE (`20b80df`); Phase 3 was PLANNED — NOT STARTED at `a0ea71c`; P3.1 was the next authorized task; `main` == `origin/main`, tree clean; no discrepancy with the control files.
**Method:** every claim below comes from reading the actual code under `dashboard/app/`, the SQL schemas, and read-only queries against the real canonical data — not from documentation alone.

---

## Executive Summary

1. **Role OS already has most of a Daily Command Center.** `GET /mission-control` (the `/` landing page) already answers *Where did I leave off / What matters now / What's next / Can I continue*, with explainable `reasons`/`evidence`, staleness honesty, and a one-click Resume Work. The remaining work is mostly **presentation and classification**, not new engines.
2. **Canonical "Role Dashboard" = the existing Dashboard v2 view** (`#/dashboard`, `GET /dashboard/summary`) inside the same single-page app. "Open Role Dashboard" is an in-app link, not a second server or a new UI.
3. **What is genuinely missing (Category A):** (a) a *completed* status the system understands and excludes from ranking; (b) a **Domain** (KONTOOR / UNGER / ROLE PERSONAL / CLIENTES) + optional **Client** field; (c) a **Tool** representation; (d) a display-level split of Mission Control's data into *Active / Completed / Tools* groups with Domain filters.
4. **There is no true Task entity in use.** A `todos` column exists on `projects` but is empty in all 10 real rows. The honest label for v1 is **"Pending Work / Next Actions"**, not "Pending Tasks".
5. **"Urgent" and "Quick win" cannot be supported honestly today.** There is no due date/deadline anywhere; effort is a keyword guess on an action title. v1 should show only signals that are real (IMPORTANT, BLOCKED, STALE, PAUSED, plus a clearly-labelled *estimated* effort), and add URGENT only if Role starts recording a due date.
6. **`ROLE_PROJECT.md` is worth doing but is not first-version-critical** (Category B). Its highest-value use is Domain/Client/Type declaration for Claude-created projects; most other fields are already auto-discovered.
7. **Windows startup is largely already built** (`Start ROLE OS.bat` → `scripts/Start-RoleOS.ps1`: already-running probe, health check, port-conflict detection, canonical env paths, no admin). P3.7 shrinks to "register that launcher to run at login, with an off switch".
8. **Smallest path to daily use is 4 tasks, not 6** (see Recommended Sequence); the largest revised item is putting P3.2 (classification) first because P3.5 depends on it.

Side findings (disclosed, not acted on): the external projects DB contains test/duplicate rows (see §Existing Data Inventory); all 5 adopted projects have identical default `priority/business_value = medium`, so today's "importance" signal carries no information until Role sets them.

---

## Existing UI Inventory

Everything below is one FastAPI app and one SPA (`templates/index.html` + `static/js/app.js`, hash router). There is **one** dashboard-like frontend, not several servers.

| UI | Route | Purpose | Data source | Status | Unique value |
|---|---|---|---|---|---|
| **Mission Control** | `/` and `#/mission-control` (`renderMissionControlPage`; `GET /mission-control`) | Decision-and-continuation home: Where I Left Off / What Matters Now / What's Next, Needs Attention, portfolio strip, recent activity | `build_mission_control()` composing ProjectContext, Workspace portfolio, Operational Intelligence, Executive Decision, session, freshness | **ACTIVE — primary landing** | Already the daily entry point; explainable and stale-aware |
| **Dashboard v2** | `#/dashboard` (`renderDashboardPage`; `GET /dashboard/summary`) | Executive analytics: cards, Portfolio Status, health, recent activity, knowledge counts | `dashboard/service.py`: composes ProjectContext + workspace + advisor; no independent scoring | **ACTIVE — secondary** (demoted from nav in Phase 1 Task 8B, still routed; reachable via "See full metrics") | The detailed, visual, whole-portfolio view |
| **Workspace** | `#/workspace` (`GET /workspace/*`) | Discovery results: scan, adopt, ignore, override boundaries | `workspace_scan_cache` + `adopted_projects` | **ACTIVE — operational** | The Discovery/Adoption control surface |
| **Cockpit** | `#/cockpit[/{id}]` (`/pi/projects/{id}/…`) | Per-project AI sessions, timeline, project memory | `projects.db` `ai_sessions`, `ai_session_snapshots` | **ACTIVE — per-project** | Session/snapshot management |
| **Projects / Project Detail / Discovered detail** | `#/projects`, `#/project/{id}`, `#/dproject/{id}`, `#/phub/{id}` | Project lists and drill-down | `projects.db` + discovery | ACTIVE — drill-down | Detail |
| **Session** | `#/session` | Daily Session (start/end my day, prompt generation) | `role_os_session.db` | ACTIVE | Daily record |
| Knowledge / Explorer / Advisor / Graph / Knowledge Graph / Assets / Settings | `#/knowledge` … `#/settings` | Supporting capabilities | various | ACTIVE, supporting | — |
| Old "Command Center" Home | none (render function kept, no route/nav) | Superseded by Mission Control | — | **LEGACY, dead-routed** | none |
| `project-dashboard.html` | none (archived under `archive/legacy-dashboard/`, byte-identical) | Standalone static card board, `localStorage`, no backend | its own | **LEGACY** | Role's own taxonomy "Herramienta / Script / Repositorio" and a copy-`cd … && claude` action — directly relevant to the Tool model |
| Project Ecosystem / Impact Analysis / Executive Decision | API only (no sidebar entry) | Relationship graph, impact, ranking | — | Backend capabilities consumed by Mission Control | — |

## Canonical Role Dashboard Recommendation

**Recommendation: ROLE DASHBOARD = Dashboard v2 (`#/dashboard`, `GET /dashboard/summary`).**

Reasons:
- It is already documented in the code as "the deeper executive analytics view" beside Mission Control (`app.js` router comment: *"Dashboard remains the deeper executive analytics view"*), which matches Role's stated model: detailed visual validation of the ecosystem.
- It is a pure composition layer over the same ProjectContext everything else uses, so it cannot disagree with Mission Control.
- It needs no new UI — only a visible **OPEN ROLE DASHBOARD** entry point on the landing page (today it is a small "See full metrics" link) and, likely, a Domain filter.

Model (unchanged from Phase 3 scope, now grounded):

```
ROLE OS                    = the app / orchestration + daily entry point (this SPA, port 8000)
MISSION CONTROL            = the Daily Command Center (startup screen, `/`)
ROLE DASHBOARD             = Dashboard v2 view, opened from Role OS ("#/dashboard")
```

"Role Dashboard's colors" that Role likes = the shared design system in `static/css/` (`colors.css`, `components.css`, `layout.css`, `animations.css`), used by every view — so preserving it is automatic if the Command Center reuses those classes and adds no new CSS framework.

**Decision needed from Role (carried to Exact Next Task):** confirm Dashboard v2 is what Role means by "Role Dashboard". If Role instead means the old `project-dashboard.html` card board (colorful, manual), the alternative is folding its "Herramienta/Script/Repositorio" cards into the Tools area — not restoring it.

## Existing Data Inventory

Legend — Existing: YES/PARTIAL/NO · Reliable enough: YES/PARTIAL/NO.

| Concept | Existing? | Source (verified in code) | Reliable for v1? | Gap |
|---|---|---|---|---|
| Projects | **YES** | Discovery (`DiscoveredProject`) → `workspace.db: adopted_projects` (5 adopted) → `ProjectContext`; also `projects.db: projects` | **YES** for the 5 adopted | External `projects.db` has 10 rows incl. fixtures (`Role Test Project`, `Active Project`, `Paused Project`, `Quiet Project`) and a duplicate `ROLE Commerce Factory` — visible on the `#/projects` page; disclosed, out of scope |
| Tasks / pending work | **PARTIAL** | `projects.todos` (JSON, `open/done`) — **empty in all 10 rows**; snapshot `pending_work`; `next_action` extraction; OI recommendations | PARTIAL | No persisted task in use — see §Pending Work |
| Priority | **PARTIAL** | `adopted_projects.priority` (free text, default `medium`) | **NO (no information yet)** | All 5 adopted = `medium`; no validation of values |
| Urgency | **NO** | — (no due date/deadline field anywhere) | NO | Needs a due date, or omit URGENT |
| Importance | **PARTIAL** | `adopted_projects.business_value` (`critical/high/medium/low`, scored in Executive Decision) | PARTIAL | All 5 = `medium` today |
| Status | **PARTIAL** | `adopted_projects.status` free text default `active` (all 5 `active`); `projects.status` free text; `registry_projects.status` uses a *different* lifecycle vocabulary (`Build`, `Definition`, `Discovery`, `Active`); `ai_sessions.status` validated `active/paused/completed` | PARTIAL | Three vocabularies; no validation on the two project statuses |
| Completion | **NO** | No code recognizes `completed/done/closed` for a project (grep of scoring, OI, portfolio, advisor) | **NO** | See §Completed Projects |
| Next action | **YES** | `discovery/next_action.py: extract_next_action` — snapshot → `NEXT_ACTION.md` → `TODO.md` → ROADMAP → README → CHANGELOG → last commit; each with source + confidence | **YES** (honest, sourced) | — |
| Blockers | **PARTIAL** | Snapshot `blockers` text (empty in the one real snapshot); status `blocked`/`at_risk` (−15 points) | PARTIAL | Only if Role sets status or writes snapshots |
| Dependencies | **PARTIAL** | `dependencies` table (0 rows); Executive Decision derives dependencies from `project_ecosystem` graph relationships | PARTIAL | Inferred, not authored |
| Effort / quick-win signal | **PARTIAL (weak)** | `executive_decision/planner.estimate_effort_and_duration`: keyword match on action title → Low/Medium/High; `advisor.scoring.effort_from_count` | **NO** as a "quick win" claim | Heuristic on text; must be labelled *estimated* or omitted |
| Last activity | **YES** | `latest_activity`, git last commit, `data_freshness` | **YES** | — |
| Stale / neglected | **YES** | Executive Decision (≥30 days → −5), OI staleness rules, `data_freshness.is_stale` | **YES** | — |
| Project domain | **NO** | — | NO | See §Domain |
| Client | **NO** | — | NO | See §Domain |
| Tools | **PARTIAL** | Only in `PROJECT_REGISTRY.md` ("ROLE HERRAMIENTAS PERSONALES": Cobalt, yt-dlp) and a `capabilities` table (0 rows, project-scoped) | NO | See §Tool |
| Skills / scripts | **NO** | Discoverable as folders only if inside a Discovery root | NO | — |
| AI session / snapshot | **YES** | `ai_sessions` (6, all `active`), `ai_session_snapshots` (1) | YES | Sparse: 1 snapshot |
| Resume Work | **YES** | `workspace/resume.py: resume_work` + `execution_target.classify_execution_target`; `POST /workspace/discovered/{id}/resume-work` | **YES** | — |

## Project State Model

How Role OS represents things today:

- **Active project:** a discovered folder with `adopted_projects.adopted = 1`. Only adopted projects compete for recommendation (`executive_decision/service.py`: *"Only adopted projects compete"*).
- **Status:** free text, default `active`. Two independent, unvalidated copies (`adopted_projects.status`, `projects.status`).
- **Priority / business value / notes:** free-text priority, `business_value` enum-like, JSON notes — on the `adopted_projects` overlay.
- **Pending work / next action:** not stored on the project — derived at read time (snapshot `pending_work`, `next_action` extraction).

**Can Role OS TODAY reliably distinguish…**

| State | Answer | Evidence |
|---|---|---|
| ACTIVE | **YES** | default `active`; only adopted projects rank |
| PAUSED | **PARTIAL** | `paused`/`on_hold`/`archived` recognised as a −20 **penalty**, not an exclusion (the code says an all-paused workspace must still yield a recommendation) |
| BLOCKED | **PARTIAL** | `blocked`/`at_risk` recognised as −15 penalty; nothing sets it automatically |
| COMPLETED | **NO** | no code path knows it |

**Smallest missing semantics (not implemented):** treat `completed` (and only that new word) as a recognised terminal status that (1) is excluded from ranking and Needs Attention, (2) is shown in its own group. Keep the existing free-text field; add `completed` to the set of words the scorers understand. No new table.

## Pending Work / Task Model

| Candidate | Exists? | Honest to call "task"? |
|---|---|---|
| Persisted task entity | `projects.todos` JSON column (`open`/`done` item statuses per `CollectionItemCreate`) | It exists in schema but is **unused** (`[]` in all 10 rows) and lives on `projects.db`, not the adopted-project overlay Mission Control reads |
| Pending work inferred from session | Snapshot `pending_work` (1 snapshot) | No — free text |
| `next_action` | One string per project, sourced/confidence-tagged | No — it's a pointer, not a task list |
| Recommendations | OI/Executive Decision output | No — derived suggestions |
| TODOs in repos | `TODO.md`/`## TODO` read as *next_action* sources only (first lines) | No — not parsed as items |

**Answer:** the Daily Command Center **cannot honestly show "Pending Tasks" today.** Recommended least-misleading v1: label the section **"Pending Work / Next Actions"**, one row per active project showing its `next_action` (with source badge) and any snapshot `pending_work`. Introduce a real Task only if Role wants multiple tasks per project (Category C), and then reuse the existing `projects.todos` collection rather than a new table.

## Tool / Skill / Script Model

- No reusable-tool concept exists in runtime data. Cobalt and yt-dlp exist **only as prose in `PROJECT_REGISTRY.md`** (and a guide page committed in `e46c93d`).
- `capabilities` (project-scoped, 0 rows) means "a capability a project provides to other projects" — close in spirit but bound to a project and unused; `capability_consumers` models reuse across projects.
- The legacy `project-dashboard.html` used the taxonomy *Herramienta / Script / Repositorio* — Role's own vocabulary.
- Skills/scripts created in Claude Code (Kontoor/Unger) are just folders; they appear only if inside a Discovery root and would be classified as "project" by Discovery.

**Recommendation:** TOOL does **not** need to become a first-class table for v1. Represent a tool as an *adopted item with `kind = tool`* (a single additive attribute — see §Domain, same mechanism), so Discovery, adoption, Resume Work, notes and the Dashboard keep working, and "completed" never applies to tools. Cobalt (a URL, no folder) is the one case a folder-based item cannot hold; for v1 it can be a tool entry with a link/note or be left to a registry-backed list (Category B). Do not build a tools subsystem first.

## High-Level Domain Model

No existing field represents Domain or Client. Candidates evaluated:

| Existing field | Safe for Domain? |
|---|---|
| `adopted_projects.tags` (JSON list) | **No** — free text, shared with every other use; a domain typo silently orphans a project; can't enforce exactly-one |
| `projects.workspace_id` / `workspaces` table (7 rows) | **No** — these are Knowledge/PI workspaces, a different concept (and separate DB from the adopted-project overlay Mission Control ranks on) |
| `classification`, `technology_stack` | **No** — computed by Discovery about the folder, not about who the work is for |
| `PROJECT_REGISTRY.md` "Type"/section headings | Reference only — prose |

**Recommendation:** add **explicit, validated `domain`** (enum of the four) and **optional `client_name`** (required only when domain = CLIENTES) to the adoption overlay (`adopted_projects`), alongside the existing `priority/business_value/status` — an additive, nullable column pair following the exact pattern Sprint 3 already used for `override_action`. Unclassified items show as "UNCLASSIFIED" rather than being guessed. (Implementation is P3.2; not done here.)

**Proposed mapping for review — nothing written to runtime:**

| Project | Proposed Domain | Confidence / note |
|---|---|---|
| ROLE OS | ROLE PERSONAL | obvious |
| ROLE_KNOWLEDGE_OS | ROLE PERSONAL | obvious for the builder/personal side; the registry notes its knowledge cards reference Kontoor/Unger material — Role to confirm |
| ROLE Commerce Factory | ROLE PERSONAL | obvious |
| ROLE MASTER | ROLE PERSONAL | obvious |
| role-ecosystem | ROLE PERSONAL | obvious |
| role-content-factory, RoleSocialFactory, rolevaldez.com, bolsa-de-trabajo, charcos-site, desierto-creativo-site, agua-azul-app (registry, not adopted) | ROLE PERSONAL by default — **Role to confirm** | `charcos-site`/`agua-azul-app` may be client work (CLIENTES) — unknown from repo evidence |
| FERREVOLT | CLIENTES / client "Ferretería VOLT" | named by Role; not found among registry entries or adopted projects — not yet represented |
| Kontoor / Unger scripts and skills | KONTOOR / UNGER | none are adopted or in a Discovery root; the registry deliberately references corporate material without copying it |
| Cobalt, yt-dlp | TOOL (domain: ROLE PERSONAL) | registry section "ROLE HERRAMIENTAS PERSONALES" |

## Prioritization Signals

What Role OS can support **today with real data**, and what explains it:

| Concept | Supported today? | Real signal | Explanation source |
|---|---|---|---|
| IMPORTANT | **PARTIAL** | `business_value` (+25/+20/+10/0) and explicit `priority` | Executive Decision `reasons`/`evidence` (`"business_value = high"`) — but all 5 projects are `medium`, so it does not discriminate until Role sets values |
| URGENT | **NO** | none (no due date) | — |
| QUICK WIN | **NO (weak)** | title-keyword effort guess only | show as "estimated effort", never as a fact |
| BLOCKED | **PARTIAL** | status `blocked`/`at_risk` (−15); snapshot `blockers`; unmet dependency names in `dependencies.status` | `evidence` strings |
| WAITING | **NO** | no waiting concept (could be a status word) | — |
| STALE | **YES** | ≥30 days idle (−5); `data_freshness.is_stale`; OI staleness rules | `evidence` strings; UI already shows stale banner and discounted confidence |
| PAUSED | **YES** | `paused/on_hold/archived` (−20) | `"Project status is 'paused'"` |
| Has clear next step | **YES** | `next_action` with source + confidence | `reasons: ["has a next action (source: …)"]` |
| Recently active | **YES** | git/snapshot recency | `reasons` |

Every existing recommendation already carries `reasons`/`evidence` (`suggested_project_to_continue`, OI `evidence`, Executive Decision `reasons`), so **"WHY is this recommended?" is available for free** for IMPORTANT/BLOCKED/STALE/PAUSED/next-action. The UI must render those strings verbatim and must **not** invent URGENT/QUICK WIN badges. No new recommendation engine is needed; three engines already feed Mission Control (OI, Executive Decision, Workspace portfolio) — adding a fourth would worsen the existing overlap.

## Completed Projects

- **Is completion reliable?** No — there is no completion concept in the project model.
- **Is status enough?** Yes, if `completed` becomes a recognised value of the existing `status` field (see Project State Model).
- **Archived ≠ completed:** `archived` is currently grouped with *paused* (penalised, and OI even flags "paused project with pending work"). Completed means "done, celebrate, hide from daily priorities"; archived means "parked". Keep them distinct.
- **Are completed projects returned by Mission Control ranking today?** Yes, in the sense that a project with status `completed` is treated as unknown-status → scored like an active one (no penalty, no exclusion). Today nothing is marked completed (all 5 `active`), so no visible harm yet.
- **Minimal change to keep completed work out of recommendations:** (1) recognise `completed` in `executive_decision/scoring.py` and `operational_intelligence/rules.py` as *excluded* (not merely penalised, unlike paused); (2) have Mission Control's `portfolio`/`ranked_projects` output a separate `completed` group. Analysis only — not done.

## External Claude Projects

Goal: low manual maintenance; Role should not rewrite history.

| Information | How obtained |
|---|---|
| Folder location, git branch/last commit/dirty, health, technology stack, recent activity, `TODO.md`/`NEXT_ACTION.md`/README content, last-commit-based next action | **Already auto-discovered** (Discovery + `extract_next_action`) — zero manual work once the folder is discoverable |
| Purpose, current state summary, pending list, "how to resume" | **Claude can infer** by reading the repository (README, git log, TODOs) — this is what a generated manifest would capture |
| **Domain**, **Client**, project vs tool kind, **explicit priority**, "is it completed?" | **Must come from Role** (or be confirmed by Role) — cannot be inferred reliably, and Domain is exactly what Discovery cannot know |
| Tools used, AI context, notes | **Optional** |

**How they get in:** (1) reachable by a Discovery root → already discoverable, then adopted; (2) unreachable (e.g. `bolsa-de-trabajo`, Kontoor/Unger scripts) → explicit registration (P3.4). Corporate (Kontoor/Unger) repos need a deliberate decision because the project's own `PROJECT_REGISTRY.md` rule is to reference, never copy, corporate content.

## ROLE_PROJECT.md Findings

- **Needed?** Useful, **not required for the first Daily Command Center** (Category B). Without it, Domain/Client/kind can be set once per project in Role OS itself (P3.2 UI or field) — 4 fields, done once.
- **Where it earns its keep:** external Claude-created projects, where Claude can write the file once and Role OS can read it with no re-typing; and AI-provider independence (any tool can emit it).
- **Smallest useful manifest** (proposal only; schema **not** finalized): front-matter with exactly the fields Role OS cannot infer — `domain`, `client`, `kind` (project|tool), `status`, `priority` — plus free-text `Purpose`/`Next Action` sections that map onto what `extract_next_action` already reads (`NEXT_ACTION.md` outranks `TODO.md`; a `## Next Action` section fits the existing extractor pattern).
- **Fit with existing models:** the manifest's content maps onto the `adopted_projects` overlay + ProjectContext; it should be *read* by Discovery as one more evidence source (like `NEXT_ACTION.md`), never become a second source of truth that overrides Role's own edits (precedence rule needed — see decisions).
- Recommend: **DEFER** until Domain fields exist (P3.2) and explicit registration (P3.4) so the manifest has somewhere to land.

## Daily Command Center Data Contract

Proposed smallest contract — a **view over the existing `GET /mission-control` payload** plus the new fields; nothing to implement now. Source column shows the verified origin; GAP = must be created.

| Section / field | Source | Gap? |
|---|---|---|
| `generated_at`, `freshness` | `data_freshness` (`get_freshness`) | none |
| `recommended_now[]` (top 1–3, each with `project`, `why[]`, `next_action`, `confidence`) | `executive_decision.decision` + `ranked_projects` + `todays_focus`; reasons from Executive Decision `reasons/evidence` | none for content; **completed must be excluded (A)** |
| `resume_work` (per item: `can_continue`, action) | `resume_state` in ProjectContext + `POST …/resume-work`; `quick_actions` | none |
| `where_i_left_off` | `primary_focus`, `snapshot_continuity`, `since_last_time` | none |
| `active_work[]` (one row per active adopted project: name, status, next_action + source, `pending_work`, health, last activity, needs_attention) | `portfolio` strip (has `has_next_action` boolean only — needs the text) + ProjectContext `next_action`/`latest_snapshot` | **small: expose next_action text in portfolio strip (A)** |
| `quick_wins[]` | estimated effort from `planner` keyword heuristic | **weak — see below (B/C)** |
| `completed_projects[]` | adopted items with `status = completed` | **GAP (A)**: status not recognised/grouped |
| `tools[]` | items with `kind = tool` | **GAP (A)** for the concept; Cobalt/yt-dlp not in runtime |
| `domains` (per item `domain`, `client_name`; counts per domain) | — | **GAP (A)**: new fields |
| `dashboard_link` | `#/dashboard` (canonical, exists) | none (a button) |
| Per-item badges (`IMPORTANT`, `BLOCKED`, `STALE`, `PAUSED`) | `business_value`, status, staleness — from existing `reasons/evidence` | none |
| Per-item badges `URGENT`, `WAITING`, real `QUICK WIN` | — | **GAP (B/C)**: needs due date / waiting status / real effort |

Note: the contract can be assembled server-side in `build_mission_control()` (it already composes everything and its docstring says the frontend must do no joining) — extend that payload additively rather than adding another endpoint or router.

## Proposed Information Architecture

```
ROLE OS  ·  [ everything ]  [ KONTOOR ] [ UNGER ] [ ROLE PERSONAL ] [ CLIENTES ]      ⟳ data as of 2 h ago (stale?)
────────────────────────────────────────────────────────────────────────────────
WHAT SHOULD I DO NOW?                                    (reuses Executive Decision + Today's Focus)
 1. ROLE Commerce Factory                      [ROLE PERSONAL]   ● IMPORTANT
    WHY: business_value = high · has next action (NEXT_ACTION.md) · active 2 days ago
    NEXT: Implement productCreate + variant mutations…           [ CONTINUE ]  ← Resume Work
 2. …next                                                        [ CONTINUE ]
 3. …lowest estimated effort (est., not a promise)               [ CONTINUE ]

WHERE I LEFT OFF · CAN I CONTINUE?   (existing Where I Left Off card, snapshot continuity)
────────────────────────────────────────────────────────────────────────────────
ACTIVE / PENDING WORK                         │ COMPLETED
 name · domain · next action (source) ·       │ completed projects only, compact,
 STALE/BLOCKED/PAUSED badge                   │ never in the left column or ranking
────────────────────────────────────────────────────────────────────────────────
TOOLS                                         │ ROLE DASHBOARD
 yt-dlp · Cobalt · (kind = tool)              │  [ OPEN ROLE DASHBOARD ]  → #/dashboard
```

Rules: the domain chips filter the same payload client-side (no second request); an "UNCLASSIFIED" bucket appears until items are classified; empty states reuse Mission Control's existing honest empty-state messages; only existing CSS classes/tokens are reused.

## Required Gaps

**A — Required for the Daily Command Center**

| # | Gap | Smallest fix |
|---|---|---|
| A1 | No recognised **completed** status; completed work would still rank | Recognise `completed` in scoring/OI as excluded; group in payload |
| A2 | No **Domain** / **Client** | Additive nullable, validated `domain` + `client_name` on the adoption overlay |
| A3 | No **Tool** representation | `kind` (`project`\|`tool`) on the same overlay; tools exempt from completion/ranking |
| A4 | Portfolio strip lacks next-action **text** and grouping | Extend `build_mission_control()` payload additively (active / completed / tools) |
| A5 | Landing page lacks a prominent **Open Role Dashboard** and Domain filter | Presentation only, existing CSS |
| A6 | Real classification data: someone must set `domain` (and priority/business_value) for the 5 adopted projects, or every item is UNCLASSIFIED/medium | A one-time review step by Role (proposed mapping above), performed only when implementing P3.2/P3.5 |

## Optional / Deferred Gaps

| # | Gap | Class | Note |
|---|---|---|---|
| B1 | `ROLE_PROJECT.md` manifest | **B** | valuable for Claude-created projects; after A2/A3 exist |
| B2 | Explicit project registration (`bolsa-de-trabajo`) | **B** | flagged since Phase 2; needed for Role's real project set, not for the first screen |
| B3 | Due date → real URGENT | **B** | only if Role will maintain due dates |
| B4 | Windows login autostart | **B** | launcher already exists; last |
| B5 | Real Task entity (reuse `projects.todos`) | **C** | v1 uses "Pending Work / Next Actions" |
| B6 | Trustworthy QUICK WIN (real effort) | **C** | until then show only *estimated* effort or omit |
| B7 | WAITING status | **C** | a status word once validation exists |
| B8 | Validating/normalising the three status vocabularies | **C** | only what A1 needs |
| B9 | External-projects-DB test/duplicate rows | **D** | hygiene; not required for the Command Center |
| B10 | Advisor / OI / Executive Decision overlap, `pi_ai_workspace` deprecation, `var/role_os_alpha/` | **D** | remain deferred; unrelated to the daily screen |
| B11 | Consolidating Dashboard v2 / Cockpit / Workspace / Explorer | **D** | not needed; nav is already grouped |

## Recommended Phase 3 Implementation Sequence

Revised from the original P3.1–P3.7 using the evidence:

| # | Task | Change from original | Why |
|---|---|---|---|
| ~~P3.1~~ | Analysis (this document) | **DONE** | — |
| **P3.2** | **Classification & status semantics** — add `domain`, `client_name`, `kind`, and the recognised `completed` status to the adoption overlay; make scoring/OI exclude completed & tools; Role classifies the 5 adopted projects | Combines original P3.2 + the completion fix; **must precede the UI** | Every A-gap except A5 lives here; the screen cannot be honest without it |
| **P3.3** | **Daily Command Center UI** on Mission Control — extend `build_mission_control()` additively (`active_work`, `completed`, `tools`, `domain`), Domain chips, Open Role Dashboard button; reuse existing CSS | Was P3.5; moved up | Delivers daily value with the data that already exists; `ROLE_PROJECT.md` and registration are not prerequisites |
| **P3.4** | **Explicit project registration** (path, validate, review, adopt) | Was P3.4 | Brings `bolsa-de-trabajo` and other isolated projects into the screen; safe Discovery/Adoption separation |
| **P3.5** | **`ROLE_PROJECT.md` manifest** (read as an evidence source; fields = Domain/Client/kind/status/priority + purpose/next action) | Was P3.3; moved later | Only pays off once A2/A3 fields and registration exist |
| **P3.6** | **Windows login autostart** — register the *existing* `Start ROLE OS.bat`/`Start-RoleOS.ps1` (already-running probe, health check, port-conflict guard, no admin) at login with an enable/disable switch | Was P3.7; shrinks | Launcher already exists |
| ~~P3.6 (orig)~~ | Role Dashboard integration | **Folded into P3.3** (it is a button + Domain chip on the same app) | Not a separate task |

Optional after daily use is validated: B3 (due date → URGENT), B5 (real tasks).

## Exact Next Task

**P3.2 — Classification & Status Semantics (design-first).**
Scope: define, then (after Role approves the design) implement additively on the `adopted_projects` overlay: `domain` (KONTOOR | UNGER | ROLE PERSONAL | CLIENTES), `client_name` (when CLIENTES), `kind` (project | tool), and the recognised `completed` status; exclude completed/tool items from ranking; classify the 5 adopted projects using the mapping above **only with Role's confirmation**. No UI beyond what is needed to set the values; no manifest; no registration; no startup work.

**Decisions Role must make before/at P3.2:** (1) confirm Dashboard v2 = "Role Dashboard"; (2) approve the four-value Domain enum and `kind`; (3) confirm the domain of the five adopted projects (esp. `ROLE_KNOWLEDGE_OS`); (4) whether FERREVOLT / Kontoor / Unger projects should be adopted at all (corporate-content policy), which also decides how P3.4 treats them; (5) willingness to maintain a due date (B3).

**Not started:** P3.2 has not begun. No runtime data was written.
