# Role OS 2.0 — Phase 3 Scope

## Status

**IN PROGRESS** (updated at P3.5 close — see *Executed Task Sequence* below; the rest of this document is the original scope, kept as written). Originally: documentation / scope definition only. No application code, tests, runtime databases, Discovery roots, adoptions, `var/role_os_alpha/`, or `pi_ai_workspace` were touched in writing this document. Implementation waits for Role's explicit authorization.

Baseline verified before writing: Phase 2 COMPLETE (checkpoint `20b80df`, see `docs/PHASE_2_COMPLETION.md`); `1546177` (pre-travel control-file checkpoint) is the only commit after it; `main` == `origin/main`, tree clean. Commits `229c1a7` / `e46c93d` (Cobalt / yt-dlp registry work) are parallel, out-of-scope, untouched. Phase 1 and Phase 2 must NOT be repeated.

## Product Vision

**ROLE OS 2.0 — DAILY COMMAND CENTER.** Role OS is the interface Role sees when starting the computer: pleasant, simple, colorful, immediately understandable, preserving Role Dashboard's current visual/color language where practical.

Primary success test: within ~30 seconds of Role OS opening, Role understands what is pending, what deserves attention, what can be finished quickly, and where to start. Phase 3 prioritizes **daily use over architectural expansion**.

## Daily Command Center

Landing experience, at minimum:

1. **What should I do now?** — small prioritized list. Signals (only where existing data supports them honestly): urgency, importance, blockers/dependencies, effort/ease, quick wins, stale/neglected work, explicit user priority. No opaque AI scoring. Every item shows WHY via badges: URGENT, IMPORTANT, QUICK WIN, BLOCKED, WAITING, STALE.
2. **Active / pending work** — active projects and actionable tasks.
3. **Completed projects** — separate area; never clutters daily priorities.
4. **Tools** — separate area for reusable tools (known: yt-dlp, Cobalt; future scripts/skills representable).
5. **Suggested start** — reuses existing Mission Control / Operational Intelligence / Executive Decision; **no new competing recommendation engine**.

Conceptual layout:

```
ROLE OS
WHAT SHOULD I DO NOW?   1. recommended  2. next  3. quick win   [CONTINUE]
ACTIVE / PENDING                         COMPLETED
TOOLS                                    ROLE DASHBOARD  [OPEN ROLE DASHBOARD]
Filters: KONTOOR | UNGER | ROLE PERSONAL | CLIENTES
```

## High-Level Work Domains

A first-class organizing concept (not a cosmetic label). Every managed item belongs to exactly one of:

1. **KONTOOR** — Freshservice projects, scripts, automations, Claude skills, other Kontoor work.
2. **UNGER** — Power BI, SolidWorks PDM, infrastructure/support, scripts/tools for Unger.
3. **ROLE PERSONAL** — Role OS, Role Dashboard, Role Content Factory, Bolsa de Trabajo, Role Master, other personal projects.
4. **CLIENTES** — FERREVOLT and future clients; carries a secondary **Client** name (e.g. Domain: CLIENTES, Client: Ferretería VOLT).

Corporate (Kontoor/Unger) content is referenced, never copied into Role OS (existing `PROJECT_REGISTRY.md` rule). **No bulk classification of existing projects is done in this task.**

## Project / Task / Tool Model

Three high-level object concepts to evaluate (no schema change now):

- **PROJECT** — has an objective/lifecycle; can be completed. (Role OS, FERREVOLT)
- **TASK** — a concrete actionable piece of work. (Fix Freshservice workflow)
- **TOOL** — reusable capability that stays available rather than "completing". (yt-dlp, Cobalt; a reusable Claude/Freshservice skill as TOOL or SKILL subtype)

Design rule: inspect existing models first (`discovery.models.DiscoveredProject`, `projects.db: projects`, `workspace.db: adopted_projects` with its priority/business_value/status/tags/notes, session snapshots) and choose the **smallest compatible extension**. Do not rebuild what exists. Observed while scoping: Cobalt/yt-dlp currently live only in `PROJECT_REGISTRY.md` ("ROLE HERRAMIENTAS PERSONALES"), not in any runtime model.

## Role Dashboard Relationship

Role Dashboard remains an important, non-obsolete part of Role OS.

- **ROLE OS** = orchestration brain + daily starting point.
- **ROLE DASHBOARD** = visual detailed view / validation dashboard for the ecosystem.
- Role OS landing gets a prominent **OPEN ROLE DASHBOARD** action. **Do not create another dashboard.**

Open question for P3.1 (observed, not resolved here): "Role Dashboard" is ambiguous in the repo — the FastAPI app under `dashboard/app/` (which `docs/ROLE_OS_2_ARCHITECTURE_PROPOSAL.md` calls "Role Dashboard, the control center"), its `/` page (`templates/index.html`, served by `routers/ui.py`), the Mission Control home, the other ~30 routers, and the archived legacy `project-dashboard.html`. P3.1 must identify precisely which existing route/UI is canonical and get Role's confirmation.

## External / Claude Project Ingestion

Many real projects (Kontoor scripts, Claude skills) were created directly in Claude Code, never passing through ChatGPT/Role OS. Role OS needs a way to import them without manually rewriting history. Workflow:

```
Existing Claude project -> Claude analyzes its repo -> generates/updates ROLE_PROJECT.md
 -> Role OS discovers/registers manifest -> Role OS understands project
 -> Mission Control / Role Dashboard can use it
```

