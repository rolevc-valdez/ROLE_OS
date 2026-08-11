# 13 — Project Unification, Sprint 5: Completion Report

Scope executed: remove the conceptual separation between manually-created
Projects (Project Intelligence, Epic 1) and discovered/adopted projects
(Discovery Engine + Workspace Adoption, Sprints 1-4) — from the user's
side there is now exactly one concept, "Project." Reuses Discovery,
Workspace Adoption, Project Intelligence, and AI Sessions unchanged; no
product redesign, no version bump, no commit/tag, no browser automation,
no scanned project file ever modified.

## 1. Files created

```
dashboard/app/workspace/identity.py             # canonical Project Identity bridge (§3)
dashboard/app/workspace/resume.py               # Resume Work orchestration (§4)
dashboard/tests/test_projects_identity.py       # 11 tests
dashboard/tests/test_workspace_identity.py      # 10 tests
dashboard/tests/test_workspace_resume.py        # 9 tests
dashboard/tests/test_workspace_sprint5_api.py   # 10 tests
dashboard/tests/test_workspace_sprint5_ui.py    # 6 tests
docs/architecture/13_PROJECT_UNIFICATION_SPRINT5_REPORT.md  # this file
```

## 2. Files modified

```
dashboard/app/projects/db.py           # + discovery_item_id column (migration), unique index,
                                        #   get_project_by_discovery_item_id,
                                        #   find_unlinked_project_by_name,
                                        #   link_project_to_discovery_item
dashboard/app/projects/models.py       # + discovery_item_id on Project, ProjectSummary
dashboard/app/services/resume.py       # + resolve_conversation_url (moved from ai_sessions.py,
                                        #   made public; build_resume_prompt untouched)
dashboard/app/routers/pi/ai_sessions.py # _resolve_open now aliases the shared, moved function
                                        #   (zero behavior change; own 47-test suite still passes)
dashboard/app/workspace/db.py          # + canonical_project_id column (migration),
                                        #   set_canonical_project_id
dashboard/app/workspace/service.py     # + identity resolution wired into adopt_item and
                                        #   enrich_project_item; get_ai_session_summary now takes
                                        #   canonical_project_id directly; get_enriched_item fixed
                                        #   to use it (was using the raw item_id — see §6) and
                                        #   gained a timeline field; + resume_work_for_item
dashboard/app/workspace/models.py      # + canonical_project_id on WorkspaceItem;
                                        #   + ResumeWorkResult
dashboard/app/workspace/advisor.py     # recommendation base dict gained item_id,
                                        #   canonical_project_id
dashboard/app/workspace/portfolio.py   # quick_resume reshaped to {item_id, canonical_project_id,
                                        #   project_name, action_text} (action_link removed --
                                        #   Quick Resume now triggers the action directly)
dashboard/app/routers/workspace.py     # + POST /discovered/{item_id}/resume-work
dashboard/app/static/js/app.js         # triggerResumeWork() helper; Resume Work button + Timeline
                                        #   section on Discovered Project Detail; Home Quick Resume
                                        #   and Advisor recommendation cards trigger it directly;
                                        #   Projects page dedupes canonical-linked manual projects
dashboard/tests/test_workspace_portfolio.py  # 1 assertion updated for the quick_resume shape change
CHANGELOG.md, docs/product/DECISIONS.md, dashboard/README.md,
docs/architecture/07_ROADMAP.md, docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md
```

No file inside `app/discovery/`, `app/workspace/service.py`'s existing
Sprint 1-4 enrichment functions (beyond the two fixes/wiring points
above), or any pre-existing AI Sessions/Snapshot/Timeline logic in
`app/projects/db.py` was rewritten — only additive columns and functions.

## 3. Identity model

Two nullable columns form a bidirectional bridge between the two
previously-separate id schemes:

