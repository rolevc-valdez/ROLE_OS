# 20 — Impact Analysis Engine, Sprint C9: Completion Report

Scope executed: build the canonical Impact Analysis Engine so ROLE OS
answers "if this project changes, what else is affected?" — reading the
Project Ecosystem Engine's (Sprint C8) already-computed relationship
graph, ProjectContext, Assets, Knowledge, Operational Intelligence (Sprint
C6), and Project Memory (Sprint C7.1). No new relationship-detection
engine, no new graph, no LLM, no embeddings, no vector database, no AI
API. No version bump, no commit, no tag.

## Architecture

One new package, `app/impact_analysis/`, deliberately keeping `api.py`
inside the package itself (an explicit deviation from the
`app/routers/`-per-domain convention every prior sprint used, called out
in this sprint's own brief):

```
app/impact_analysis/
    __init__.py    -- public entry point (get_impact_analysis)
    models.py       -- canonical ImpactReport shape + RISK_LEVELS/IMPACT_CATEGORIES
    scoring.py        -- compute_overall_risk() / average_confidence() -- fixed thresholds
    service.py          -- get_impact_analysis() -- the one public call, plus traversal/effects helpers
    api.py                -- GET /impact-analysis/{project_id}
```

No detector, no graph, and no filesystem/database scan exists anywhere in
this package. Every read is a call into an already-canonical domain:
`app.project_ecosystem.graph` for relationships/traversal primitives,
`app.project_context.builder` for project identity/business_value/git,
`app.operational_intelligence` for existing recommendations.

## Files created

- `dashboard/app/impact_analysis/__init__.py`
- `dashboard/app/impact_analysis/models.py`
- `dashboard/app/impact_analysis/scoring.py`
- `dashboard/app/impact_analysis/service.py`
- `dashboard/app/impact_analysis/api.py` (`GET /impact-analysis/{project_id}`, inside the package per the brief's explicit deviation)
- `dashboard/tests/test_impact_analysis.py` (27 tests)

## Files modified

- `dashboard/app/main.py` — imported and registered the new
  `impact_analysis.api` router.
- `dashboard/app/project_ecosystem/models.py` — **real bug fix**:
  `BLOCKING_STATUSES` incorrectly included `"critical"` (see below).
- `dashboard/app/project_ecosystem/detectors.py` — **real bug fix**:
  `detect_dependencies` no longer treats a target's computed health tier
  as equivalent to an explicit blocked/at-risk status (see below).
- `dashboard/app/operational_intelligence/rules.py` — new
  `rule_high_impact_change`, fed by the same cheap
  `bundle["ecosystem_dependencies"]` key Sprint C8's
  `rule_unblocks_dependents` already uses; does its own bounded
  dependents-traversal rather than calling the new engine.
- `dashboard/app/project_memory/service.py` — restructured to compute
  Operational Intelligence recommendations at most once per call
  (previously computed twice — see below), added a `potential_impact`
  field (`get_impact_analysis`, given the shared `operational_intelligence_recs`).
- `dashboard/app/explorer/service.py` — `project_hub()` gained an
  `impact_analysis` key; `search()` gained `_search_impact` and a new
  `RESULT_TYPES` entry (`"Impact"`); `_search_ecosystem` and the new
  `_search_impact` both now take an already-computed `relationships` list
  from `search()`'s single `compute_relationships()` call, rather than
  each computing their own.
- `dashboard/app/static/js/app.js` — Project Hub's new "Impact Analysis"
  card grid (`phubImpactAnalysisSectionHtml`); Cockpit's Project Memory
  card gained a "Potential Impact" line (`renderPotentialImpactHtml`).
- `CHANGELOG.md`, `docs/product/DECISIONS.md`, `docs/product/
  CHANGELOG_PRODUCT.md`, `docs/architecture/07_ROADMAP.md`,
  `dashboard/README.md` — documentation.

## Impact model

Every report (`models.make_impact_report`) carries exactly the brief's
suggested fields:

`project, generated_at, overall_risk, confidence, affected_projects,
direct_dependencies, transitive_dependencies, shared_assets,
shared_prompts, shared_documentation, shared_knowledge, shared_sessions,
operational_effects, release_effects, recommended_actions, evidence,
limitations`

Disambiguation worth stating explicitly: `direct_dependencies`/
`transitive_dependencies` name the projects **affected by** a change to
`project` — i.e. projects that depend on `project` (directly, or via a
further hop) — never what `project` itself depends on. This reading was
grounded in the brief's own worked example (changing ROLE OS affects ROLE
Commerce Factory and, transitively, RoleValdez.com) rather than the field
names alone, which could otherwise be misread either way.

## Risk model

`scoring.compute_overall_risk()` — five levels, each a fixed, documented
count threshold, never a hidden weighted score:

| Risk | Trigger |
|---|---|
| `critical` | 1+ already-blocked dependent (this project's own status/health is stalling a real dependent), or 5+ direct dependents |
| `high` | 3+ direct dependents, or (1+ direct dependent and 3+ transitive dependents) |
| `medium` | 1+ direct dependent, or 1+ shared-evidence relationship of any kind |
| `low` | transitive dependents only, no direct dependents, no shares |
| `none` | no dependency, blocking, or sharing relationships detected |

Every level's `reasons` names the exact counts that produced it (e.g.
`"3 project(s) directly depend on this one"`) — `evidence` on the full
report always includes these reasons plus every underlying relationship's
own evidence strings, so a risk level is never a bare label.

## Transitive analysis

`service._traverse_dependents()` — a breadth-first traversal over the
Ecosystem Engine's `depends_on` edges, reversed (who depends on this
project, then who depends on those dependents, ...), bounded to
`MAX_TRANSITIVE_DEPTH = 3` hops. A `visited` set keyed by project identity
(`canonical_project_id` / `item_id` / `display_name`, same key scheme C8's
own `impact_summary()` uses) guarantees:

