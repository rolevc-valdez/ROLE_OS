# 19 — Project Ecosystem Engine, Sprint C8: Completion Report

Scope executed: build the canonical Project Ecosystem Engine so ROLE OS
understands how adopted projects relate to each other — dependencies,
shared assets/knowledge/documentation/prompts/sessions, and blocking
relationships — from deterministic evidence only. No LLM, no embeddings,
no vector database, no AI API. No version bump, no commit, no tag.

## Architecture

One new package, `app/project_ecosystem/`, following the same
"composition over a new source of truth" discipline every prior sprint
this session established (Mission Control, Operational Intelligence,
Project Memory):

```
app/project_ecosystem/
    __init__.py       -- public entry points (compute_relationships, get_project_ecosystem)
    models.py          -- canonical Relationship shape + SUPPORTED_TYPES enum
    detectors.py        -- 8 pure detector functions, additive registry (ALL_DETECTORS)
    relationships.py     -- dedupe/conflict-resolution + manual-override application
    graph.py              -- in-memory adjacency + Impact Summary (no persisted graph)
    service.py             -- compute_relationships() / get_project_ecosystem() -- the two public calls
    db.py                   -- role_os_ecosystem.db: manual override overlay only
```

No detector owns evidence another domain already owns: Assets stays
canonical for asset identity/duplicates (`app.assets.service`), Knowledge
stays canonical for card content (`app.db`), ProjectContext stays
canonical for git/health/next-action, PI stays canonical for explicit
dependencies/capabilities. The Ecosystem Engine's own code only combines
reads from these into relationship records.

## Files created

- `dashboard/app/project_ecosystem/__init__.py`
- `dashboard/app/project_ecosystem/models.py`
- `dashboard/app/project_ecosystem/detectors.py`
- `dashboard/app/project_ecosystem/relationships.py`
- `dashboard/app/project_ecosystem/graph.py`
- `dashboard/app/project_ecosystem/service.py`
- `dashboard/app/project_ecosystem/db.py`
- `dashboard/app/routers/project_ecosystem.py` (`GET /project-ecosystem/{id}`)
- `dashboard/tests/test_project_ecosystem.py` (23 tests)

## Files modified

- `dashboard/app/config.py` — added `ecosystem_db_path` (same `var/`-relative
  convention as every other domain holding real user-generated overrides).
- `dashboard/app/main.py` — registered the new router.
- `dashboard/app/operational_intelligence/engine.py` / `rules.py` — new
  `rule_unblocks_dependents`, fed by a cheap `ecosystem_dependencies` bundle
  key (plain SQL, not the full ecosystem).
- `dashboard/app/project_memory/service.py` — new bounded `related_projects`
  section (`include_related_projects` cost knob, default `True`, `False`
  wherever the cheap/preview path already existed).
- `dashboard/app/workspace/resume.py` / `dashboard/app/routers/pi/
  ai_sessions.py` — wrapped the calls that now also compute Related
  Projects/Ecosystem in `app.assets.service.request_scope()`.
- `dashboard/app/explorer/service.py` — `project_hub()` gained an
  `ecosystem` section; `search()` gained `_search_ecosystem` and a new
  `RESULT_TYPES` entry (`"Ecosystem Relationship"`); `search()`'s whole
  body now runs inside `request_scope()` (fixes a pre-existing, unrelated
  double-asset-walk between `_search_assets` and the new ecosystem
  detector).
- `dashboard/app/assets/service.py` — **real bug fix**: `group_duplicates`
  only ever cleared `duplicate_group_id`, never (re)set it (see below).
- `dashboard/app/static/js/app.js` — Project Hub's new "Project Ecosystem"
  card grid (`phubEcosystemSectionHtml`); Cockpit's Project Memory card
  gained a "Related Projects" sub-section (`renderRelatedProjectsHtml`).
- `dashboard/tests/test_assets_os.py` — new regression test for the
  `group_duplicates` fix.
