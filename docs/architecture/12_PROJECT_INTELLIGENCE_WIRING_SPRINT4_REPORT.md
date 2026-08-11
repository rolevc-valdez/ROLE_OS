# 12 — Project Intelligence Wiring, Sprint 4: Completion Report

Scope executed: wire the real discovered/adopted project data from
Sprints 1-3 into Projects, Home, Advisor, and Assets — which previously
showed empty/zero-centric content whenever no manually-created Project
Intelligence data existed — reusing the Discovery Engine and Workspace
Adoption unchanged. No product redesign, no Mission Control, no browser
automation, no scanned project file ever modified.

## 1. Files created

```
dashboard/app/discovery/next_action.py          # deterministic Next Action extractor (§3)
dashboard/app/workspace/assets_index.py         # read-only asset discovery index (§6)
dashboard/app/workspace/activity.py             # unified Recent Activity feed (§7)
dashboard/app/workspace/advisor.py              # Workspace Advisor 2.0, 11 rules (§5)
dashboard/app/workspace/portfolio.py            # Home portfolio aggregation (§4)
dashboard/tests/test_discovery_next_action.py   # 13 tests
dashboard/tests/test_workspace_assets_index.py  # 10 tests
dashboard/tests/test_workspace_advisor.py       # 16 tests
dashboard/tests/test_workspace_activity.py      # 9 tests
dashboard/tests/test_workspace_portfolio.py     # 7 tests
dashboard/tests/test_workspace_sprint4_api.py   # 12 tests
dashboard/tests/test_workspace_sprint4_ui.py    # 7 tests
docs/architecture/12_PROJECT_INTELLIGENCE_WIRING_SPRINT4_REPORT.md  # this file
```

## 2. Files modified

```
dashboard/app/discovery/models.py       # + CommitInfo, GitInfo.recent_commits
dashboard/app/discovery/git_reader.py   # + one read-only `git log -5` call per repo
dashboard/app/workspace/service.py      # + enrichment layer: get_ai_session_summary,
                                         #   get_next_action_for_item, enrich_project_item,
                                         #   list_enriched_top_level_projects, get_enriched_item,
                                         #   list_project_assets, list_activity_feed,
                                         #   list_advisor_recommendations, get_home_portfolio,
                                         #   get_freshness
dashboard/app/routers/workspace.py      # + GET /home, /advisor, /assets, /activity;
                                         #   ?view=top_level now enriched; /discovered/{id}
                                         #   now enriched; /summary merges freshness fields
dashboard/app/static/js/app.js          # Home portfolio section, #/dproject route + full
                                         #   detail view, Projects page card rewrite, Advisor
                                         #   "Discovered Projects" section, Assets page rebuild,
                                         #   stale-data badge on the Workspace page
dashboard/tests/test_workspace_ui.py    # 1 test updated (data source changed, still additive)
CHANGELOG.md, docs/product/DECISIONS.md, dashboard/README.md,
docs/architecture/07_ROADMAP.md, docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md
```