- **No cycle is ever re-entered** — a synthetic 3-node dependency cycle
  (A→B→C→A) terminates cleanly with each project appearing exactly once.
- **No project is ever listed twice**, regardless of how many paths reach
  it.
- **Depth is honored** — a synthetic 5-hop chain surfaces only the first 3
  hops; a 4th-hop-only project is correctly absent from the report.

Verified directly against the brief's own worked example: a synthetic
ROLE OS → ROLE Commerce Factory → RoleValdez.com chain produces ROLE
Commerce Factory as a depth-1 (direct) hop and RoleValdez.com as a depth-2
(transitive) hop, both present in the resulting `ImpactReport`.

## API

`GET /impact-analysis/{project_id}` → the full `ImpactReport`. 404 (with a
descriptive detail message) for an unknown project id. No new query
parameters — every consumer either wants the full report or nothing.

## Project Detail integration

Explorer's Project Hub (`GET /explorer/project/{id}`) gained an
`impact_analysis` key; the frontend (`renderProjectHubPage`) renders it as
an "Impact Analysis" card grid (`phubImpactAnalysisSectionHtml`) directly
below the existing "Project Ecosystem" section: Overall Risk (badge +
confidence %), Affected Projects (clickable name list), Top Reasons (first
3 evidence strings), Recommended Actions (full list). Concise cards only —
no diagram, matching the brief's explicit instruction.

## Mission Control / Operational Intelligence integration

New rule `rule_high_impact_change` (`operational_intelligence/rules.py`):
when 2+ other adopted projects depend (directly or transitively) on a
project, recommends scheduling the change — e.g. *"Changing ROLE_OS today
will affect 3 project(s)"* — with every named affected project backed by
a real dependency edge in `evidence`. Deliberately reads only the cheap
`bundle["ecosystem_dependencies"]` key (plain SQL) and performs its own
bounded traversal locally, rather than importing/calling
`app.impact_analysis` — keeping Operational Intelligence's own "no
repeated scans, no heavier engine in the loop" contract intact regardless
of what else runs in the same request.

## Explorer integration

New search result type `"Impact"` (`_search_impact`): searching a
project's display name (e.g. `"ROLE_OS"`) surfaces one `"Impact of
changing ROLE_OS: medium risk"` result alongside its other matches
(commits, markdown, etc.), reusing the same `relationships` list
`search()` already computed for `_search_ecosystem` in the same request.

## Project Memory integration

`build_project_memory` gained a `potential_impact` field: `{overall_risk,
affected_count, affected_names (top 3), top_reason}` — a compact,
one-line summary, never a full report dump. Cockpit's Project Memory card
renders it as a "Potential Impact" line under "Related Projects" when
`overall_risk` is not `"none"` and at least one project is affected —
correctly suppressed for isolated projects. `include_related_projects`
(already existing from C8) gates this computation; the cheap preview path
(`preview_resume_state`) continues to skip it entirely.