- `dashboard/tests/test_project_context_ui.py`,
  `dashboard/tests/test_cockpit_redesign_ui.py` — pre-existing tests
  updated for intentional Sprint C7.1 UI changes surfaced while running
  full regression this sprint (see Sprint C7.1's own report/CHANGELOG
  entry; unrelated to C8's own scope but caught in the same regression
  pass).
- `CHANGELOG.md`, `docs/product/DECISIONS.md`, `docs/product/
  CHANGELOG_PRODUCT.md`, `docs/architecture/07_ROADMAP.md`,
  `dashboard/README.md` — documentation.

## Relationship model

Every relationship (`models.make_relationship`) carries exactly:

`relationship_id, source_project, target_project, relationship_type,
confidence, evidence, detector, discovered_at, last_verified,
manual_override, status`

`relationship_id` is **deterministic** (a hash of source+target+type+
detector), not random — the same evidence always produces the same id, so
a manual override survives recomputation. `relationship_type` is always
exactly one of `SUPPORTED_TYPES`: `depends_on, uses, consumes, produces,
extends, shares_assets, shares_prompts, shares_documentation,
shares_knowledge, shares_sessions, blocks, blocked_by, related`.

## Detectors (evidence sources)

| Detector | Evidence | Relationship type(s) | Confidence |
|---|---|---|---|
| `detect_dependencies` | PI's explicit `dependencies` table | `depends_on` | 1.0 |
| `detect_dependencies` (derived) | dependency target's own blocked/at-risk/critical status | `blocks`, `blocked_by` | 0.85 |
| `detect_capabilities` | PI's `capabilities`/`capability_consumers` tables | `uses`, `produces` | 1.0 |
| `detect_shared_assets` | canonical Assets index's `duplicate_group_id` | `shares_assets` | 0.9 |
| `detect_shared_knowledge` | Knowledge cards' `people`/`applications`/`vendors`, soft-matched to a project | `shares_knowledge` | 0.6 |
| `detect_shared_documentation` | bounded (20KB) README/ROADMAP/CHANGELOG/TODO/NEXT_ACTION read, text-searched for another project's name | `shares_documentation` | 0.6 |
| `detect_git_remote_references` | git `remote_url` text-searched for another project's name/slug | `related` | 0.5 |
| `detect_shared_prompts_and_sessions` | latest Session Snapshot/AI Session text mentioning another project | `shares_prompts`, `shares_sessions` | 0.4 |
| `detect_sibling_projects` | two adopted projects sharing a parent folder | `related` | 0.3 |

Every relationship's `evidence` list names the specific fact behind it
(the dependency note, the matching filename(s), the tag value, the
mentioning file, the shared parent path) — never a bare score.

## Conflict resolution & manual overrides

`relationships.dedupe()` merges records sharing `(source, target, type)`
across detectors — evidence lists union, confidence keeps the higher
value. `role_os_ecosystem.db` (`db.py`) stores only manual dismiss/confirm
decisions, keyed by the relationship's own deterministic id; relationships
themselves are never persisted, always recomputed fresh from the
canonical domains on every request.

## Impact Summary

`graph.impact_summary()`: `affected_projects, shared_assets,
shared_documents, shared_prompts, shared_knowledge, shared_sessions, risk,
confidence`. Bounded to this project's **direct (1-hop) relationships
only** — no multi-hop traversal, no graph dump. `risk` is a fixed,
documented threshold rule (blocks-or-3+-dependents → high; blocked-by-or-
any-dependents → medium; any other relationship → low; none → none), not
a hidden score.

## API

`GET /project-ecosystem/{project_id}` → `relationships, dependencies,
consumers, blocks, blocked_by, shared_assets, shared_prompts,
shared_documents, shared_knowledge, shared_sessions, impact_summary`. 404
for an unknown project id.

## Project Detail integration

Explorer's Project Hub (`GET /explorer/project/{id}`) gained an
`ecosystem` key; the frontend (`renderProjectHubPage`) renders it as a
"Project Ecosystem" card grid (`phubEcosystemSectionHtml`) — Dependencies,
Consumers, Blocked By, Blocks (name lists, each linking to the related
project), Shared Assets/Prompts/Knowledge/Documentation (counts), and
Impact (risk badge + affected-project count + confidence). Clean cards
only, no graph visualization, matching the brief's explicit instruction.