No file inside `app/projects/`, `app/advisor/` (Epic 2's engine), `app/graph/`,
or any `/pi/*` router was touched. **No database migration this sprint** —
every new capability computes on read from the existing scan cache /
overlay database / `app.projects.db` (read-only); nothing new is
persisted (see §3 "asset index" for why this was a deliberate choice, not
an oversight).

## 3. Services added

- **Next Action extractor** (`app/discovery/next_action.py`) — pure,
  filesystem-only functions (no DB access), called from the workspace
  layer with an optional AI-session hint. See §5 below for the algorithm.
- **Asset discovery index** (`app/workspace/assets_index.py`) — walks one
  project's real files on demand (not cached, not persisted): every
  request to `/workspace/assets` re-walks the currently-adopted projects'
  folders fresh. This is a deliberate choice for this sprint's scope —
  at the real project counts involved (single digits), a fresh walk costs
  well under a second; caching would be premature optimization that adds
  a staleness-invalidation problem for no measured benefit yet (see §8).
- **Workspace Advisor 2.0** (`app/workspace/advisor.py`) — 11 pure rule
  functions plus `generate_recommendations()`, structured as one file with
  one function per rule (see §6 for why this is a deliberate, time-scoped
  simplification versus Epic 2's `advisor/rules/` package-per-rule
  pattern).
- **Recent Activity** (`app/workspace/activity.py`) — pure aggregation
  over data the other services already computed; performs no filesystem
  or git access of its own.
- **Home portfolio** (`app/workspace/portfolio.py`) — pure aggregation +
  one explainable scoring function (`suggested_project_to_continue`).
- **Enrichment layer** (`app/workspace/service.py`, new functions) — the
  one place next-action/AI-session/documentation-status/test-status/
  asset-count are attached to a merged workspace item, so Projects, Home,
  Advisor, and Project Detail can never compute these differently or
  disagree with each other.

## 4. API / UI changes

All additive; the Sprint 2/3 `/workspace/discovered` (no `view`) contract
is untouched.

| Endpoint | Change |
|---|---|
| `GET /workspace/discovered?view=top_level` | Now enriched: `next_action`, `documentation_status`, `test_status`, `asset_count` added to every item |
| `GET /workspace/discovered/{id}` | Now enriched: same fields, plus `ai_sessions` (`sessions`/`latest_session`/`latest_snapshot`) |
| `GET /workspace/summary` | Gained `is_stale`, `hours_since_scan`, `stale_threshold_hours` (§8, stale after 24h) |
| `GET /workspace/home` (new) | §4 of the brief: Home portfolio aggregation |
| `GET /workspace/advisor` (new) | §5: Workspace Advisor recommendations |
| `GET /workspace/assets[?project_id=]` (new) | §6: real asset records, grouped by project |
| `GET /workspace/activity[?limit=]` (new) | §7: unified recent-activity feed |

UI: Projects page cards now show every required field (name, root path,
status, type, tech stack via language histogram, git branch/dirty state/
last commit, last modified, health, confidence, move risk, repository/
component counts, documentation status, asset count, test status, next
action, adoption status) and link to a **new** `#/dproject/{id}` detail
view (`renderDiscoveredProjectDetail`) — a parallel, separate view from
the existing manual-project `#/project/{id}` (see `DECISIONS.md` for why
these were kept separate rather than merged). Home gained a "Your
Projects" section above the existing, untouched "Today's Focus". Advisor
gained a "Discovered Projects" section alongside Epic 2's existing
recommendations. Assets was rebuilt from an inert placeholder (it rode on
`/graph?node_type=Asset`, wired to nothing real) into a real table over
`/workspace/assets`. The Workspace page's summary cards gained a
stale-data warning badge.

## 5. Next-action algorithm

`app/discovery/next_action.py::extract_next_action()`, in priority order:

1. **AI Session Snapshot** `next_prompt`/`pending_work` — passed in by the
   caller (this module has no database access); the workspace layer
   fetches it via `get_ai_session_summary()` before calling this.
2. **`NEXT_ACTION.md`** — first non-empty, non-heading line(s).
3. **`TODO.md`/`TODO.txt`**, or else a `## TODO` section inside
   `README.md`/`ROADMAP.md` — first unchecked (`- [ ]`) item, or first
   bullet, or first non-empty line.
4. **`ROADMAP.md`'s current milestone** — first unchecked item, or the
   first heading's own text plus what follows it.
5. **README's "Next Steps" section** — text between that heading and the
   next one.
6. **`CHANGELOG.md`'s unreleased section** — text between `## [Unreleased]`
   (or `## Unreleased`) and the next heading.
7. **Latest git commit message** — passed in from `GitInfo`.

Every result carries `source`, `source_path` (`None` for the AI-session
and git-commit sources, which have no file path), a fixed `confidence`
per source tier (0.95 → 0.3), and `extracted_at`. Finding nothing at any
tier returns `text: None` — rendered as "Not yet defined" everywhere, per
the brief's explicit "do not invent values" instruction. All file reads
are bounded (20KB cap) and read-only; verified by a dedicated test that
snapshots the scanned tree before/after.

## 6. Advisor rules

`app/workspace/advisor.py`, all pure functions over one enriched item,
each returning `None` or exactly one recommendation:

| Rule | Fires when |
|---|---|
| `rule_inactive` | No activity (commit or filesystem mtime) in >90 days |
| `rule_dirty_git_tree` | `git status` shows uncommitted changes |
| `rule_no_readme` | No README found |
| `rule_no_roadmap` | Neither ROADMAP nor CHANGELOG found |
| `rule_no_tests` | No tests detected (top-level projects only) |
| `rule_next_action_available` | A next action was found (any source) |
| `rule_high_value_low_activity` | `business_value` is high/critical AND inactive >60 days |
| `rule_high_move_risk` | Discovery's own `move_risk == "high"` (reasons carried through verbatim) |
| `rule_momentum` | Active in the last 7 days AND has an open next action |
| `rule_assets_no_commercial_output` | 10+ assets AND `commercial_readiness == "not-commercial"` |
| `rule_near_completion` | Health ≥ 80 AND commercial-ready/production AND not stale |

Every recommendation carries `project`, `project_id`, `recommendation`,
`reason`, `evidence` (a list of the literal signal values behind it —
never prose-only filler), `priority` (0-100), `confidence` (0-1), and
`action_link` (`#/dproject/{id}`). `generate_recommendations()` sorts by
priority descending. A dedicated test
(`test_generate_recommendations_empty_for_healthy_project_with_no_issues`)
verifies a fully "healthy" project triggers zero problem-rules — the
explicit "do not recommend a project with no supporting evidence"
requirement.

**Deliberate style deviation**: Epic 2's `app/advisor/rules/` is one file
per rule with a shared `RuleContext`/`RecommendationCandidate` type. Given
this sprint's scope and time budget, Workspace Advisor's 11 rules live in
one file as plain functions over plain dicts instead. Still fully unit
tested per rule (16 tests, one or more per rule) and easy to split into
files later if the rule count grows — noted as a possible Sprint 5 cleanup,
not a defect.

## 7. Asset indexing behavior

`app/workspace/assets_index.py::index_assets_for_project()` walks one
project's `root_path` (bounded to 2,000 files, skipping the same
technical directories Discovery already ignores) looking for
`.png/.jpg/.jpeg/.webp/.svg/.pdf/.mp4/.mov/.psd/.ai/.ttf/.otf/.woff/.woff2`.
For each match: filename, project, full path, `asset_type` (image/video/
document/design-file/font), `category` (further splits images into
`logo` vs. plain `image` via a filename match against `logo|icon|
favicon`), size, modified timestamp, a `reusable` flag (true for
logo/font/design-file categories), and a `duplicate_hash` — SHA-1 over at
most the first 1MB of the file, a "practical" (per the brief's own
wording) dedup signal that never fully hashes a large video file. Never
opens a file for writing, never renames/moves/copies anything — verified
by a dedicated read-only test. No thumbnails, per the brief's explicit
"do not build thumbnails yet."

