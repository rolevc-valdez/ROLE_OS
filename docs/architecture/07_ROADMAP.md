# 07 — Roadmap

This is a record of what has shipped, in order, and the seams left open
for what could come next. For full detail on any entry, see `CHANGELOG.md`
at the repo root — this page is the condensed map; the changelog is the
source of truth.

## Shipped

| # | Name | What it added |
|---|---|---|
| M1 | Knowledge API | `GET /health`, `/projects`, `/search?q=`, `/knowledge/{id}` over the Builder-generated SQLite DB. No AI features. |
| M2 | First usable dashboard | Web UI served at `/`: global search, project list, recent cards, card detail, timeline. New additive `GET /ui/recent`, `GET /ui/timeline`. |
| M3 | Knowledge Engine 2.0 | Modular extractor pipeline (`builder/extractors/`): summary, decisions/deliverables, todos, prompts, entities (people/apps/vendors/urls/files), relationships (`related_conversations`). New `VENDORS.json` index. |
| Epic 1 | Project Intelligence | First-class Workspaces, Projects, Capabilities, Dependencies, and a modular Health Score engine. New `/pi/*` API and Projects UI tab. |
| Epic 2 | AI Advisor | Eight deterministic rules recommending what to do next, each explainable (`reason`/`evidence`/`suggested_action`/`impact`). New `/advisor/*` API and Advisor UI tab. `AdvisorNarrativeProvider` seam introduced. |
| Epic 3 | Knowledge Graph | 12 node types, 12 relationship types, computed on demand from the other three databases — no new database. New `/graph/*` API and Graph UI tab with SVG visualization. |
| Epic 4 | Command Center | Full UI redesign: persistent sidebar/header, hash router, Home/Project/Graph/Advisor/Assets/Settings pages, reusable design system, `createGraphView()` factory. UI-only — zero new backend surface. |
| Alpha | Alpha demo | `scripts/run_alpha.sh` / `.bat` one-command setup + seed script (`scripts/seed_alpha_demo.py`) populating seven realistic demo projects across five workspaces, so the whole system is explorable without bringing real data first. |

Each entry after M1 was additive: every prior API endpoint and UI surface
was left unchanged, confirmed by a regression test in that entry's own
test suite (see `CHANGELOG.md` for the passing counts recorded at each
stage, e.g. "226/226 passing repo-wide" as of Epic 4).

## Open seams (not yet built, but explicitly designed for)

These are documented extension points in the current codebase, not
commitments or a scheduled backlog — treat them as "if this is ever
built, here's where it plugs in," not "this is planned":

- **`AdvisorNarrativeProvider`** (`dashboard/app/advisor/narrative.py`) —
  a `Protocol` for a future LLM-backed narrative provider that would
  improve *wording* of recommendation summaries/reasons without touching
  rule logic, scoring, or persistence. `DeterministicNarrativeProvider` is
  the only implementation today and the rules/scoring remain the source of
  truth for *what* to recommend regardless of which provider is active.
- **Graph Query Engine as a headless library** (`dashboard/app/graph/queries.py`)
  — every query function (`neighbors`, `shortest_path`, `impact_analysis`,
  `search_nodes`, and the named convenience wrappers) is a pure function
  over an already-built `Graph`, with no dependency on the API or
  dashboard, so a future AI provider or script could reason over the graph
  without going through HTTP.
- **`commits` Health Score signal** (`dashboard/app/projects/health/commits.py`)
  — implemented as a pure function but always returns unavailable, since
  no git integration is wired up yet. Adding one is "give this file a real
  data source," not a new signal to design.
- **Screenshots** — `README.md`, `dashboard/README.md`, and `DEMO.md` all
  note that real screenshots aren't bundled yet; the placeholder locations
  (`docs/screenshots/home.png`, `projects.png`, `advisor.png`, `graph.png`,
  `project_detail.png`) are already referenced and waiting to be filled in.
- **Keyboard shortcuts** — `DEMO.md` explicitly notes the Alpha has no
  custom shortcut layer yet; every interaction is click-driven.

## Guiding constraint for anything added next

Per [[01_VISION]] and [[02_PRINCIPLES]]: no external AI/LLM API call, no
new data store where a read/compute layer would do, additive namespacing
that never breaks a prior endpoint, and (for UI work) no new backend
surface unless the data genuinely doesn't exist yet. Any roadmap item that
would violate one of these should be treated as a deliberate, called-out
exception — not a silent departure from how every prior Epic was built.

## Where to go next

- [[01_VISION]] — the product vision this roadmap serves.
- `CHANGELOG.md` (repo root) — the full, detailed history behind this table.
- [[../product/CHANGELOG_PRODUCT]] — the product-facing view of the same history.
- [[../product/DECISIONS]] — why key choices were made along the way.