- `projects.discovery_item_id` — Project → discovery item (the discovery
  item's stable hash id, e.g. `sha1(root_path)`-derived).
- `adopted_projects.canonical_project_id` — discovery item → Project.

Resolution (`app/workspace/identity.py::get_or_create_canonical_project_id`)
runs in this order, every time it's called, and is idempotent:

1. If the overlay already has a `canonical_project_id` that still resolves
   to a real Project row, return it unchanged.
2. Else, look for an existing **unlinked** manual Project whose name
   matches the discovered folder's name, case-insensitively
   (`find_unlinked_project_by_name`). If found, link it
   (`link_project_to_discovery_item`) — this is the backward-compatibility
   migration path, and it only ever sets the new column; every other field
   on the existing Project (notes, description, priority, capabilities,
   dependencies, existing sessions) is left untouched.
3. Else, create a new, minimal Project (`name` + `Discovered` workspace
   only) and link it.

A **read-only** variant, `get_canonical_project_id`, checks step 1 only
and never creates — used wherever code needs to know "does this item
already have a canonical identity" without side effects (e.g. rendering a
Resume Work button only when one exists).

This is deliberately **not** a data migration that merges the two
schemas. The canonical Project row never receives a copy of git status,
health score, documentation status, or asset data — that information
continues to live exclusively in the Workspace scan cache and is always
read fresh, the same "filesystem is the source of truth" principle
Sprint 2 established for the overlay table. The bridge's only job is to
give a discovered/adopted project a real `projects.id` so it can
participate in AI Sessions, Snapshots, and Timeline exactly like a
manually-created one, without duplicating anything Discovery already
owns.

**Self-healing**: if the linked Project row is deleted out-of-band, the
next resolution call detects the dangling link and transparently
re-resolves a fresh one (test: `test_stale_link_self_heals`). This matters
because the Workspace scan cache can be rebuilt independently of Project
Intelligence at any time.

**Where resolution is triggered**:
- `service.adopt_item` resolves a canonical identity immediately as part
  of adoption — this is what makes requirement #2 ("AI Sessions must work
  for every adopted project… zero manual creation") true from the moment
  a folder is adopted, not just the first time someone visits its detail
  page.
- `service.enrich_project_item` also resolves one (self-healing) for any
  already-adopted item that doesn't have one yet, so adoptions made before
  this sprint shipped are covered on their next read, with no migration
  script required.

## 4. Resume Work orchestration

`app/workspace/resume.py::resume_work(canonical_project_id)` is the single
function behind requirement #3 ("one primary action… Resume Work"):

1. Look up the Project; return `None` if it doesn't exist.
2. `list_ai_sessions()` — if any exist, reuse the most relevant one
   (existing ordering logic, unchanged); if none exist, `create_ai_session`
   (assistant=`claude`, title=`"Resume Work"`) — zero manual creation.
3. `set_ai_session_current` — mark it the project's current session.
4. `get_latest_snapshot` → `resume_service.build_resume_prompt` (existing,
   unmodified Resume Engine function) — builds the actual prompt text.
5. `resume_service.resolve_conversation_url` (moved out of the AI Sessions
   router into `app/services/resume.py` so both the pre-existing router
   endpoints and this new orchestration call the exact same function, with
   zero duplication) — resolves a saved conversation URL, or an assistant
   homepage fallback.
6. `touch_ai_session_last_used`.

`service.resume_work_for_item(item_id)` wraps this for the Workspace
layer: it 404s if the item was never adopted (adoption is the explicit
"track this" gate, unchanged from Sprint 2/4), otherwise resolves/reuses
the canonical identity and delegates to `resume_work`. Exposed as
`POST /workspace/discovered/{item_id}/resume-work`.

