# 11 — Project Boundary / Hierarchy, Sprint 3: Completion Report

Scope executed: fix project-boundary detection so the Workspace page
represents real project structure instead of a flat directory listing —
top-level project vs. nested repository/component vs. internal folder vs.
excluded vs. non-project — reusing the existing Discovery Engine and
Workspace Adoption unchanged, with no rewrite of the project domain.

## 1. Files created

```
dashboard/app/discovery/identity.py                # shared compute_item_id(), used by boundary + workspace
dashboard/app/discovery/boundary/__init__.py        # public surface: assign_boundaries, ITEM_KINDS, exclusions
dashboard/app/discovery/boundary/exclusions.py      # exclusion matching (exact/case-insensitive/glob/relative-path)
dashboard/app/discovery/boundary/exclusions_config.json  # one source-of-truth default exclusion list
dashboard/app/discovery/boundary/excluded_stub.py   # builds a DiscoveredProject for an excluded folder, no walk
dashboard/app/discovery/boundary/rules.py           # per-folder boundary heuristics (own markers, independence, etc.)
dashboard/app/discovery/boundary/hierarchy.py       # whole-scan corpus pass: assigns item_kind/parent/hierarchy
dashboard/tests/test_discovery_boundary.py          # 21 tests
dashboard/tests/test_workspace_hierarchy.py         # 16 tests
dashboard/tests/test_workspace_hierarchy_api.py     # 10 tests
dashboard/tests/test_workspace_hierarchy_ui.py      # 6 tests
docs/architecture/11_PROJECT_BOUNDARY_SPRINT3_REPORT.md  # this file
```

## 2. Files modified

```
dashboard/app/discovery/models.py            # + item_id/item_kind/parent_item_id/... fields on DiscoveredProject
dashboard/app/discovery/pipeline.py           # + PipelineStage.BOUNDARY
dashboard/app/discovery/scanner.py            # exclusion check before descending; excluded candidates flagged
dashboard/app/discovery/service.py            # excluded-stub path + assign_boundaries() call; extra_exclusions param
dashboard/app/discovery/reporters.py          # "Project Hierarchy" Markdown section + false-positive comparison
dashboard/app/discovery/__main__.py           # + repeatable --exclude
dashboard/app/discovery/detectors/constants.py # + pom.xml to TOP_LEVEL_MARKER_FILES
dashboard/app/discovery/detectors/markers.py  # + .sln recognized as a tech marker
dashboard/app/config.py                       # + discovery_extra_exclusions (comma-separated names/globs)
dashboard/app/workspace/db.py                 # + override_action/override_parent_id columns (idempotent ALTER)
dashboard/app/workspace/service.py            # discovery_id delegates to shared identity; list_hierarchy(); overrides
dashboard/app/workspace/models.py             # + WorkspaceItem hierarchy/override fields; + OverrideRequest
dashboard/app/routers/workspace.py            # + ?view= param; + /override, /override/clear
dashboard/app/static/js/app.js                # Workspace page: filter tabs, expand/collapse, Review overrides
dashboard/app/static/css/components.css       # + .u-pl-4, .workspace-filter-tabs
CHANGELOG.md, docs/product/DECISIONS.md, dashboard/README.md,
docs/architecture/07_ROADMAP.md, docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md
```

No file inside `app/projects/`, `app/advisor/`, `app/graph/`, or any
`/pi/*` router was touched. `role_os_projects.db`'s schema is untouched.

## 3. Project-boundary algorithm

**Identity.** Every discovered folder's `item_id` is
`sha1(root_path)[:16]` (`app/discovery/identity.py`), the same function
`app.workspace.service.discovery_id` now delegates to instead of keeping
its own copy — one definition, used by both layers.

**Per-folder evidence, not per-folder judgment.** `detectors.py`/
`classifier.py` already run per folder in isolation; boundary assignment
needs the *whole scan's* parent/child relationships at once, so it's a
corpus-level pass (`boundary/hierarchy.assign_boundaries`), run once after
every folder has been detected and classified — the same shape as the
already-existing `recommendation/container_override.py` pass.