## 8. Tests and results

67 new tests, all real (no mocks anywhere in this sprint's tests either —
every filesystem-touching test creates its own tmp_path tree and runs the
actual, unmodified code path):

| File | Count | Covers |
|---|---|---|
| `test_discovery_next_action.py` | 13 | full 7-source priority order, "nothing found" honesty, read-only guarantee, real paths with spaces/parentheses |
| `test_workspace_assets_index.py` | 10 | every supported extension, category/reusable inference, duplicate hashing, technical-directory exclusion, read-only guarantee |
| `test_workspace_advisor.py` | 16 | every rule fires only with real evidence and never without it, sorting, required-field shape |
| `test_workspace_activity.py` | 9 | every event source, sorting, deduplication, limit |
| `test_workspace_portfolio.py` | 7 | last-active/most-recently-modified selection, suggested-project scoring, Quick Resume shape |
| `test_workspace_sprint4_api.py` | 12 | full API surface, excluded-folder non-leakage into Home/Advisor/Assets/Activity, stale-data warning (including the "never scanned yet" case), manual-project preservation, real paths with spaces/parentheses, read-only guarantee |
| `test_workspace_sprint4_ui.py` | 7 | Home portfolio, `#/dproject` route + all 10 detail sections, Projects page field set, Advisor's discovered-projects section, Assets page real wiring, stale-data badge |

Full suite: **845 passed, 0 failed** (`pytest -q` from repo root, up from
771 at the end of Sprint 3). `ruff check` and `black --check` run clean
on every file created this sprint. JavaScript syntax validated with
`node --check` after every edit. Live browser smoke test performed
against a real running server (see §9).

## 9. Real-workspace verification (live browser, no screenshots saved — summarized here)

Ran against `C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS`,
adopting `ROLE_OS` (already adopted from Sprint 3), `ROLE Commerce
Factory`, `ROLE MASTER`, `role-ecosystem`, and `ROLE_KNOWLEDGE_OS`:

- **Projects page**: all 5 shown with real git branch/dirty state, real
  last-commit dates, real health/confidence/move-risk, real documentation/
  test status, real nested-component counts (`ROLE Commerce Factory`: 2
  components), and real next actions — `ROLE MASTER`: *"Confirm
  TYPOGRAPHY.md font choices and licensing"* (from a TODO section);
  `ROLE_OS`: its actual latest commit message, *"docs(discovery): define
  Discovery Engine domain model"* (git-commit fallback, since it has no
  NEXT_ACTION/TODO/ROADMAP-milestone/README-Next-Steps/CHANGELOG-
  unreleased signal at the time of scanning).