The frontend's shared `triggerResumeWork(itemId)` helper calls this
endpoint, copies the returned prompt to the clipboard, opens the resolved
URL in a new tab, and navigates to Cockpit (`#/project/{project_id}`) —
wired identically from three places: the Discovered Project Detail view's
primary button, Home's Quick Resume card, and every Workspace Advisor
recommendation card. All three now perform the real action instead of
merely linking to a page (requirement #5: "every Advisor recommendation
must link directly to Resume Work").

## 5. History wiring

`get_enriched_item` now resolves the canonical id once and threads it
through to both:
- `ai_sessions` (via `get_ai_session_summary(canonical_project_id, …)`),
- a new `timeline` field (`projects_db.list_project_timeline`).

Both are exposed on the Discovered Project Detail view (requirement #6:
"Sessions, Snapshots, Activity, Commits, Assets, Timeline… using the
unified identity"). Activity/Commits/Assets were already wired in Sprint
4 and needed no changes.

## 6. A real bug fixed, not just closed off

Sprint 4's completion report documented a "known gap": AI Sessions/
Snapshots couldn't be created for a purely-discovered project because
`create_ai_session` requires a real `projects.id`. What that report didn't
catch: `get_enriched_item` was *already* calling
`get_ai_session_summary(item_id, …)` using the raw discovery-item hash as
if it were a real `projects.id` — this silently returned empty results on
every call, because the hash never matched a real project row (no error,
just always-empty data). This sprint's identity bridge fixes the root
cause: every AI-session/timeline lookup now goes through the resolved
canonical id.

## 7. Backward compatibility

- Manual projects without a matching discovered folder are completely
  unaffected — `discovery_item_id` stays `NULL`, every existing
  `/pi/projects/*` endpoint behaves exactly as before (test:
  `test_manual_project_without_discovery_link_still_works`).
- A pre-existing manual Project whose name exactly matches (case-
  insensitively) a newly-adopted discovered folder gets linked
  automatically on adoption — never duplicated, never overwritten (test:
  `test_backward_compat_migration_links_existing_manual_project`, plus
  `test_existing_project_fields_untouched_by_linking` at the db layer).
- The Projects page (`renderProjectsList`) filters `/pi/projects` to
  `discovery_item_id == null` before rendering the manual list, so a
  project that now has a canonical link is never shown twice — once as a
  "manual" card and again as a "Discovered" card.

## 8. Testing

- **Unit**: `test_projects_identity.py` (11) — column default, link/find/
  get functions, `UNIQUE` constraint on `discovery_item_id`, schema
  idempotency across repeated connections, linking never mutates existing
  Project fields (notes/description/priority/collections all asserted
  preserved).
- **Identity bridge**: `test_workspace_identity.py` (10) — create-new,
  idempotent reuse, link-by-name, no cross-item collisions, read-only vs.
  create semantics, stale-link self-heal, adoption itself resolving an
  identity automatically, real paths with spaces and parentheses.
- **Resume Work sequencing**: `test_workspace_resume.py` (9) — unknown
  project → `None`, first-session zero-manual-creation, session reuse (no
  duplicate on a second call), prompt reflects the latest snapshot, the
  no-snapshot fallback prompt text, saved-URL resolution, homepage
  fallback, `last_used_at` touched, session marked current (including the
  branch where an older non-current session is the one reused).
- **API integration**: `test_workspace_sprint5_api.py` (10) — 404 before
  adopt, 200 with zero manual creation after, the canonical project
  visible in `/pi/projects` with `discovery_item_id` set, every existing
  AI Sessions/resume/snapshot/timeline endpoint working *unmodified*
  against the canonical id, resume idempotency, the backward-compat
  migration, a purely-manual project's flow, real paths with spaces/
  parentheses, and a full before/after filesystem snapshot proving no
  scanned project file is ever modified.
- **UI**: `test_workspace_sprint5_ui.py` (6) — string-assertion tests
  against the served `app.js` confirming the shared `triggerResumeWork`
  helper, the Resume Work button, the Timeline section, Quick Resume/
  Advisor wiring, and the Projects-page dedup filter are present.
- **Regression**: `test_workspace_portfolio.py` updated for the
  `quick_resume` shape change (`action_link` → direct trigger).
- **Full suite**: 891 passed, 0 failed (up from 845 at the end of Sprint
  4 — all 46 new tests, zero regressions). `ruff check --fix` and `black`
  run on every new/touched file (pre-existing `B008` findings for
  `Depends`/`Body` in argument defaults across the router files are the
  established FastAPI idiom already used everywhere else in this codebase
  and were left as-is, consistent with prior sprints' practice of not
  touching pre-existing lint findings in files being modified for other
  reasons). `node --check app.js` clean.

### Real-workspace verification

Ran against the real `1 - IA PROJECTS` folder (the same five projects
adopted in earlier sprints' live sessions: `ROLE_OS`, `ROLE Commerce
Factory`, `ROLE MASTER`, `role-ecosystem`, `ROLE_KNOWLEDGE_OS`), via a
freshly started server and direct API calls:

- `GET /workspace/discovered?view=top_level` showed all five real
  projects still adopted, each self-healing a `canonical_project_id` on
  read (none had one yet from before this sprint).
- `POST /workspace/discovered/{item_id}/resume-work` against `ROLE_OS`
  created a real, brand-new AI Session (`is_new_session: true`), returned
  a real built prompt and the `https://claude.ai` homepage fallback URL
  (no conversation URL saved yet for this session).
- A second call to the same endpoint reused the same session
  (`is_new_session: false`) — idempotency confirmed live, not just in
  tests.
- `GET /workspace/discovered/{item_id}` showed `canonical_project_id` set
  and one real Timeline entry (`session_started`).
- Called the pre-existing `POST /pi/projects/{id}/ai-sessions/{id}/
  snapshots` endpoint directly against the resolved canonical id — it
  worked completely unmodified, and the Timeline then showed two real
  entries.
- Confirmed via `git status`-equivalent (a before/after file-mtime/size
  walk) that no file under any real scanned project folder was touched at
  any point during this verification.
- One pre-existing test artifact (`app-a`, a manual Project row left in
  the dashboard's local sample database from an earlier smoke test in
  this same sprint) remains in that sample DB — noted to the user rather
  than deleted, since the deletion action required a permission gate this
  session didn't have; it is dev/sample data only, not real project data.

## 9. Known limitations

- The backward-compatibility name match is **exact (case-insensitive)
  only** — a manual Project named differently from the folder that
  represents the same real project (e.g. "My App" vs. "my-app-v2") will
  not auto-link; it gets its own new canonical Project on first adoption,
  leaving two Project rows for what the user considers one project. A
  future sprint could add a manual "link to existing project" action for
  this case.
- Resume Work always defaults a brand-new session to `assistant=claude`.
  There's no per-project "preferred assistant" setting yet to seed that
  choice from — `ai_workspace`'s per-project `preferred_model`/`role`
  fields (v1.3 concept, since migrated into AI Sessions in v1.4) aren't
  consulted here.
- The Discovered Project Detail view and the manual Project Detail/
  Cockpit view remain two separate pages/routes (`#/dproject/{id}` vs.
  `#/project/{id}`) rather than one unified template — intentional, to
  avoid rewriting Cockpit's already-working Resume Work UI and its
  distinct section layout, per this sprint's "reuse, don't rewrite"
  constraint, but it means "one concept, Project" is true at the data/
  identity layer and at the primary-action layer, not yet at the
  page-template layer.
- No UI surfaces the identity bridge itself (no "this discovered project
  is linked to Project X" indicator beyond the fact that Resume Work now
  works) — someone auditing *why* two things share history has to check
  `discovery_item_id`/`canonical_project_id` directly via the API.

## 10. Recommended Sprint 6

Unify the two detail-page templates (`renderProjectDetail` and
`renderDiscoveredProjectDetail`) behind the canonical identity now that
both read from the same underlying Project row for AI Sessions/Snapshots/
Timeline — likely by having the manual detail view optionally render
Discovery-sourced sections (Git/Documentation/Assets) when a
`discovery_item_id` is present, closing the last "two pages for one
concept" gap noted in §9. A smaller, independent option: add a manual
"link to existing project" action in the Workspace Review panel for the
non-exact-name-match case also noted in §9.