**Top-level promotion** (`_assign_top_level`, per depth-1 folder): a
folder is promoted to `item_kind = "project"` if *any* of —

1. it has its own `.git` or tech-stack marker file, checked **at its own
   root only** (`rules.has_own_strong_markers` re-derives this via the
   same shallow, non-recursive check `scanner.py` already uses to decide
   whether to descend — see §5, the bug this caught);
2. it contains at least one nested folder that itself has its own markers
   (the `ROLE Commerce Factory` → two `RCOM-*-Adapter` case — solved
   generically, no name-specific logic anywhere in this codebase);
3. it has a README plus substantial internal structure: 3+ internal
   folders, or a roadmap/changelog (the `ROLE MASTER` case — a README
   alone, per the brief's negative list, is deliberately not enough).

**Child assignment** (`_assign_child`, per depth-2 folder under a
promoted parent):

- own `.git` → `repository`, unless it *also* clears a high independence
  bar (`rules.is_independent_despite_nesting`: own confidence ≥ 0.75, own
  git remote, and a roadmap/changelog) — in which case it's promoted to
  its own top-level project instead of being nested (§3's exception).
- own tech-stack marker (no `.git`) → `component`.
- name matches a known internal-structure pattern (`01_*`-style numbered
  prefixes, `docs`, `assets`, `src`, `tests`, `node_modules`, ... —
  `rules.INTERNAL_FOLDER_NAMES`/`NUMBERED_PREFIX_RE`), checked **after**
  the own-markers check above, so a numbered folder that happens to be
  its own repository is never forced into `internal_folder` (§4's "use
  the parent context and evidence", not the name alone) → `internal_folder`
  / `documentation` / `asset_library` depending on its own doc/asset
  signal.
- otherwise → `unknown` (needs review).

A depth-2 folder whose parent *wasn't* promoted (`_assign_standalone`)
falls back to evaluating itself the same way a depth-1 folder would, so a
real project buried inside an unrecognized container is never silently
dropped.

## 4. Exclusion mechanism

One source-of-truth file, `boundary/exclusions_config.json`: `exact_names`,
`case_insensitive_names`, `glob_patterns`, `relative_path_patterns`.
Defaults include common technical folder names (redundant with, but
independent of, `detectors/constants.py`'s `IGNORE_DIR_NAMES` — that set
gates the *inner file walk* of an already-admitted folder; this one gates
*candidate admission itself*) and `OTROS - no proyectos` by exact name, as
required. User extras: `Settings.discovery_extra_exclusions` (env
`ROLE_OS_DISCOVERY_EXTRA_EXCLUSIONS`, comma-separated names/globs — never
an absolute path) or the CLI's repeatable `--exclude`.

`scanner.discover_candidates` checks exclusion **before** deciding whether
to descend into a folder: an excluded depth-1 (or depth-2) folder is still
returned as a candidate (so it's reportable, with its reason) but its
children are never enumerated. `service.run_audit` then builds it via
`boundary.build_excluded_project` — a stub that never calls
`detectors.analyze_folder`, so an excluded folder costs a single
already-known directory-listing entry, not a filesystem walk.

## 5. A real bug this sprint caught and fixed

Initial version of `rules.has_own_strong_markers` read
`project.tech_markers` directly. That list comes from
`detectors/markers.py`'s *recursive* inventory walk — for a container
folder, it therefore also includes marker files belonging to its own
nested children. In a smoke test, `ROLE Commerce Factory` (no `package.json`
at its own root) scored `boundary_confidence = 0.85` instead of the
expected `0.35`, because its two adapters' `package.json` files leaked
into what was supposed to be "evidence of *its own* markers." Fixed by
re-deriving this check via the existing shallow, non-recursive
`detectors.has_own_strong_markers(path)` (the same function `scanner.py`
already uses for its own descend-or-not decision) instead of trusting the
deep-walked list — applied to both the top-level promotion check and the
child repository/component check in `hierarchy._assign_child`. Caught
before any test was written, by manually running the algorithm against a
synthetic tree shaped like the real workspace, per this sprint's own "no
fake data" discipline.

## 6. API / UI changes

- `GET /workspace/discovered` — **unchanged** when `view` is omitted
  (Sprint 2's flat contract, verified by a new regression test). New
  `?view=top_level|repositories|excluded|needs_review|all`: `top_level`
  (the Workspace page's new default) returns only top-level projects, each
  with an embedded `children` list and repository/component/documentation/
  asset-library/internal-folder counts — no second request needed to
  expand.
- `POST /workspace/discovered/{id}/override` (`top_level` |
  `attach_to_parent`) / `.../override/clear` — a user correction to the
  computed grouping, stored only in the overlay database. The computed
  `item_kind`/`parent_item_id` are never altered by it; the Review panel
  shows both the detected boundary and the active override side by side.
- Workspace page: four filter tabs, per-project child counts with an
  Expand action (indented child rows), and Review now shows detected
  boundary, parent, evidence, confidence, exclusion match, and the two
  override actions.

## 7. Migrations

Two nullable columns added to the existing `adopted_projects` table
(`override_action`, `override_parent_id`), via `ALTER TABLE ... ADD
COLUMN` wrapped to swallow SQLite's "duplicate column" error on repeat
runs — additive, no data loss, safe on both a fresh database and one from
before this sprint. No changes to `role_os_projects.db` or any Discovery
Engine persistence (it has none).

## 8. Tests and results

53 new tests, all real (no mocks — every test scans a synthetic folder
tree it creates itself, through the actual unmodified `run_audit`/
`app.workspace.service` code paths):

| File | Count | Covers |
|---|---|---|
| `test_discovery_boundary.py` | 21 | top-level detection (own markers / child-with-markers / substantial structure / bare-container-not-promoted), nested git repos, monorepo-style siblings, the independent-nested-project exception (both directions), numbered folders with the own-markers exception, exact/case-insensitive/glob/user exclusions, recursive-exclusion prevention, deterministic ids, real paths with spaces and parentheses, read-only guarantee, JSON serialization of the new fields |
| `test_workspace_hierarchy.py` | 16 | grouped/flat/excluded/needs-review views, overrides (set/clear/dangling-parent fallback), rescan persistence of adopted/ignored state, no duplicates across repeated rescans, deterministic ids across rescans, removed-folder and renamed-folder behavior, inline children embedding |
| `test_workspace_hierarchy_api.py` | 10 | the `?view=` HTTP contract, override endpoints (success/400/404), invalid view returns 400 |
| `test_workspace_hierarchy_ui.py` | 6 | filter tabs, expand/collapse, status badges, child-kind counts, Review's boundary detail and override actions present in the served JS |

Full suite: **771 passed, 0 failed** (`pytest -q` from repo root, up from
694 at the end of Sprint 2). `ruff check` and `black --check` run clean on
every file created this sprint (pre-existing files this sprint only
edited were left at their pre-existing style rather than reformatted
wholesale — see the completion report's quality-gates note). JavaScript
syntax validated with `node --check`. Live browser smoke test performed
against a real running server (see §9).

## 9. Real-workspace before/after comparison

Ran `python -m app.discovery audit --root "...\1 - IA PROJECTS"` and, live
in a real browser, `POST /workspace/rescan` against the same folder:

| | Before (Sprint 1/2, flat) | After (Sprint 3, `view=top_level`) |
|---|---|---|
| Rows in the default view | 17 | 4 |
| `ROLE_OS` | peer row | top-level project (confidence 0.75) |
| `ROLE Commerce Factory` | peer row | top-level project (confidence 0.6) |
| `RCOM-Printful-Adapter` | peer row | nested `component` under `ROLE Commerce Factory` |
| `RCOM-Shopify-Adapter` | peer row | nested `component` under `ROLE Commerce Factory` |
| `ROLE MASTER` | peer row | top-level project (confidence 0.25) |
| `01_BRAND_CORE` ... `09_ASSET_LIBRARY` (8 folders) | 8 peer rows | 8 nested `internal_folder` items under `ROLE MASTER` |
| `role-ecosystem` | peer row | top-level project (confidence 0.75) |
| `OTROS - no proyectos` | peer row (classified "Mixed Project") | excluded, not shown in the default view |

All nine required outcomes from the brief's acceptance-test list were
verified this way, live, against the real disk — not simulated:
`ROLE_OS`/`ROLE Commerce Factory`/`ROLE MASTER`/`role-ecosystem` each
appear exactly once as a top-level project; both RCOM adapters nest under
`ROLE Commerce Factory`; `ROLE MASTER`'s internal numbered folders never
appear as top-level; `OTROS - no proyectos` is excluded from the default
list; and the previously-adopted `ROLE_OS` record was neither duplicated
nor lost across the rescan (confirmed via the summary counts and the
Workspace page showing it still marked "Adopted").

## 10. Remaining false positives / manual-review items

- **`ROLE_KNOWLEDGE_OS`** did not auto-promote to top-level: it has a
  README but no ROADMAP/CHANGELOG, and its own numbered subfolders (e.g.
  `01_PROJECTS`, `02_PROMPTS`) apparently don't contain their own README/
  marker file, so the scanner's `is_candidate_signal` check never admitted
  them as candidates at all — meaning boundary assignment saw zero
  children and couldn't apply the "3+ internal folders" substantial-
  structure rule either. It correctly landed in "Needs review" with an
  honest reason, rather than being silently hidden or wrongly promoted.
  Demonstrated live: one click on "Treat as top-level project" in Review
  fixed it, and it immediately appeared in the Top-level projects tab.
- **`ROLE_OS_BUILDER`** (nested inside `ROLE_KNOWLEDGE_OS`) inherits the
  same ambiguity, for the same root cause, cascading from its parent.
- **Confidence-weighted needs-review is not implemented for `item_kind ==
  "project"`.** A container promoted only via the "contains a child with
  markers" rule (e.g. `ROLE Commerce Factory`, confidence 0.35-0.6) still
  appears directly in the Top-level projects tab — it is not additionally
  flagged in "Needs review" the way an `unknown`-kind item is. This was a
  deliberate scope decision (needs_review == `item_kind == "unknown"`
  only, kept simple and testable) rather than an oversight, but a future
  sprint could reasonably lower the threshold for review.
- **This sprint's exception rule
  (`rules.is_independent_despite_nesting`) has no real-workspace example
  to validate against** — nothing in `1 - IA PROJECTS` currently has a
  nested repo with its own remote/roadmap/changelog, so this path is only
  verified by synthetic tests (`test_nested_repo_with_strong_independent_
  evidence_is_promoted`), not live data. Worth re-checking once a real
  case appears.
- **The `Documents` folder run from Sprint 1's report was not re-verified
  this sprint** — the brief's acceptance criteria named only
  `1 - IA PROJECTS`, so that's the only real root this sprint's
  before/after comparison covers.

## 11. Recommended next sprint

Per `08_IMPORT_ENGINE_PROPOSAL.md` §19 and this sprint's own carry-overs:

1. **Health/Advisor wiring** (§12 of the original proposal) — now that
   real hierarchy exists, decide whether a nested component's health
   should roll up into its parent project's number, or stay separate.
2. **Confidence-weighted "needs review" for promoted-but-weak top-level
   projects** (§10 above) — surface `ROLE Commerce Factory`-style
   containers (promoted by the weaker "has a child with markers" rule
   alone) in "Needs review" too, not just fully `unknown` items.
3. **Notes/tags editing UI inside the Review modal** (carried over from
   Sprint 2's report — the API has supported this since Sprint 2, the UI
   still only reads them).
4. **Mission Control ranking view** (§13) — real hierarchy + health +
   confidence + move-risk data is now sitting in the cache, unused by any
   "what should I work on today" ranking yet.