AI-provider independent: Claude, ChatGPT, Codex, or manual development must be representable identically.

## ROLE_PROJECT.md Concept

*Update (P3.5):* re-scoped as an **optional** manifest for local folders only; the minimal schema is designed in `docs/PHASE_3_TASK_5_UNIVERSAL_INGESTION.md`, parser/import deferred. Work with no local folder is handled by P3.5's external managed work instead.

A lightweight manifest living inside an external project. **Schema is NOT finalized here.** Candidate sections: Project (Name, Domain, Client, Type, Status, Priority), Purpose, Current State, Pending, Next Action, Tools, AI Context, Notes. P3.3 designs the smallest useful version after inspecting existing models, and defines its relationship to Discovery, Project Context and Workspace.

## Explicit Project Registration

For isolated repositories unreachable by a broad Discovery root — known example `C:\Users\rolev\bolsa-de-trabajo`. **Do NOT scan `C:\Users\rolev`** (unrelated, sensitive/corporate material). Conceptual flow: Register Project (select/paste folder) → Role OS validates → discovers metadata / `ROLE_PROJECT.md` → user reviews → user explicitly adopts. **Discovery and Adoption stay separate.**

## Windows Startup Experience

Final objective: Windows login → Role OS backend starts safely → interface opens → Daily Command Center appears. **Implemented LAST**, only after the Command Center is validated for daily use. Planning constraints: no duplicate server processes; health check before browser launch; graceful failure; simple enable/disable; no dependency on sample data; canonical runtime paths; no administrator rights if avoidable.

## Proposed Phase 3 Tasks

| Task | Title |
|---|---|
| **P3.1** | Daily Command Center requirements / data gap analysis — what existing data already supports pending work, urgency, priority, completion, quick wins, next actions, tools, domain; identify only missing data |
| **P3.2** | Unified classification/model design — Domain, Project/Task/Tool, Client (when CLIENTES), status/completion semantics; map onto existing models first |
| **P3.3** | External Project Manifest design — `ROLE_PROJECT.md` and its relation to Discovery, Project Context, Workspace |
| **P3.4** | Explicit Project Registration — isolated repos (bolsa-de-trabajo) without widening Discovery |
| **P3.5** | Daily Command Center implementation — reuse Mission Control + Role Dashboard design language |
| **P3.6** | Role Dashboard integration — clear access to the canonical dashboard; no duplication |
| **P3.7** | Windows Startup — only after daily-use validation |

Order is proposed, not approved; each task needs Role's authorization.

### Executed Task Sequence (authoritative — supersedes the proposed table above)

| Task | Title | State |
|---|---|---|
| **P3.1** | Daily Command Center requirements / data gap analysis | COMPLETE (`2b7e83f`) |
| **P3.2** | Work classification (domain / client / kind) + `completed` semantics | COMPLETE (`62be54c`) |
| **P3.3** | Daily Command Center UI on Mission Control + Role Dashboard access | COMPLETE (`4822221`) |
| **P3.4** | Explicit Project Registration (isolated local folders, e.g. bolsa-de-trabajo) | COMPLETE (`2057ca5`) |
| **P3.5** | **Universal Project & Tool Ingestion** — evolved from "`ROLE_PROJECT.md` only": managed work may be local, Claude Web, ChatGPT, Chrome bookmark, GitHub, web or other; `source` (where it lives) is separate from `kind` (what it is) and `domain` (whose work). `ROLE_PROJECT.md` designed as optional, local-only; import deferred. See `docs/PHASE_3_TASK_5_UNIVERSAL_INGESTION.md` | COMPLETE |
| **P3.6** | Daily Use Validation & Real Work Onboarding — add a SMALL number of Role's real external projects/tools and validate the full daily experience | NEXT — not started |
| later | Windows Startup — only after P3.6 validates daily use | not scheduled |

## Success Criteria

1. Role turns on / logs into the computer.
2. Role OS becomes available automatically.
3. The first screen is understandable without navigating multiple modules.
4. Within ~30 seconds Role can answer: what is pending, what is urgent, what can be finished quickly, what to start with, which projects are completed, what tools exist, and which domain each item belongs to.
5. Role can open Role Dashboard from Role OS.
6. Existing Claude-created projects can be incorporated without their history having passed through ChatGPT.
7. Isolated projects can be registered safely without scanning broad sensitive directories.
8. The system still answers: Where did I leave off? What matters now? What's next?

## Deferred / Explicitly Out of Scope

Not automatically part of Phase 3 unless directly required by the Daily Command Center and separately approved: deleting `var/role_os_alpha/`; removing/deprecating `pi_ai_workspace`; redesigning Advisor (or resolving the Advisor/OI/Executive Decision overlap); new recommendation engines; another dashboard; adding many routers; adopting every discovered project; scanning the whole user home directory; rewriting Role OS architecture; features added merely because they are possible.

## Decisions Still Required Before Implementation

1. Role's go-ahead to start P3.1 (currently: wait for Role to return).
2. Which existing route/UI is the canonical "Role Dashboard" (see open question above).
3. Whether to keep the proposed P3.1–P3.7 order.
4. Domain assignment policy for existing projects (manual, manifest-declared, or suggested) — and who confirms it.
5. Whether TASK is a new persisted object or derived from existing signals (session snapshots, pending items).
6. Where TOOLs live (registry-only today) and whether SKILL is a TOOL subtype.
7. `ROLE_PROJECT.md` location/ownership rules and whether it is written by AI, by hand, or both.