## Performance

- **No repeated relationship detection.** Every consumer that already
  computed `all_contexts`/`enriched_items`/`relationships` in the same
  request (Project Hub, Project Memory, Explorer's `search()`) passes them
  straight through to `get_impact_analysis()`, which only computes them
  itself when called standalone (e.g. directly via the API).
- **No repeated Operational Intelligence pass.** A genuine double-call bug
  was found and fixed this sprint (see below) — `operational_intelligence_recs`
  is now threaded through as an optional parameter the same way
  `all_contexts`/`relationships` already were, computed at most once per
  `build_project_memory` call.
- **Real workspace timing**: `GET /impact-analysis/{id}` for each of the 5
  real projects (ROLE_OS, ROLE Commerce Factory, ROLE MASTER,
  ROLE_KNOWLEDGE_OS, role-ecosystem) responded well under 2s — dominated
  by the same shared-documentation detector cost already measured in
  Sprint C8, since this engine adds only in-memory traversal on top of an
  already-computed graph.

## Two real bugs found and fixed

1. **Health-tier/status conflation in the Ecosystem Engine's blocking
   detection.** Smoke-testing the brief's own worked example (ROLE OS →
   ROLE Commerce Factory → RoleValdez.com) produced `overall_risk:
   critical` instead of a sensible `medium`/`high`. Root cause:
   `project_ecosystem/models.py`'s `BLOCKING_STATUSES` tuple included
   `"critical"`, and `detectors.py`'s `detect_dependencies` separately
   checked `target_health.lower() == "critical"` — conflating an
   explicit, human-set `status` field with a *computed health tier*. A
   freshly-created PI project defaults to `health_score=0`, which buckets
   to tier `"critical"` under the existing 80/50 threshold convention —
   meaning nearly any brand-new project would be falsely flagged as
   "blocking" its dependents. Fixed by removing `"critical"` from
   `BLOCKING_STATUSES` (now `("blocked", "at_risk")` only) and removing
   the health-tier clause from `detectors.py` entirely, leaving only the
   explicit `status` check. Re-verified the brief's example now returns
   `medium`; re-ran `test_project_ecosystem.py` (23 tests, unaffected).
2. **Double Operational Intelligence computation in Project Memory.**
   `build_project_memory()` called `get_operational_intelligence()` (a
   full whole-workspace Epic 2 Advisor health-score refresh) twice per
   invocation once the new `potential_impact` field needed its own copy
   inside `get_impact_analysis`'s `_operational_effects` — once for the
   existing Operational Recommendation field, once inside Impact
   Analysis's internal call. Caught by a test-suite timing regression
   (a combined run of touched test files jumped well past its normal
   duration). Fixed by adding an `operational_intelligence_recs` optional
   parameter to `get_impact_analysis()`/`_operational_effects()` and
   computing it exactly once inside `build_project_memory()`, threaded
   into both the Operational Recommendation field and Impact Analysis.
   This is the same class of bug found in Sprint C7.1 (double Epic2
   Advisor refresh via `preview_resume_state` recursion) — the third time
   this session the "compute once at the outermost caller, thread down as
   an optional parameter" fix has been applied (C7.1, C8, C9), confirming
   it as this codebase's standing convention rather than a one-off patch.

## Tests

- `dashboard/tests/test_impact_analysis.py` — 27 tests: all five risk
  levels and their reasons, transitive traversal matching the brief's own
  example, cycle safety (a synthetic 3-node cycle), bounded-depth
  enforcement, shared-assets/documentation/knowledge detection, an
  unknown-project 404 (both the service function and the API), an honest
  empty report for an isolated project, Project Hub/Explorer/Mission
  Control/Project Memory integration, the adopted-only security boundary
  (unadopted discovered projects are ignored), and two dedicated
  performance regressions (no duplicate relationship detection, no
  duplicate asset walk when `relationships`/`all_contexts` are already
  provided).
- Full suite: **1118 passed**, 0 failed (confirmed via a fresh run after
  the double-OI-call fix, 254 of the touched-file tests passing in
  ~370s, then the complete suite in ~1107s).
- `ruff check` / `black --check`: clean on every file this sprint touched
  (fixed three `ISC004` implicit-string-concatenation findings in the new
  `_LIMITATIONS` list; the remaining `B008`/`BLE001` findings are the
  same pre-existing, repo-wide accepted patterns noted in the C8 report,
  present in files this sprint did not touch).