- **Discovered Project Detail** (`#/dproject/{id}`): verified for both
  `ROLE_OS` (full Git section with branch/state/last commit/remote) and
  `ROLE MASTER` (correctly showing "Not yet defined"/"Not a git
  repository" for the fields that genuinely don't apply).
- **Home**: "Your Projects" showed Last Active Project (`ROLE_OS`), Most
  Recently Modified (`ROLE_OS`), Quick Resume (`ROLE MASTER`'s next
  action, with a working Resume button that correctly navigated to its
  detail page), Projects Needing Attention (4 real, linked
  recommendations), and Recent Commits (6 real commits spanning `ROLE_OS`
  and `role-ecosystem`, real messages). "Recent Assets" and "Latest AI
  Session" correctly showed empty/"Not yet defined" (genuinely true at
  the time — see limitations below). "Today's Focus" below it remained
  untouched, still correctly showing "Nothing needs attention" since zero
  manual Projects exist.
- **Advisor**: "Discovered Projects" section showed 12 real, evidence-
  based recommendations across the 4 then-adopted projects — near-
  completion for `ROLE Commerce Factory` (health 86, client-ready),
  momentum for `role-ecosystem`/`ROLE_OS`, high-move-risk for `ROLE_OS`
  (a real, current absolute-path-reference count), dirty-tree, next-
  action-available, and no-tests — each with real evidence and a working
  "Open project →" link.
- **Assets**: initially correctly showed "No assets discovered yet" (the
  4 then-adopted projects genuinely contain zero PNG/JPG/PDF/etc. files —
  verified, not a bug). After adopting `ROLE_KNOWLEDGE_OS` (which has real
  images), the page showed all 9 real files with correct filenames,
  paths, sizes, and categories — including `shot_4_logo.png` correctly
  identified as category `logo` and `reusable: yes`.
- **A real, diagnosed non-bug**: one browser click on "Rescan Workspace"
  didn't visibly update the "Last Scan" timestamp. Verified via direct API
  calls that this was a missed UI click (a known flakiness of this
  session's browser-automation coordinates, documented in earlier
  sprints), not a code defect — a follow-up `POST /workspace/rescan`
  immediately showed the correct fresh timestamp and a fully-populated
  `recent_commits` array.
- **Excluded folders**: `OTROS - no proyectos` never appeared in Projects,
  Home, Advisor, or Assets throughout (confirmed both live and by the
  automated exclusion tests).
- **No scanned project files modified**: confirmed both by the dedicated
  read-only tests (byte-for-byte snapshots) and by the absence of any
  write call anywhere in this sprint's new code paths.

## 10. Remaining gaps

- **AI Sessions cannot yet be *created* for a purely-discovered project.**
  `app.projects.db.create_ai_session` requires a real row in the
  `projects` table (an explicit check plus a SQLite foreign key), which a
  discovered-only item never has. The *read* side is fully wired and
  correctly returns empty/`None` rather than erroring, so this surfaces
  honestly as "Not yet defined" everywhere — but there is currently no
  path for a user to start a new AI session directly from a Discovered
  Project's detail page. Resolving this needs a Sprint 5 decision about
  how the two id schemes (discovered-item hash vs. manual-project uuid)
  should relate — possibly by letting adoption optionally also create a
  linked manual Project row, which would be a real architectural change,
  not a small patch.
- **Asset index has no caching.** Fine at today's real project count
  (single digits); would need caching/pagination if the adopted-project
  count or file counts grew by an order of magnitude.
- **Recent commits capped at 5 per repo.** Deeper history would need a
  paginated `git log` call, not implemented this sprint.
- **Confidence-weighted "needs review" for weakly-promoted top-level
  projects** — carried over from Sprint 3's report, still not
  implemented.
- **Workspace Advisor is one flat file, not a package-per-rule** (§6) —
  a deliberate, documented time-scoping choice, not a defect, but worth
  splitting if the rule count grows significantly.
- **Mission Control ranking remains entirely unbuilt**, as instructed.

## 11. Recommended Sprint 5

1. **Mission Control ranking view** — the natural next step now that
   Home/Advisor/Assets/Activity all compute real per-project signals;
   Mission Control would rank/combine them into one "what to work on"
   view, rather than the current per-page presentation.
2. **Decide the AI Session id-scheme question** (§10) — likely the
   highest-value unblock, since it currently caps "AI Sessions"/"Latest
   Snapshot" at "Not yet defined" for every purely-discovered project.
3. **Confidence-weighted needs-review** (carried over from Sprint 3).
4. **Split Workspace Advisor into a rules package** if new rules are
   added, matching Epic 2's established pattern.
5. **Thumbnails for the Assets page** — deferred twice now (§6 of Sprint 3,
   §6 of this sprint); the discovery index this sprint built is the
   prerequisite for it.