## Mission Control / Operational Intelligence integration

New rule `rule_unblocks_dependents` (`operational_intelligence/rules.py`):
when a project other adopted projects explicitly depend on still has open
work, recommends completing it — e.g. *"Complete ROLE OS to unblock ROLE
Commerce Factory, RoleValdez.com"* — with every named dependent backed by
a real dependency edge in `evidence`. Reads only the cheap
`detect_dependencies` output (plain SQL against PI's `dependencies`
table), never the full ecosystem (which also runs filesystem/knowledge
scans) — preserving Operational Intelligence's own "no repeated scans"
contract regardless of what else runs in the same request.

## Explorer integration

New search result type `"Ecosystem Relationship"` (`_search_ecosystem`):
searching a project's name surfaces "Used by ..." results (its
dependents); searching a relationship keyword (`"shared assets"`,
`"depends on"`, `"blocks"`, etc.) surfaces every relationship of that
type, each linking to the other project.

## Project Memory integration

`build_project_memory` gained a `related_projects` field: `{dependencies,
consumers, recent_shared_decisions}`, each capped at 3 names — a small,
bounded section, never a graph dump, matching the brief's explicit
instruction. Cockpit's Project Memory card renders it under a "Related
Projects" heading when non-empty. `include_related_projects` defaults
`True` for the real Resume Work path, `False` for every cheap/preview path
(`preview_resume_state`, the per-session `/resume` endpoint).

## Performance