- `node --check app/static/js/app.js`: passes.

## Live verification (real workspace)

Ran against `C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS`.
For ROLE_OS, ROLE Commerce Factory, ROLE_KNOWLEDGE_OS, ROLE MASTER, and
role-ecosystem:

- `GET /impact-analysis/{id}` returned an honest `overall_risk: "medium"`
  for all five, driven entirely by real `shares_documentation` evidence
  (README/ROADMAP files referencing each other by name) — e.g. ROLE_OS's
  report named `role-ecosystem`, `ROLE_KNOWLEDGE_OS`, and `ROLE Commerce
  Factory` as affected, with `evidence` quoting the actual matching
  README lines.
- **No direct or transitive dependents were fabricated** for any of the
  five — this real workspace has no PI dependency edges declared today,
  so `direct_dependencies`/`transitive_dependencies` were correctly empty
  everywhere; only shared-evidence relationships (which do exist)
  contributed to risk. This is the expected, honest behavior for a
  workspace where dependency data hasn't been manually entered yet.
- Confirmed the API's 404 path for a nonexistent project id.
- Confirmed Explorer's Impact search: `q=ROLE_OS` (the project's actual
  display name) returned an `"Impact"`-type result, `"Impact of changing
  ROLE_OS: medium risk"`.
- Browser-verified: opened ROLE_OS's Project Hub (`#/phub/{id}`) and
  confirmed the "Impact Analysis" card grid renders directly below
  "Project Ecosystem" — Overall Risk (medium, 60% confidence), Affected
  Projects (3, clickable), Top Reasons, Recommended Actions — all
  populated with real data, no diagram. Opened Cockpit for ROLE Commerce
  Factory and confirmed the Project Memory card's new "Potential Impact"
  line: *"medium · 2 project(s) affected: role-ecosystem, ROLE_OS"*.
- No console errors from application code (one benign, pre-existing
  Chrome-extension messaging artifact unrelated to this app, also seen in
  every prior sprint's live verification).

## Known limitations

- **Transitive traversal follows only explicit `depends_on` relationships
  (Sprint C8), bounded to 3 hops** — a real but undeclared dependency (no
  PI dependency edge created for it) is not traversed, and a dependency
  chain longer than 3 hops is truncated (documented, not silently wrong:
  the report only ever claims what it actually traversed).
- **Shared-evidence detection inherits the Project Ecosystem Engine's own
  limitations** — no import/package-reference parsing; name-mention
  detectors (`shares_documentation`, `shares_prompts`, `shares_sessions`)
  are literal substring matches, not semantic.
- **Operational/release effects are read from each affected project's
  existing signals, never independently assessed** — `operational_effects`
  reuses each affected project's own Operational Intelligence
  recommendation verbatim; `release_effects` reuses `business_value`/git
  dirty-state already on `ProjectContext`. Neither computes a new
  judgment specific to the impact scenario itself.
- **No manual override / dismiss mechanism for a report's own conclusions**
  — unlike C8's relationships (which support dismiss/confirm via
  `role_os_ecosystem.db`), an `ImpactReport` is always freshly computed
  with no ability to annotate "this risk assessment doesn't apply here."
  Consistent with the brief (which asked for analysis, not an override
  workflow) but worth naming as a gap if usage reveals a need for one.

## Recommendation for C10

1. **Lightweight dependency-manifest scanning**, closing the same gap
   noted as a C9 candidate in the C8 report — a bounded text search for
   another adopted project's package/module name inside
   `package.json`/`pyproject.toml`/`requirements.txt` would let
   `direct_dependencies`/`transitive_dependencies` surface real,
   currently-undeclared dependencies without full source parsing.
2. **Surface `overall_risk: "critical"`/`"high"` projects inside Mission
   Control's Needs Attention**, not just each project's own hub — mirrors
   the same recommendation carried over from C8 for Impact Summary, now
   doubly relevant since Impact Analysis's risk levels are a strict
   superset of what C8's `impact_summary.risk` already computes.
3. **A `POST /impact-analysis/{id}/acknowledge`-style workflow** if real
   usage shows teams want to record "we reviewed this risk and accepted
   it" rather than re-seeing the same medium/high risk on every visit —
   deliberately not built this sprint per the brief's analysis-only scope.