- **One whole-workspace pass per request.** `compute_relationships()`
  calls `all_project_contexts()` at most once per call and every detector
  operates on that same list; callers that already computed it (Mission
  Control's OI rule, Project Memory) pass it straight through.
- **`request_scope()` everywhere a filesystem walk could repeat.**
  `detect_shared_assets` walks assets via the canonical
  `list_all_assets()` — the same walk Dashboard/Mission Control/Explorer's
  own asset search already do. Every new call site that also needs
  ecosystem data (Resume Work, Cockpit's memory card, Explorer's
  `search()`/`project_hub()`) now runs inside `app.assets.service.
  request_scope()`, verified with a dedicated regression test
  (`test_no_duplicate_asset_walk_when_computing_ecosystem`).
- **Real workspace timing**: `GET /project-ecosystem/{id}` for each of the
  5 real projects (ROLE_OS, ROLE Commerce Factory, ROLE MASTER,
  ROLE_KNOWLEDGE_OS, role-ecosystem) responded in **~1.1-1.4s** — the
  dominant cost is the shared-documentation detector's bounded file reads
  across every adopted project, not the graph/dedup logic itself.

## Real bug found and fixed

Building `detect_shared_assets` surfaced that `app.assets.service.
group_duplicates` only ever **cleared** a record's `duplicate_group_id`,
never (re)set it. `list_all_assets` calls this function a second time on
records that already passed through it once (inside each project's own
`index_project_assets` call) — a file whose only duplicate lives in a
*different* project has group size 1 within its own project's pass
(correctly cleared to `None` there), and the old outer-call logic could
never restore it to the shared hash, contradicting `list_all_assets`'s own
docstring guarantee ("re-groups across every project's combined
records"). Fixed at the root (positively assign in both branches, not
just clear); covered by a new regression test in `test_assets_os.py`
(`test_list_all_assets_resolves_duplicate_group_id_across_projects`).

## Tests

- `dashboard/tests/test_project_ecosystem.py` — 23 tests: the canonical
  model (shape, deterministic id), every detector (dependencies,
  blocked-dependency derivation, capabilities, shared assets, shared
  knowledge, shared documentation), impact summary risk levels
  (high/none), manual overrides (dismiss/confirm/clear), the API (404 +
  full shape), Project Hub integration, Explorer search integration,
  Mission Control/OI integration, Project Memory integration, the
  adopted-only security boundary, and a no-duplicate-asset-walk
  performance regression.
- `test_assets_os.py` — 1 new regression test for the `group_duplicates`
  fix.
- Full suite: **1091 passed**, 0 failed.
- `ruff check` / `black --check`: clean on every touched file (only the
  pre-existing, repo-wide accepted `B008`/`BLE001` patterns remain,
  present before this sprint).
- `node --check app/static/js/app.js`: passes.

## Live verification (real workspace)

Ran against `C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS`.
For ROLE_OS, ROLE Commerce Factory, ROLE MASTER, ROLE_KNOWLEDGE_OS, and
role-ecosystem:

- `GET /project-ecosystem/{id}` returned real `shares_documentation`
  relationships among all five (their README/ROADMAP files reference each
  other by name) — e.g. ROLE_OS ↔ role-ecosystem, ROLE_OS ↔
  ROLE_KNOWLEDGE_OS, ROLE_OS ↔ ROLE Commerce Factory, role-ecosystem ↔
  ROLE MASTER — each `impact_summary.risk` correctly `"low"` (no
  blocking/dependent relationships exist between them today), confidence
  0.36-0.47.
- No dependency, shared-asset, or shared-knowledge relationships were
  fabricated where no PI dependency edge, duplicate asset, or matching
  knowledge tag actually exists — confirmed honest "None detected" cards
  for Dependencies/Consumers/Blocked By/Blocks on every one of the five.
- Browser-verified: opened ROLE_OS's Project Hub (`#/phub/{id}`) and
  confirmed the "Project Ecosystem" card grid renders exactly as clean
  cards (Dependencies/Consumers/Blocked By/Blocks/Shared Assets/Shared
  Prompts/Shared Knowledge/Shared Documentation/Impact), matching the
  brief's own mockup. Explorer search for "ROLE MASTER" correctly showed
  no "Ecosystem Relationship" group (it has no dependents today) — an
  honest empty state, not a forced result.
- No console errors from application code (one benign, pre-existing
  Chrome-extension messaging artifact unrelated to this app, also seen in
  prior sprints' live verification).

## Known limitations

- **No import/package-reference (source-code parsing) detection.**
  Parsing arbitrary source files for cross-project imports would require
  per-language parsers and a much larger security/parsing surface for
  comparatively low-confidence evidence; deliberately out of scope this
  sprint.
- **Shared-prompts/shared-sessions detection is a simple literal name
  mention**, not a semantic match — a project mentioning another's name in
  passing (not necessarily meaningfully related) can still surface a low-
  confidence (0.4) relationship. Documented, not hidden.
- **Manual overrides have no UI yet** — `POST`/`DELETE` endpoints for
  dismiss/confirm were deliberately not added this sprint (the brief asked
  for the *model* to support `manual_override`, not a full override
  workflow); `app.project_ecosystem.db.set_override`/`clear_override`
  exist and are tested, but only reachable today by calling them directly,
  not via HTTP.
- **`detect_shared_documentation`/`detect_git_remote_references` are
  literal-substring matches** on project display names — a very short or
  generic project name (below `_MIN_NAME_LENGTH_FOR_TEXT_SEARCH = 4`
  characters) is excluded from these two detectors entirely to avoid
  false positives, meaning a real short-named project's documentation
  relationships may go undetected by these two detectors specifically
  (other detectors are unaffected).

## Recommendation for C9

1. **Manual override HTTP endpoints** (`POST /project-ecosystem/{id}/
   relationships/{relationship_id}/dismiss` / `/confirm`) — the model and
   storage already exist; only the HTTP surface and a small UI affordance
   (a dismiss/confirm button on each ecosystem card) are missing.
2. **A lightweight, language-agnostic import/reference detector** — not
   full AST parsing, but a bounded text search for another project's
   package/module name inside a project's own dependency manifest files
   (`package.json`, `pyproject.toml`, `requirements.txt`) would close the
   "package references" evidence gap the brief calls out, at much lower
   risk/cost than source-code parsing.
3. **Surface Impact Summary inside Mission Control's Needs Attention**,
   not just Project Hub — a project with `risk: "high"` (blocking 3+
   dependents) is arguably as actionable as anything Operational
   Intelligence already surfaces there; today it's only visible by
   opening that project's own hub.
