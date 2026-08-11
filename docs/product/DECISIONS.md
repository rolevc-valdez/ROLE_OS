# Product Decisions

A running log of consequential product/architecture decisions and the
reasoning behind them, distinct from the changelog (which records *what*
shipped) — this records *why* it was built that way. Newest first.

---

## The Executive Decision Engine scores with a fixed, additive point table instead of a learned/hidden weighting, and never lets two projects tie

**Decision**: Sprint C10 asked ROLE OS to stop being an information
dashboard and become a deterministic decision system -- one answer, every
morning, to "what should I work on next?" Key calls:

1. **Scoring is a plain, additive point table, not a formula anyone has
   to reverse-engineer.** Each of the nine contributors in `scoring.py`
   (Operational Intelligence priority, commercial value/launch-readiness,
   projects unblocked, already-blocking-dependents, Impact Analysis risk,
   pending work, recent activity/staleness, project health, paused/
   blocked status) is a pure function returning `(points, reason)`; the
   final score is their sum, clamped to 0-100. Every non-zero
   contribution is named in `evidence` in the same fixed order the
   function evaluates them -- the brief's "never invent hidden weighting,
   document every contribution" requirement is enforced by the code's own
   shape, not by a comment promising it is.
2. **Stale Discovery data discounts confidence, never the score.** A
   project's evidence doesn't become less true because the workspace
   hasn't been rescanned recently -- but it becomes less *current*.
   Rather than silently shading scores (which would be an undocumented,
   effectively hidden adjustment), `is_data_stale` only ever discounts
   `confidence`, with the exact discount named in `evidence` too.
3. **Conflict resolution is a total order, not a special case.**
   `service._sort_key` sorts by `(decision_score desc, health_score desc,
   canonical_project_id asc)` -- three criteria, the last one a fixed,
   arbitrary-but-stable identity comparison that can never itself tie.
   This guarantees the brief's "never output ties" requirement
   structurally: no code path exists that could return two projects
   sharing rank 1, and the same input always produces the same winner
   (verified by a regression test that calls the engine twice on
   identical data and asserts the same project wins both times).
4. **No new detector, no second relationship graph, no second Operational
   Intelligence pass.** Every input this engine reads --
   `all_project_contexts`, `get_operational_intelligence`,
   `compute_relationships`/the Ecosystem graph, `get_impact_analysis` --
   is called at most once per request and threaded through as an optional
   parameter, the same "compute once at the outermost caller" pattern
   established across C7.1/C8/C9. Pending Work and Next Action text are
   not re-derived either -- `app.project_memory.service`'s own
   `_pending_work`/`_next_action_output` functions are imported and
   called directly.
5. **A real "double asset walk" bug was caught by an existing test, not
   discovered live.** Wiring Executive Decision into Mission Control
   initially placed the new call just *after* Mission Control's existing
   `request_scope()` block closed -- meaning Executive Decision's own
   `compute_relationships` call (whose shared-assets detector walks the
   filesystem) reran that walk once per adopted project instead of reusing
   the single walk `request_scope()` already collapsed everything else
   to. `test_no_double_asset_walk_per_project_per_request` (written for
   an earlier sprint) failed immediately on the first full regression
   run, before this ever reached a live server. Fixed by moving the call
   inside the existing scope -- the fix is one line of placement, not new
   logic.
6. **A second real bug, caught only by live browser verification**: the
   frontend's `RESULT_TYPE_ORDER` array (Explorer's render-order list, a
   *separate* list from the backend's `RESULT_TYPES`) was never updated
   when Sprint C8 added `"Ecosystem Relationship"` or Sprint C9 added
   `"Impact"` -- both result types had been silently un-renderable in the
   UI (present in the API response, absent from the page) since those
   sprints shipped, and no test caught it because the existing Explorer
   UI tests assert against the API response, not the rendered DOM's set
   of visible groups. Adding `"Executive Decision"` to the same array
   surfaced the gap; fixed by adding all three missing types together
   rather than only the new one.
7. **The 500ms performance target is reported honestly as unmet, not
   silently claimed.** Profiling on the real workspace showed Executive
   Decision's own scoring/ranking/planning logic costs ~2ms; the
   remaining ~1.3-1.9s comes entirely from `all_project_contexts`
   (~750ms) and `compute_relationships` (~570ms) -- both pre-existing,
   already-documented costs from the C6/C8 reports, inherited rather than
   introduced by this sprint. Matching this project's established
   practice (e.g. the C8 report's own measured "~1.1-1.4s"), the
   completion report and known limitations say so plainly rather than
   redefining "under 500ms" to make the number technically true.

---

## The Impact Analysis Engine reads the Ecosystem graph rather than building a second one, and two conflation bugs were fixed instead of worked around

**Decision**: Sprint C9 asked for an engine that answers "if this project
changes, what else is affected?" with bounded transitive traversal and
five explainable risk levels, using existing evidence only. Key calls:

1. **No new relationship detection, no new graph.** `app/impact_analysis/`
   only ever calls `app.project_ecosystem.graph.build_graph()`/
   `dependents_of()`/`shares_of()`/`blocks_of()` against relationships
   computed by C8's `compute_relationships` -- traversal (BFS with a
   visited set, bounded to 3 hops) is the only new algorithm in this
   sprint; every edge and every piece of shared-evidence it walks was
   already detected by the Ecosystem Engine.
2. **Risk is a fixed, documented threshold table, not a formula.** Every
   level (`none, low, medium, high, critical`) is reached by a plain count
   comparison (already-blocking dependents, direct/transitive dependent
   counts, total shared-evidence count) and returns the exact reason
   string that produced it -- deliberately avoiding any weighted score
   that could produce a risk level nobody could explain by pointing at a
   number.
3. **A second real, pre-existing bug was found while smoke-testing the
   brief's own worked example** (ROLE OS -> ROLE Commerce Factory ->
   RoleValdez.com should be `medium`/`high`, not `critical`).
   `project_ecosystem/models.py`'s `BLOCKING_STATUSES` tuple included
   `"critical"`, and `detectors.py`'s `detect_dependencies` also matched
   a target's *computed health tier* against `"critical"` -- conflating
   "someone marked this blocked" (a status) with "this project's health
   score defaults to 0 because it's new" (a tier), which would have
   falsely flagged nearly every brand-new project as blocking its
   dependents. Fixed at the root (`project_ecosystem`, not a workaround
   in the new engine) since every existing Ecosystem Engine consumer
   benefits, not just Impact Analysis.
4. **A second "double whole-workspace pass" bug, same class as C7.1's**,
   was caught by a test-suite timing regression, not a correctness
   failure: `build_project_memory()` called
   `get_operational_intelligence()` (a full Epic 2 Advisor health-score
   refresh) twice per invocation once Impact Analysis's
   `operational_effects` needed its own copy. Fixed by threading a single
   computed `operational_intelligence_recs` list through both call sites
   -- the same "compute once at the outermost caller, pass down as an
   optional parameter" pattern now applied a third time (C7.1, C8, C9)
   confirms it's the right general shape for this codebase, not a
   one-off fix.
5. **UI stays cards-only, no diagram**, per the brief -- Project Hub's new
   "Impact Analysis" section and Project Memory's "Potential Impact" line
   both render plain risk/count/reason text, matching the Ecosystem
   Engine's own C8 precedent of never adding a graph visualization to a
   page that didn't already have one.

---

## The Project Ecosystem Engine composes existing canonical domains rather than owning a second copy of any of them

**Decision**: Sprint C8 asked for a "Project Ecosystem Engine" that
understands dependencies, shared assets/knowledge/documentation/prompts/
sessions, and blocking relationships between projects, using deterministic
evidence only. Several calls made while keeping this a *composition* layer
rather than a fourth data domain:

1. **No detector re-derives evidence another domain already owns.**
   `detect_shared_assets` reads `app.assets.service.list_all_assets`'s
   already-resolved `duplicate_group_id` rather than re-hashing files;
   `detect_shared_knowledge` reads Knowledge cards via the exact same
   soft, case-insensitive project-name match `ProjectContext.
   _knowledge_count`/Explorer's `project_hub` already established, rather
   than inventing a second knowledge-to-project link; `detect_
   dependencies`/`detect_capabilities` read PI's existing explicit tables
   verbatim. The Ecosystem Engine's own code only ever *combines* results
   from these reads into relationship dicts -- it holds no persisted
   opinion about what an asset, a knowledge card, or a dependency *is*.
2. **A real, pre-existing bug was found and fixed, not worked around.**
   Building `detect_shared_assets` surfaced that `app.assets.service.
   group_duplicates` only ever cleared `duplicate_group_id`, never
   (re)set it -- meaning `list_all_assets`'s own documented promise ("re-
   groups across every project's combined records") was false for the
   exact cross-project case Assets OS was built to detect. Fixing the
   root cause (one function, two lines) was the correct move over adding
   a special-case workaround in the new detector; every existing caller
   of `list_all_assets`/`group_duplicates` benefits, not just this
   sprint's new code.
3. **Only one small overlay table was added** (`role_os_ecosystem.db`,
   dismiss/confirm by the relationship's own deterministic id) -- the
   relationships themselves are never persisted; every request recomputes
   them fresh from the canonical domains. This keeps "detector output, not
   a stored graph" true even as evidence changes underneath (a git commit,
   a new snapshot, a deleted dependency) without a stale-cache
   invalidation problem to solve.
4. **Import/package-reference scanning was deliberately left out.**
   Parsing source code for cross-project imports would require per-
   language parsers (Python, JS, etc.), a real security surface (arbitrary
   file parsing across every adopted project), and produces much lower-
   confidence evidence than the explicit/structural signals already
   implemented. Documented as a known limitation and C9 candidate rather
   than attempted at low quality.
5. **Every whole-workspace pass reuses `app.assets.service.
   request_scope()`.** The Ecosystem Engine's own shared-assets detector
   walks the filesystem exactly like Dashboard/Mission Control/Explorer's
   asset search already do -- wrapping every new call site (Resume Work,
   Cockpit's memory card, Explorer's `search()`/`project_hub()`) in the
   same cache scope was necessary to avoid reintroducing the Sprint C4.1/
   C5 double-walk problem this sprint's own detector could otherwise cause.
6. **Mission Control's new OI rule deliberately reads only the cheap
   dependency detector**, not the full ecosystem (which also runs
   filesystem/knowledge scans) -- Operational Intelligence's own "no
   repeated scans" contract must hold regardless of whether a caller in
   the same request also asked for the full Project Ecosystem view.

---

## Resume Work resumes a Project via Project Memory; the AI Session is a transport, never the source of truth

**Decision**: Real-world use of Mission Control's Resume Work button
surfaced a design flaw undetected by unit tests: the prompt Resume Work
copied was assembled entirely from the *AI Session* and its latest
snapshot. A thin or generic session meant a thin or generic prompt, and
the assistant would have to ask what the project even was — the opposite
of the feature's purpose. Sprint C7.1 fixed the actual architecture, not
just the symptom:

1. **Project Memory (`app/project_memory/`) is a new, explicit layer
   between `ProjectContext` and the Resume Prompt** — not a rename, a real
   ownership change. It reads the same already-computed `ProjectContext`
   fields (next action, git, latest snapshot) plus, for a real click, the
   Operational Intelligence Engine's top recommendation for that project.
   The AI Session is consulted *only* to decide where to open the
   conversation and to name the `Conversation:` section — never to supply
   the objective, the pending work, or the next action.
2. **A real recursion had to be broken, not avoided.** `ProjectContext`'s
   `resume_state` is itself built from `preview_resume_state`, which (to
   show an accurate preview) now builds Project Memory — which itself
   calls `build_project_context` for the same project. Rather than
   duplicating `_assemble`'s logic in a second, parallel builder (which
   would risk the two disagreeing over time), two new cost-knob parameters
   were added to the existing `build_project_context`/`_assemble`
   (`include_resume_state`, `include_epic2_recs`), both defaulting to
   `True` so every other caller in the codebase sees zero behavior change.
   `app.project_memory` is the one caller that passes `False` for both.
3. **The real Resume Work click intentionally pays for one whole-workspace
   Operational Intelligence pass**; every more-frequent caller
   (`preview_resume_state`, Cockpit's Project Memory card, the per-session
   `/resume` endpoint) explicitly skips it. This was a real regression
   caught during this sprint's own regression run (a naive
   "always include the recommendation" design made two existing test files
   take over two minutes instead of a few seconds, because every
   `ProjectContext` build was newly nesting a second full `build_project_
   context` call inside `preview_resume_state`) — fixed by threading
   `include_epic2_recs=False`/`include_operational_recommendation=False`
   through every caller except the one primary action button.
4. **Conversation selection is now a named, explainable decision**
   (`app.project_memory.session_selection.select_best_session`): latest
   active session, then pinned (`favorite` — the only "pin"-like field
   that exists; no second concept was invented), then preferred (`current`
   — the closest existing concept to a per-project "preferred" session),
   then newest. Every choice returns a plain-English reason alongside it.
5. **Session naming is retroactive, not just forward-looking.** A session
   already titled "Resume Work" (the exact bug this sprint fixes) is
   retitled to `<Project Name> — <Objective>` the moment it's next
   resumed, rather than requiring a separate migration or leaving already-
   created sessions permanently mis-named.
6. **The old session-only prompt builder was deleted, not deprecated.**
   `app.services.resume.build_resume_prompt` and its test file were
   removed entirely (not left as unused dead code) — "the AI Session never
   owns the prompt" is an architectural invariant, not a preference, so no
   code path should be able to construct one from session data alone
   anymore.

---

## One Operational Intelligence Engine composes the two existing rule engines rather than replacing either

**Decision**: Sprint C6 asked for "one canonical Operational Intelligence
service" that Mission Control, Advisor, Dashboard, Daily Session, and
Resume Work all consume, with an explicit "do not create separate
recommendation engines." The repo already had two: the Workspace Advisor
(`app.workspace.advisor`, discovery/git evidence) and the PI Advisor
(`app.advisor.engine`, dependencies/capabilities/TODOs/deliverables,
persisted with a dismiss/complete/TTL lifecycle). Several calls made while
reconciling "one engine" with "two engines already exist and have real,
different-shaped persisted state":

1. **Composition, not a rewrite.** `app.operational_intelligence.engine.
   generate_recommendations` calls both existing engines' own public
   orchestrator functions (`workspace_advisor.generate_recommendations`,
   `advisor_engine.get_recommendations`) exactly as they are, then
   normalizes both native shapes into one canonical dict. Rewriting either
   engine's 8-12 rules from scratch into a new shared format would have
   been higher-risk (regressing 1000+ existing tests, especially the PI
   engine's persisted dismiss/complete workflow) for no evidence-coverage
   benefit — the rules themselves were already correct and already
   deterministic; what was missing was one shape and one entry point, not
   new rule logic for the evidence both engines already read.
2. **The PI engine's persisted lifecycle stays exactly where it is.**
   `GET /advisor/recommendations`'s dismiss/complete/TTL semantics are
   Advisor-specific user-facing state (a user explicitly dismissed this
   specific recommendation), not something a stateless composition engine
   should reinterpret or duplicate. The new `GET /advisor/operational-
   intelligence` endpoint is additive and always-fresh/stateless; it does
   not replace the persisted feed.
3. **Only three genuinely new evidence dimensions got new rules**
   (`app/operational_intelligence/rules.py`): Knowledge freshness (no
   prior computation existed anywhere in the repo), Discovery scan
   freshness (already computed by `workspace.service.get_freshness`, but
   never turned into an actionable recommendation before this sprint), and
   workspace status × pending work (neither existing engine reads a
   project's own `status` overlay field at all). Dependencies/capabilities/
   TODOs/deliverables/decisions/health/git/commercial-readiness were
   already covered — reused via composition, not reimplemented.
4. **`expected_benefit` (a brief-mandated field neither existing engine
   had) is a static, documented keyword → sentence lookup**, never
   generated or inferred — consistent with "no hidden scoring, no magic
   numbers without documentation." Every possible benefit sentence is
   readable in one place (`models.py`).
5. **Resume Work and Dashboard were deliberately not deeply rewired this
   sprint.** Resume Work's prompt-building has no scoring of its own to
   replace — its actual integration point is that the Mission Control card
   which triggers it now explains *why* via this engine. Dashboard "may
   summarize it" per the brief (a lower bar than Mission Control/Advisor's
   "must consume"); it continues reading `ProjectContext.advisor_summary`
   (itself built from the discovery pack) unchanged, since Dashboard's role
   this sprint stayed analytics, not action — deeper Dashboard integration
   is a reasonable candidate for a future sprint, not a gap introduced now.

---

## Mission Control replaces Home as the default route; Dashboard stays the deeper analytics view

**Decision**: Sprint C5 built one new endpoint, `GET /mission-control`
(`app/mission_control/service.py`), as the daily operating surface the
brief asked for — "what should I work on today, where did I leave off,
what changed, what needs attention, what's closest to producing real
value," answerable within 10 seconds of opening ROLE OS. Several
consequential calls made while building it:

1. **Home becomes Mission Control; the old "Command Center" Home page is
   retired from routing** (`static/js/app.js`'s `routes.home` now points at
   `renderMissionControlPage`, and the sidebar's first nav item is
   relabeled "Mission Control"). Dashboard (`/dashboard/summary`) is kept
   as-is and un-renamed — it remains the deeper, report-shaped executive
   view (portfolio status breakdowns, recent knowledge, full metrics
   cards); Mission Control is deliberately narrower and action-oriented,
   never a second copy of Dashboard's content. The brief's "don't keep two
   near-identical pages" therefore reads as *Home* being redundant with
   Dashboard once Mission Control exists, not Dashboard itself.
2. **No new ranking/recommendation engine was written.** Every section of
   the payload calls an existing service exactly once:
   `all_project_contexts` for canonical project state, `get_home_portfolio`
   for the Primary Focus recommendation (`suggested_project_to_continue`,
   unchanged), and `workspace.advisor.generate_recommendations` for both
   Today's Focus and Needs Attention — the same rule set Dashboard's
   `needs_attention` already calls, just deduped/sliced two different ways
   (`workspace.portfolio.projects_needing_attention`, reused verbatim, not
   reimplemented).
3. **"Since Last Time" baselines on the user's own last completed/active
   Daily Session** (`app.session.db.list_sessions`, most recent
   `completed_at`/`created_at`), falling back to a clearly labeled 24-hour
   window when no session has ever been recorded — never silently showing
   "everything" or crashing on a fresh install. `filesystem_modified`
   activity events are explicitly excluded from this view (mtime-only
   noise, no other signal), while still appearing in the general Recent
   Activity feed.
4. **The Value Signal section only ever reports what
   `workspace.advisor.rule_near_completion` already found** ("Consider
   shipping/launching," itself gated on health score + commercial
   readiness == client-ready/production). No revenue or market-potential
   number is fabricated; when no project qualifies, the section says so
   honestly ("insufficient evidence") rather than guessing a runner-up.
5. **The C4.1 finding — `/dashboard/summary` walking every adopted
   project's assets twice per request — is fixed with a request-scoped
   cache, not a redesign.** `app.assets.service.request_scope()` is a
   `contextvars`-backed cache keyed by resolved root path, active only
   inside a `with request_scope():` block; `index_project_assets` checks it
   before walking. Both `build_dashboard_summary` and
   `build_mission_control` wrap their bodies in it, collapsing what used to
   be up to 3-4 real filesystem walks per adopted project per request down
   to exactly one. Absent the context manager, behavior is byte-for-byte
   unchanged (every caller still walks fresh) — existing callers that don't
   opt in are not affected.
6. **Known limitation, recorded rather than worked around**: "Since Last
   Time" cannot surface status changes, new blockers, or roadmap/TODO edits
   as discrete events — the Recent Activity feed (`workspace.activity`) has
   no event type for them today. Only what the feed already tracks (git
   commits, filesystem changes, adoption, AI sessions/snapshots, discovered
   assets) can appear there; extending that event vocabulary is out of
   scope for this sprint and is a candidate for C6.

---

## A formal Discovery Engine Domain Model was written before any persistence, identity resolution, or API work began

**Decision**: `docs/architecture/11_DISCOVERY_ENGINE_DOMAIN_MODEL.md`
(renumbered from an initial `10_` that collided with the unrelated,
already-uncommitted `10_WORKSPACE_ADOPTION_SPRINT2_REPORT.md`, left
untouched) defines 26 domain concepts (Workspace through Workspace Graph
Edge), their boundaries, invariants, lifecycles, a conceptual identity-
resolution model, a source-of-truth matrix, and a logical (not physical)
persistence/API boundary — with zero code, schema, or endpoint changes.
Several consequential decisions from that document (and its architectural
review) are recorded here:

1. **Discovered Project and Managed Project are, and will remain, separate
   concepts** — a Discovered Project is recomputed evidence, owned
   entirely by Discovery; a Managed Project is a human's curated decision,
   owned by Project Intelligence. Linking them (once Identity Resolution
   exists) creates a *reference* between two records that keep their own
   lifecycles — it never merges their schemas into one row, and discovered
   data may only ever fill a gap in a Managed Project, never overwrite a
   field a human already set.
2. **Identity resolution requires human confirmation in its initial
   implementation, regardless of confidence score.** Even "exact evidence"
   (matching git remote, matching path history) produces an Identity
   Candidate awaiting a Human Confirmation, not an automatic link. No
   confidence threshold promotes a candidate to confirmed on its own.
3. **Discovery owns its own persisted scan records** (a future
   `discovery_*` SQLite file, never `role_os_projects.db`), following the
   same "each domain owns its own database" convention already used by
   Projects, Advisor, Imports, and Extraction — not a new pattern, a
   continuation of an existing one.
4. **Discovery's Recommendation stays advisory, not an executable
   action**, matching how Advisor's `suggested_action` already works —
   nothing in Discovery, today or proposed, moves, renames, merges, or
   archives a folder in response to a Recommendation. Only a human,
   acting entirely outside Discovery's own read-only guarantee, ever
   performs the actual filesystem operation.
5. **A Recommendation's `action`/`reasons`/generated timestamp/rule-or-
   engine-version may be retained as part of a future persisted scan
   result or Snapshot** — but full recommendation *lifecycle* (dismiss,
   accept, snooze, a history UI) is explicitly deferred past Sprint 2, and
   is not the same commitment as Advisor's already-built
   persist-and-dismiss model. Recording the value is in scope; managing
   its lifecycle is not, yet.
6. **`Merge with another project` stays a reserved, valid action in the
   six-action vocabulary — not deleted, and not required to be emitted by
   any current rule.** No rule may emit it without strong identity *and*
   relationship evidence, and — like every other action — it never
   executes anything on its own; a human confirms it before any
   consolidation happens. It is documented in the Domain Model as
   reserved/inactive, not as a gap to silently paper over.
7. **The Projects domain is the sole authority for *confirmed* Project
   Relationships and Project Families.** Discovery may only produce
   *candidate* relationships from discovered evidence — labeled
   distinctly (`possible duplicate of`, `possible archived copy of`,
   `possible fork of`, `possible child module of`, `possible member of
   project family`, `possible successor/predecessor`) so a candidate is
   never mistaken for a confirmed fact. A Discovery candidate relationship
   becomes an authoritative one only through the same explicit Human
   Confirmation step Identity Resolution already requires (decision 2) —
   Discovery never silently creates or overwrites an authoritative
   relationship.
8. **Managed Project Health and Discovered Project Health remain two
   separate, separately-explainable scores — never silently merged into
   one number.** Managed Project Health evaluates the curated,
   human-maintained record (`projects/health/`, unchanged); Discovered
   Project Health evaluates technical/structural filesystem evidence
   (`discovery/health.py`, unchanged). Either may be *displayed* alongside
   the other once a link exists, but any future single composite score
   combining them must be its own explicitly-defined, explainable, and
   versioned computation — not an implicit average or a silent
   replacement of one by the other.

**Why**: Sprint 1/1.5 built a real, tested, read-only audit engine, but
its only formal vocabulary lived in code (`DiscoveredProject`'s ~50 flat
fields) and one architecture proposal that pre-dated the actual
implementation and used "Project" ambiguously for both discovered and
managed projects. Persistence, an API, and identity resolution were all
about to be designed next — and each of those would have had to invent
(or silently assume) this vocabulary under implementation pressure,
exactly the situation that produces terminology drift (three different
meanings of "Project" across three modules) and safety gaps (the kind of
"confidence score alone shouldn't merge two real projects" rule that's
easy to skip when it's not written down anywhere before the merge code
exists). Writing the domain model first, with no code attached, let this
get reviewed and challenged before it was load-bearing — decisions 5-8
above are exactly that review's output: each one closes a specific gap
(recommendation persistence scope, the unused `Merge` action, relationship
authority, and health-score conflation) the initial draft had left
implicit or only partially resolved.

**How to apply**: Before Sprint 2 (or any future Discovery work) adds a
table, endpoint, or algorithm, check it against
`11_DISCOVERY_ENGINE_DOMAIN_MODEL.md`'s vocabulary, invariants, and open
questions first — in particular: persisting a Recommendation's *value* is
fine in Sprint 2; building dismiss/accept/snooze is not, yet. Any rule
that emits `Merge with another project` needs both strong identity
evidence and human confirmation, no exceptions. Any Discovery-derived
relationship must be labeled as a candidate (`possible ...`) until a human
confirms it into the Projects domain. And any UI or scoring work touching
"health" must keep Managed and Discovered health visibly distinct unless
a new, explicit composite score has been separately designed and
versioned.

---

## Discovery Engine Sprint 1.5: detectors and recommendations moved to registry/rule-engine architecture, no product behavior changed

**Decision**: Sprint 1.5 was scoped as structural hardening only (no new
features, no persistence, no API). Three refactors:

1. **Detector registry** (`dashboard/app/discovery/detectors/`, replacing
   the single flat `detectors.py`): one shared, read-only `FolderInventory`
   walk (`inventory.py`) records raw structural facts only (which files/
   dirs exist, names, extensions) with zero interpretation; twelve
   independent detector modules (`documentation.py`, `testing.py`,
   `environment.py`, `scripts.py`, `docker.py`, `ci.py`, `databases.py`,
   `obsidian.py`, `vscode_workspace.py`, `markers.py`, `assets.py`,
   `absolute_paths.py`) each own a small `Findings` dataclass and a pure
   `detect(inventory) -> Findings` function; `registry.run_all()` merges
   them with a collision guard (`DetectorFieldCollisionError`) so two
   detectors can never silently claim the same `DiscoveredProject` field.
   This mirrors `app/projects/health/` and `app/advisor/rules/`'s existing
   "one signal, one file, one registry" shape — Discovery had reinvented a
   worse version of a pattern this codebase already solved.
2. **Recommendation rule engine** (`dashboard/app/discovery/recommendation/`,
   replacing the flat `recommendation.py`'s if/elif ladder): six rules
   (`rules/non_project.py`, `high_move_risk.py`, `brand_asset_project.py`,
   `documentation_project.py`, `real_project.py`, `fallback.py`), each an
   independent `evaluate(project) -> RecommendationCandidate | None` with
   an explicit `PRIORITY` int. `engine.recommend()` runs every rule and
   keeps the highest-priority candidate that fired — precedence is an
   inspectable number on each rule, documented in a table in
   `rules/__init__.py`, not implicit if/elif ordering. Verified (test:
   `test_rule_order_in_list_does_not_affect_precedence`) that reversing
   the rules' list order doesn't change any outcome.
3. **Pipeline-stage safety** (`dashboard/app/discovery/pipeline.py`, new,
   ~60 lines): a `PipelineStage` `IntEnum` (`NEW` → `DETECTED` →
   `CLASSIFIED` → `SCORED` → `RECOMMENDED`) stamped onto
   `DiscoveredProject.stage` as each stage completes, and a
   `require_stage()` guard called at the top of `health.compute_health()`
   (needs `CLASSIFIED`) and `recommendation.recommend()` (needs `SCORED`).
   Calling either out of order now raises `PipelineStageError` instead of
   silently scoring against incomplete/default data (e.g.
   `commercial_readiness == "unknown"` quietly mapping to a plausible-
   looking 20). This was the smallest safeguard that closed the gap, not a
   `DiscoveredProject` model rewrite — its shape is unchanged.

Behavioral parity was proven, not assumed: re-running the CLI against both
real corpora used in the Sprint 1 report (`Documents`, `1 - IA PROJECTS`)
produced byte-for-byte identical Markdown reports before/after the
refactor (the one line that differed was `ROLE_OS`'s own git commit hash,
which changed because of an unrelated checkpoint commit made between
runs — not a behavior change). Two known pre-existing quirks were
preserved deliberately rather than "fixed": `go.mod` files are still
double-counted in `tech_markers` (a Sprint 1 bug now documented in
`detectors/markers.py`, left alone because fixing it would silently change
`confidence_score` and possibly classification for Go projects), and
`DiscoveredProject.frameworks` is still always empty (never had a detector
in Sprint 1 either).

**Why**: The architecture review after Sprint 1 identified detectors.py's
single ~150-line `analyze_folder()` and recommendation.py's if/elif ladder
as the two places that would not scale as more detectors/rules were added
— every addition meant editing a shared function, with no isolation
between unrelated concerns and no way to test one detector without the
whole walk. Pipeline-stage safety closed a related but separate risk: nothing
enforced that `compute_health`/`recommend` were only ever called after
classification, which worked today only because `classifier.classify()`
happens to be the sole call site.

**How to apply**: A new Discovery Engine detector is a new file with a
`Findings` dataclass + `detect()` function, plus one line in
`detectors/registry.py::DETECTOR_REGISTRY` — never edit
`inventory.py`'s walk itself. A new recommendation rule is a new file with
an `evaluate()` function and a `PRIORITY` constant, plus one line in
`recommendation/rules/__init__.py::RULES`, with its precedence reasoning
added to that file's table. Any future stage added to the Discovery
pipeline (e.g. a Sprint 2 "confirmed" stage) should extend
`PipelineStage` and guard its own entry point with `require_stage()`,
following the same pattern rather than inventing a new one.

---

## The Cockpit redesign (UX-001) computes Today's Objective / Next Action / Last Snapshot from the existing snapshots endpoint instead of adding a new one

**Decision**: The new insight cards call the pre-existing
`GET /pi/projects/{id}/ai-sessions/{id}/snapshots` endpoint for the
current session and take the most recent row (`snapshots[0]`, since
`list_ai_session_snapshots` already orders by `created_at DESC`), reading
`pending_work` as the objective, `next_prompt` as the next action, and
`summary` as the last snapshot text — rather than adding a new
"session summary" or "objective" field/endpoint to the backend.

**Why**: The task was explicit that this sprint is frontend-only ("Do not
redesign the backend... Only improve the user experience"). The snapshot
fields already captured this exact information — `pending_work` and
`next_prompt` are literally "what's left" and "what to do next" — but the
UI had never surfaced them outside the Resume prompt. Reusing the
existing endpoint and existing fields satisfied the requirement with zero
backend surface area added.

**How to apply**: Before adding a field or endpoint for a UX
requirement, check whether the data already exists somewhere in the
domain and just hasn't been surfaced in the UI yet — a frontend-only
constraint is a strong signal to look harder before reaching for a
backend change.

---

## Cockpit secondary actions moved behind a per-session overflow menu, not deleted or demoted to a settings page

**Decision**: Open / Favorite / Set current / Snapshot / Delete stayed
exactly where they were in the DOM (same buttons, same `data-*`
attributes, same click handlers) — they were simply wrapped in a
`hidden`-by-default `.overflow-menu` container toggled by a new `⋯`
button per session card, and one at the page header level for the
project switcher.

**Why**: "Preserve all existing functionality" and "hide secondary
actions under an overflow menu" both had to be true at once. Wrapping in
place (rather than rewriting the actions into a new menu component) meant
every existing `[data-open-session]` / `[data-favorite]` / etc. selector
and event handler kept working unchanged, and `test_cockpit_ui.py`
required zero modifications — the redesign is additive DOM structure
around unchanged functionality, not a rewrite of it.

**How to apply**: When a UX task asks to visually de-emphasize existing
actions ("hide behind a menu", "collapse", "move to overflow") without
removing them, prefer wrapping the existing markup/handlers in a
show/hide container over reimplementing the actions — it's the surest way
to satisfy "preserve existing functionality" literally.

---

## First-run detection uses the true unfiltered project total, not the header's workspace filter

**Decision**: The Projects page decides whether to show onboarding vs.
the normal list by fetching `/pi/projects` with no query string and
checking that count, even though the page also independently fetches a
workspace-filtered list to actually render. These are deliberately two
separate requests, not one reused response.

**Why**: The header's workspace filter is user-selectable and persists
across navigation. If detection reused the filtered fetch, a user with
existing projects who simply had a workspace filter selected that
happened to match none of them would be shown "Welcome to ROLE OS,
create your first Project" — which is both confusing and, if they went
through with it, would create a duplicate/stray project instead of just
clearing their filter. Correctness here mattered more than the cost of
one extra request.

**How to apply**: Any future "is this collection empty" UI decision in
this app should default to checking the true unfiltered total, not
whatever view-scoped filter is currently active — filters are for
display, not for state detection.

---

## The onboarding wizard and normal-mode "+ New Project" form share one field generator and one submit handler

**Decision**: `renderCreateProjectFieldsHtml()` and
`handleCreateProjectSubmit(e, statusElId)` are single, shared functions
used by both the first-run wizard and the always-available "+ New
Project" inline form on the normal Projects list — the only difference
between the two call sites is which status `<div>` id progress/errors
get written into.

**Why**: These are the same operation (create a project via
`POST /pi/projects`) reachable from two different entry points in the
UI. Writing two near-identical forms/handlers would have been the kind
of duplication that quietly drifts out of sync the next time either one
needs a field added or a validation rule changed — exactly the pattern
this project's own guidance says to avoid.

**How to apply**: When a task asks for "the same creation flow" to be
reachable from more than one place in the UI, default to one shared
form-builder and one shared handler parameterized only by presentation
details (status element, container), not two parallel implementations.

---

## v1.4 keeps ai_workspace fully intact and copies its data forward, instead of migrating in place

**Decision**: The v1.3 `ai_workspace` table, its db.py functions, and its
entire `/pi/projects/{id}/ai-workspace*` API are byte-for-byte unchanged
in v1.4. A new, separate `ai_sessions` collection is populated from it by
a one-time, tracked migration that **copies** matching data — it never
renames, alters, or drops `ai_workspace`, and never writes back to it.

**Why**: The task was explicit on two fronts that pull in the same
direction: "preserve AI Workspace URLs through a migration" and "keep
existing API contracts unless versioned." A copy-forward migration
satisfies both literally and without judgment calls -- there is no
ambiguity about whether some old client or test still depends on the
v1.3 shape, because it was never touched. The alternative (migrate the
table in place, drop the old columns, repoint the old endpoints at the
new tables) would have been a genuine breaking change dressed up as a
migration, and would have put every existing `test_ai_workspace_db.py`
/ `test_ai_workspace_api.py` assertion at risk for no functional gain.

**How to apply**: When a task says both "replace X" and "preserve X's
data / keep X's contract," read that as "add the replacement alongside
X, migrate data forward by copying, leave X alone" -- not as permission
to delete or rewrite X in place. Revisit only when a future task
explicitly asks to retire `ai_workspace` for real.

---

## The migration is tracked in a real `schema_migrations` table, not folded into the idempotent `CREATE TABLE IF NOT EXISTS` pattern

**Decision**: `app/projects/db.py` gained an actual migration
mechanism -- a `schema_migrations(id, applied_at)` table and an ordered
list of named, run-once functions (`MIGRATIONS`) -- rather than trying
to make the `ai_workspace` → `ai_sessions` data copy idempotent by
re-checking "does a matching session already exist" on every connection
the way `ensure_schema`'s table creation already is.

**Why**: The existing `CREATE TABLE IF NOT EXISTS` pattern is naturally
idempotent because *creating a table that already exists is a no-op* --
but copying rows is not naturally idempotent in the same way; without an
explicit "have I already done this" record, either the copy would need
to re-derive "does this look already-migrated" from data shape (fragile:
what if a user creates a real session that happens to look like a
migrated one?), or it would duplicate sessions on every restart. A
dedicated, explicitly-tracked migration is the standard, unambiguous
answer to that problem, and doubles as the literal "add a database
migration" deliverable this task asked for as its own numbered
objective, not just an implementation detail of the AI Sessions feature.

**How to apply**: Any future schema change that *moves or transforms*
existing data (as opposed to adding a new, empty table or column) should
be a new entry in `MIGRATIONS`, following the same "append, never
rewrite, runs once" discipline as `role-ecosystem/DECISION_LOG.md`.
Pure additive schema changes can keep using plain `CREATE TABLE IF NOT
EXISTS`.

---

## "Current" is scoped per (project, assistant), not one global current session per project

**Decision**: `set_ai_session_current()` only demotes other sessions
that share both the same `project_id` *and* the same `assistant` as the
one being promoted. A project can have a current Claude session and a
current ChatGPT session simultaneously.

**Why**: "Current" answers the question "which conversation do I resume
when I click Resume for this assistant on this project?" -- and that
question is naturally per-assistant. A single project-wide "current"
flag would force picking one assistant as primary and would make
Resume ambiguous or wrong for whichever assistant lost.

**How to apply**: Any future "pick the primary X" feature over a
collection with a secondary dimension (here: assistant) should default
to scoping "primary" by that secondary dimension unless there's a
specific reason the whole collection needs exactly one primary.

---

## The Project detail page's old AI Workspace card was deleted, not left alongside the new one

**Decision**: `renderAiWorkspaceCardHtml`/`wireAiWorkspaceCard` were
removed from `app.js` entirely, replaced by a lean AI Sessions summary
card linking into Cockpit -- the two UIs were not shown side by side.

**Why**: The task's first objective was explicit: "Replace the single AI
Workspace record with an AI Session collection." Two competing panels
for overlapping purposes (one saved URL per tool vs. many named
sessions per tool) on the same page would have been confusing, not
backward-compatible -- and the *backend* compatibility this task also
required is fully satisfied without keeping the old UI, since
`/pi/projects/{id}/ai-workspace*` remains reachable for anything that
still calls it directly. `test_ai_workspace_ui.py` was updated to match
(asserting the old markup is gone), while `test_ai_workspace_db.py` and
`test_ai_workspace_api.py` -- which test the preserved backend contract,
not the replaced UI -- were left untouched.

**How to apply**: "Keep existing API contracts" and "keep the UI that
called them" are different promises. When a task explicitly asks to
replace a UI, replace it outright and update that UI's own tests to
match; only the underlying data/API contract needs preserving unless
told otherwise.

---

## AI Workspace attaches to Project Intelligence projects, not the Daily Session registry

**Decision**: `ai_workspace` is a new table in `role_os_projects.db`,
keyed by Project Intelligence's `project_id` -- not a new field on
`app.session`'s small, fixed, seven-entry local registry that the v1.2
AI Launcher reads from.

**Why**: The task asked for a panel on "every project." Project
Intelligence is the domain that actually models arbitrary, user-created
projects (workspaces, health, capabilities, dependencies -- an open-
ended set); the Session domain's registry is a small, fixed list of
ROLE Ecosystem products used specifically to scope a *daily session*,
not a general project store. Attaching AI Workspace to the registry
would have meant only seven specific projects could ever have one.

**How to apply**: When a new per-project feature is requested generically
("every project"), check which store actually owns the general concept
of "a project" before picking where to attach it -- in this codebase,
that's `app.projects` (Project Intelligence), not `app.session`'s
registry, even though the registry also has rows that happen to be
called "projects."

---

## AI Workspace is a new table in the existing Project Intelligence database, not a new domain

**Decision**: `ai_workspace` lives in `role_os_projects.db` (Project
Intelligence's existing SQLite file), as a new table alongside
`capabilities` and `dependencies` -- not a new top-level domain with its
own database file.

**Why**: Every row in `ai_workspace` is meaningless without the project
it belongs to (`project_id REFERENCES projects(id)`), and it has no
independent lifecycle, ownership, or access pattern that would justify a
separate store -- exactly the same reasoning that already put
`capabilities` and `dependencies` in this database rather than their
own. Splitting it out would have meant a `project_id` foreign key across
two SQLite files, which this codebase's own rule already forbids in
spirit ("never duplicate data into a new store").

**How to apply**: A new capability whose data has no meaning without an
existing entity, and doesn't need its own database for isolation or
ownership reasons, is a new table (or set of tables) in that entity's
existing database -- not an automatic new top-level domain. Compare this
to the Daily Session domain (`app.session`, `[[../architecture/
06_DEVELOPMENT_RULES]]`'s precedent), which *did* get its own database
specifically because it has its own lifecycle unrelated to any single
project.

---

## AI Workspace stores at most one URL per tool per project, not a history

**Decision**: `ai_workspace` has exactly one `claude_url`, one
`chatgpt_url`, and one `gemini_url` column per project -- saving a new
URL overwrites the previous one. There is no conversation history table.

**Why**: The task's schema is explicit: "Claude conversation URL," not
"Claude conversation URLs." A single current pointer per tool matches
how the feature is actually used -- you're continuing *the* conversation
for this project in this tool, not choosing from a list of past ones.
Adding history would be speculative scope the task didn't ask for.

**How to apply**: If a future request asks for conversation history
specifically, that's a new, explicitly-scoped table
(`ai_workspace_history`, append-only) -- don't retrofit the current
single-URL-per-tool columns to also serve as a log; the two are
different data shapes for different questions.

---

## The AI Launcher copies the clipboard and opens tabs client-side -- the backend never touches either

**Decision**: `POST /launcher/start` returns only a prompt string and a
list of URLs. `navigator.clipboard.writeText()` and `window.open()` --
both plain browser JS -- do the actual clipboard-copy and tab-opening,
in `static/js/app.js`. No Python clipboard library (e.g. `pyperclip`)
and no server-side "open the user's browser" call was added.

**Why**: The dashboard is a web page already running in the user's
browser. Anything the backend could do to open a URL or set the
clipboard, the page it's already serving can do more simply, with zero
new dependencies, and without the platform-specific quirks of
driving the OS clipboard from a Python process (different mechanisms on
Windows/macOS/Linux, extra permissions on some). This keeps "local
only" (requirement 9) trivially true: nothing here talks to the OS at
all outside the browser sandbox it's already running in.

**How to apply**: Any future one-click action from the dashboard that
ends in "open a URL" or "put something on the clipboard" should follow
this same shape -- backend returns data, `app.js` performs the
browser-native action. Reserve an actual OS-level call (like the
Windows launcher's `Start-Process`) for contexts where no browser page
is already open to do it from, which is a genuinely different situation
from this one.

---

## AI Launcher is a new `app/services/` package, not a new domain

**Decision**: `launcher.py` lives in a new top-level `app/services/`
package, not in `app/session/` (which already generates a similar,
simpler Claude prompt) and not as its own domain with an owned SQLite
file.

**Why**: The Launcher has no state of its own to persist -- it reads the
active session (`app.session`), a registry project's milestone/next
action (also `app.session`), and recent decisions
(`app.session.decisions_adapter`), and returns text. Every existing
domain in this codebase (`projects`, `advisor`, `session`, ...) exists
specifically *because* it owns a SQLite file; forcing the Launcher into
that pattern would mean inventing a database for a feature that
persists nothing. `app/session/markdown.py`'s existing
`build_claude_prompt()` was left untouched rather than extended,
because it's simpler by design (used by the existing prompt card) and
the Launcher's prompt is deliberately richer (adds Pending Tasks and
Recent Decisions) -- conflating the two would have made the simpler,
already-tested one harder to reason about for no benefit.

**How to apply**: A new capability that only *reads* existing domains
and performs a stateless action belongs in `app/services/`, named
after what it does, not modeled as a domain. The moment it needs to
remember something between requests, it graduates to a real domain
with its own store, following the pattern in
[[../architecture/06_DEVELOPMENT_RULES]].

---

## `/launcher/start` is a new path, not a reuse of the existing `/session/start`

**Decision**: The AI Launcher's endpoint is `POST /launcher/start`,
under a new `/launcher` prefix -- not a change to the existing
`POST /session/start`, which already has a different, well-established
meaning (create and activate a new Daily Session).

**Why**: `/session/start` is a tested, documented endpoint whose
contract (create a session; 409 if one is already active) has nothing
to do with launching an AI tool for a session that's already running.
Reusing that path for a different action would have meant either
overloading one endpoint with two unrelated behaviors selected by some
implicit signal, or breaking its existing behavior -- both worse than a
short, clearly-named new path, and both would have risked the "keep
existing tests passing" requirement this change was built under.

**How to apply**: `docs/architecture/06_DEVELOPMENT_RULES.md`'s "never
modify an existing, shipped endpoint's contract" rule applies even when
a new feature's name superficially suggests reusing an existing path --
name the new endpoint for what it does instead.

---

## Launcher sets all five database env vars as absolute, repo-root-anchored paths -- not just the Knowledge one

**Decision**: `Resolve-RoleOSDatabaseEnv` (`scripts/RoleOS.Common.ps1`)
sets `ROLE_OS_DB_PATH`, `ROLE_OS_PROJECTS_DB_PATH`,
`ROLE_OS_ADVISOR_DB_PATH`, `ROLE_OS_IMPORTS_DB_PATH`, and
`ROLE_OS_EXTRACTION_DB_PATH` -- all five of `app/config.py`'s
sample-seeded database paths -- as absolute paths anchored to the
repository root, not just the one (`ROLE_OS_DB_PATH`) whose failure was
visibly reported on the Knowledge page.

**Why**: All five share the exact same root cause: `app/config.py`
defaults each one to a path relative to the process's working directory,
and the launcher starts uvicorn with `dashboard\` as that working
directory (per "change safely into the dashboard directory"). Only
`ROLE_OS_DB_PATH` fails loudly, because `app/db.py`'s Knowledge API is
read-only and raises `DatabaseUnavailableError` when its file is missing.
The other four (Project Intelligence, Advisor, Imports, Extraction) are
dashboard-owned and auto-create their schema on first use -- so with the
same misresolved working directory, they would have silently created
four *new, empty* databases at `dashboard\samples\...` instead of loading
the real seeded sample data at `samples\...`, with no error at all. That
is a strictly worse failure mode than the Knowledge page's loud one:
empty-but-functional pages that look correct until you notice the data
that should be there isn't. Fixing only the reported variable would have
left this silent version of the same bug in place.

**How to apply**: Any environment variable `app/config.py` defaults
relative to the working directory, and that the launcher's uvicorn
process depends on, must be set as an absolute path by the launcher --
auditing `app/config.py` for every `os.environ.get(..., "<relative
path>")` pattern is the reliable way to find them all, rather than fixing
only the one a user happened to notice.

---

## `ROLE_OS_WORKSPACE_DIR` is an opt-in launcher switch, not automatic workspace detection

**Decision**: The launcher defaults to the bundled
`samples\role_os_sample\00_SYSTEM\` fixture unless the user explicitly
sets `ROLE_OS_WORKSPACE_DIR` to a folder containing their own
`00_SYSTEM\`. It does not look for, or automatically prefer, a
conventionally-named real workspace (e.g. a sibling `ROLE_KNOWLEDGE_OS\`
folder) even when one exists on disk.

**Why**: Automatically switching a user's default database out from under
them -- even to something that looks like "their real data" -- is
exactly the kind of silent behavior change this task was explicitly
asked to avoid ("without silently migrating data"). An explicit
environment variable is inspectable (`launcher.log` always states which
source was used and why), reversible (unset it, get the sample data
back), and never surprises a user who genuinely wants to explore the
bundled demo. No file is ever copied, moved, or renamed by this feature
in either direction.

**How to apply**: The same "opt-in env var over convention-guessing"
choice should be the default answer for any future setting where ROLE OS
could plausibly guess right most of the time -- guessing right *usually*
is not the bar for something that silently changes what data a user is
looking at.

---

## The Windows launcher is implemented in PowerShell, with .bat files as thin double-click wrappers

**Decision**: `Start ROLE OS.bat` and `Stop ROLE OS.bat` are minimal
wrappers (`powershell -ExecutionPolicy Bypass -File ...`) around real
logic in `scripts/Start-RoleOS.ps1`, `scripts/Stop-RoleOS.ps1`, and a
shared `scripts/RoleOS.Common.ps1`. Pure batch was not used for the
actual logic.

**Why**: The launcher needs to reliably do things batch cannot do well:
parse a JSON health-check response and distinguish "ROLE OS is up" from
"something else is on this port," start a background process detached
and minimized while capturing its stdout/stderr to separate log files,
resolve a redirected/localized Desktop folder for the shortcut, and
identify a process by its actual command line (not just its PID) before
killing it. `-ExecutionPolicy Bypass` on the `.bat` wrapper means the
user never has to change a system-wide PowerShell execution policy or
run as Administrator — the bypass applies only to that one invocation.

**How to apply**: Keep all real logic in the `.ps1` files; a `.bat` file
should only ever resolve its own directory (`%~dp0`) and hand off to
PowerShell. If a future Windows-only tool needs more than a few lines of
conditional logic, prefer this same pattern over growing a batch script.

---

## The launcher's "already running" check is a live health probe, not a PID-file trust

**Decision**: `Start-RoleOS.ps1` decides whether ROLE OS is already
running by calling `GET /health` and checking that the JSON body's
`"app"` field equals `"ROLE OS"` — not by checking whether the PID file
exists, and not by checking whether *anything* is listening on port 8000.

**Why**: A PID file only tells you what the launcher itself last
started; if the user started ROLE OS manually (e.g. `uvicorn
app.main:app` in a terminal), a PID-file check would wrongly conclude
nothing is running and start a second, port-conflicting server. A bare
TCP-connect check would wrongly treat *any* service on port 8000 as
ROLE OS. The health payload's `app` field is the one signal that is both
always present when ROLE OS is actually up, and specific enough to
correctly reject a different application occupying the port (verified in
testing: a plain, non-ROLE-OS HTTP listener on 8000 is correctly reported
as "port already in use by a different application," not silently
treated as ROLE OS already running).

**How to apply**: The corollary is that `Stop-RoleOS.ps1` **does** rely on
the PID file — deliberately, and only when the PID's own command line
also contains `uvicorn` and `app.main:app`. Stopping a process is
destructive and must be conservative (only touch what we're sure we
started); detecting whether to start one is not, and should be
optimistic about finding an existing, healthy instance however it was
started.

---

## Launcher runtime files are co-located with the Session domain's own data, under `dashboard\var\role_os_dashboard\`

**Decision**: `role_os.pid`, `launcher.log`, `uvicorn.out.log`, and
`uvicorn.err.log` are all written to `dashboard\var\role_os_dashboard\` —
the same directory `app/config.py`'s `session_db_path` already defaults
to (since the launcher always starts uvicorn with `dashboard\` as the
working directory, matching that default's own resolution).

**Why**: One runtime directory for all of ROLE OS's local, git-ignored
state is simpler to document, find, and clean up than two. The
alternative (a repo-root-level `var\role_os_dashboard\`, sibling to
`dashboard\`) would have meant the launcher's files and the app's own
session database lived in different places for no functional reason.

**How to apply**: Any future local, git-ignored runtime file this product
needs should default into this same directory unless there's a specific
reason to isolate it (the way the Alpha demo's `var\role_os_alpha\`
already is, for a deliberately different purpose: seeded demo data, not
live runtime state).

---

## The Session domain is a new top-level domain, not folded into Project Intelligence

**Decision**: The ROLE OS Dashboard MVP's Start/End My Day feature lives in
a new `app/session/` domain with its own SQLite file
(`role_os_session.db`), rather than as new fields on `app/projects`
(Project Intelligence) or a new collection type alongside `notes`/
`decisions`/`todos`.

**Why**: A daily session (date, mode, objective, expected result, one
active-at-a-time constraint, a generated Claude prompt, a generated
Markdown record) is a different kind of object from a Project Intelligence
project or its collections — it has its own lifecycle (Not Started →
Active → Completed) and its own uniqueness constraint (at most one active
session system-wide) that doesn't map onto any existing table. Reusing
`app/projects` would have meant either bending its schema to fit an
unrelated concept, or adding session logic to a module whose job is
already fully defined (health scoring, capabilities, dependencies).

**How to apply**: This follows the same test as the Sprint 5 Knowledge
Graph precedent below: a new capability gets its own top-level domain when
it has its own data shape and lifecycle with no logic to share, even if it
superficially touches an existing concept ("projects"). The local project
*registry* the Session page also introduces is deliberately lightweight
(name/status/reference/milestone/next_action) and does not attempt to
replace or sync with Project Intelligence's much richer project model —
they answer different questions ("what ROLE Ecosystem product is this?"
vs. "how healthy is this Project Intelligence project?").

---

## The Session page is a new page, not an extension of Home

**Decision**: The Session page is a new sidebar item/route (`#/session`,
`renderSessionPage()`) rendering entirely separate content from Home.
Home's own markup, data sources, and layout are untouched.

**Why**: Same reasoning as the Sprint 7 Dashboard decision below — Home
already *is* a dashboard, built over Project Intelligence/Advisor/Graph
data. The Session page needs an entirely different question answered
("what am I doing today, and what's my status?") from an entirely
different, brand-new data source (the Session domain), with no natural
shared layout with Home's Today's Focus/Workspace Overview/Health
Dashboard.

**How to apply**: See the Sprint 7 entry below for the general rule this
follows.

---

## Cross-repository reads (ROLE Ecosystem decisions) are opt-in, never path-guessed

**Decision**: `app/session/decisions_adapter.py` only reads
`role-ecosystem/DECISION_LOG.md` live when the user explicitly sets
`ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH`. It never guesses a relative path
between the two repositories, even though on this machine, today, one
exists.

**Why**: `role-ecosystem` and `ROLE_OS` are separate repositories with no
guaranteed common location — a different clone, a different machine, or a
CI runner would break a guessed relative path silently or loudly. Every
other environment-derived value in `app/config.py` already follows this
"explicit env var, honest fallback if unset" pattern; this is the same
seam applied to a cross-repository read for the first time.

**How to apply**: Any future feature that wants to read something from
another ROLE Ecosystem repository should follow this same shape: a
dedicated adapter function, an explicit, documented environment variable
with no default guess, and a clearly-labeled fallback (not a crash, not a
silent empty result) when it isn't configured or the read fails. See
[[../architecture/06_DEVELOPMENT_RULES]]'s "Never duplicate data into a
new store" rule — the fallback here is a deliberately small snapshot, not
a second copy of the full log.

---

## No external AI/LLM API is called anywhere in the system

**Decision**: Every extractor, Health Score signal, Advisor rule, and
Knowledge Graph relationship is deterministic and rule-based. No OpenAI,
Claude, or any other model API is called by the Builder or Dashboard.

**Why**: Determinism makes every output reproducible and fully
explainable — a recommendation or relationship can always be traced back
to the exact data that produced it, with no risk of hallucination, API
cost, latency, or a network dependency for a tool meant to run entirely
against local SQLite files. Explainability was treated as a core product
requirement for the Advisor specifically (Epic 2), not a nice-to-have.

**How to apply**: Any future feature that seems to call for "AI" should
first be checked against the existing deterministic toolkit
(`app/advisor/scoring.py`, the Health Score signals) — most "make this
smarter" asks can be served by a better rule or signal. Where an LLM
genuinely adds value (e.g. rephrasing a recommendation's wording), it
must go through the narrow `AdvisorNarrativeProvider` seam and must not
change *what* the deterministic core decides. See
[[../architecture/06_DEVELOPMENT_RULES]].

---

## The Knowledge Graph is a compute layer, not a fourth database

**Decision**: `build_graph()` recomputes the full graph from the Builder,
Project Intelligence, and (on demand) Advisor databases on every request,
rather than persisting graph state anywhere.

**Why**: A persisted graph would need to be kept in sync with three other
independently-mutated databases, creating a class of bugs (stale
relationships, drift between a project's real state and its graph
representation) that simply cannot occur if the graph is always freshly
derived. The same "recompute on read" pattern was already validated by
the Advisor in Epic 2, so Epic 3 reused it rather than introducing a new
consistency model.

**How to apply**: Prefer computing derived data on read over persisting a
copy, unless there's a demonstrated performance problem that recomputation
can't solve (there hasn't been one yet — see the Performance section of
[[../architecture/05_UI_GUIDELINES]] for how the UI avoids the N+1 pattern
that would otherwise make recompute-on-read expensive).

---

## Project Intelligence lives under `/pi`, not `/projects`

**Decision**: The existing `/projects` endpoint (a Milestone 1 knowledge-
API concept: conversation counts grouped by a classifier string) was left
untouched. First-class Project records got a new namespace, `/pi/*`,
entirely.

**Why**: `/projects` and a first-class "Project" record are genuinely
different concepts that happen to share a name. Reusing the endpoint would
have silently changed its meaning for existing consumers; a new namespace
avoided that ambiguity entirely rather than requiring a version bump or a
breaking migration.

**How to apply**: When a new concept's natural name collides with an
existing endpoint's name, prefer a new namespace over overloading the old
one — even if it means a slightly less intuitive URL. See
[[../architecture/02_PRINCIPLES]] §3.

---

## Epic 4 (Command Center) introduced zero backend changes

**Decision**: The entire dashboard UI redesign — new sidebar, hash router,
Home/Project/Graph/Advisor/Assets/Settings pages, and design system — was
built with no new API endpoint, database, or backend logic.

**Why**: Every piece of data the new UI needed already existed behind an
endpoint from Milestones 1–3 or Epics 1–3. Building it as a pure
presentation layer kept the backend's test coverage and behavior
completely stable through a large, highly visible change, and proved the
existing API surface was actually sufficient to power a real product UI —
a useful validation of the additive-namespacing decisions made in Epics
1–3.

**How to apply**: Before adding a backend endpoint for a UI feature,
confirm the data really isn't available through composition of existing
endpoints first. See [[../architecture/05_UI_GUIDELINES]].

---

## Builder has zero third-party dependencies

**Decision**: `builder/requirements.txt` intentionally stays empty of
third-party packages; the entire extraction pipeline is standard-library
Python.

**Why**: The Builder is meant to run as a simple, portable CLI (including
via `run_windows.bat` for non-technical use) against a user's own ChatGPT
export, with nothing to install and nothing that can break from a
dependency update or an unavailable package index.

**How to apply**: Adding a third-party dependency to the Builder should be
treated as a significant, deliberate decision requiring explicit
justification — not a default choice for convenience.

---

## Sprint 5's Knowledge Graph is a second, independent graph — not an extension of Epic 3's

**Decision**: `dashboard/app/conversation_graph/` is a standalone graph
domain with its own vocabulary (8 lowercase node types, one `contains`
relationship), its own API (`/conversation-graph`), and its own UI page —
computed from the imports/extraction databases. It does not extend
`app/graph/`'s `NODE_TYPES`/`RELATIONSHIP_TYPES`, does not add a builder
to `app/graph/builders/`, and does not share node ids with Epic 3's graph
even where a type name is the same (e.g. both have a "Person" concept,
but they're different nodes from different pipelines).

**Why**: Epic 3's graph vocabulary is frozen and test-locked —
`dashboard/tests/test_graph_api.py` asserts `GET /graph/meta/types`
returns exactly 12 node types and 12 relationship types, and three
architecture docs document "12 node types / 12 relationship types" as a
fixed fact (see [[../architecture/04_DATA_MODEL]]). Sprint 5 needed three
node types Epic 3 doesn't have (`Task`, `Idea`, `Document`) and a
relationship type it doesn't have (`contains`); adding them would have
broken a currently-passing test and contradicted the documented
"12/12" vocabulary. Beyond the test, the two graphs' overlapping type
names describe genuinely different things: Epic 3's `Conversation` nodes
come from the Builder's `knowledge_cards`; Sprint 5's `conversation` nodes
come from the imports database. Merging them under one id scheme risked
silently conflating two unrelated pipelines' data the first time a name
collided (e.g. two different `Person` slugs computed differently by each
pipeline landing on the same node, silently merging unrelated context).

**How to apply**: Don't extend Epic 3's `NODE_TYPES`/`RELATIONSHIP_TYPES`
tuples to accommodate a new feature unless that feature's data genuinely
belongs to the same three source databases (Builder, Project
Intelligence, Advisor) Epic 3 already reads. A new pipeline with its own
data source is a case for its own small graph domain, following this same
"compute layer, not a database" pattern (see the entry above) at whatever
smaller scale that pipeline needs — not a case for growing Epic 3's
vocabulary or reusing its id scheme.

---

## Sprint 6's Advisor Search is a sibling module inside `app/advisor/`, not a merge into the recommendation engine

**Decision**: Keyword search over conversations/extracted objects lives
in two new files, `app/advisor/search.py` and
`app/advisor/search_models.py`, registered through a **separate** FastAPI
router (`routers/advisor_search.py`) that happens to share the
`/advisor` URL prefix. Epic 2's recommendation engine — `db.py`,
`engine.py`, `rules/`, `scoring.py`, `narrative.py`, and
`routers/advisor.py` — is not modified, and search results are not
folded into `Recommendation` objects or the Daily Brief.

**Why**: "What should I work on next?" (Epic 2 — rule-based scoring over
Project Intelligence data, persisted dismiss/complete state) and "where
is everything about X?" (Sprint 6 — stateless keyword search over
imported conversations and extracted objects) are different questions
with different data sources and no shared logic; there was nothing to
gain from merging their code. But unlike the Sprint 5 Knowledge Graph
decision above, there was also no *test-locked vocabulary* or *identity-
collision* risk forcing a fully separate top-level domain — search has no
fixed type count to violate and no id scheme that could collide with
Epic 2's. So the answer here isn't "merge" or "fully separate," it's
"sibling": new files alongside the existing ones, under the same
conceptual umbrella (the Advisor page now does two related but distinct
things), registered as a second router so the diff to Epic 2's existing,
already-tested router is exactly zero lines.

**How to apply**: When a new capability is conceptually part of an
existing feature area but has its own data source and no logic to share,
prefer adding sibling files/routers within that area's package over
either (a) editing the existing files to accommodate the new logic, or
(b) spinning up a whole new top-level domain out of caution. Reserve (b)
for cases like the Sprint 5 entry above, where a shared vocabulary or id
scheme would create real collision risk.

---

## Sprint 7's Dashboard is a new page, not an extension of Home

**Decision**: The Dashboard is a new sidebar item/route (`#/dashboard`,
`renderDashboardPage()`) rendering entirely separate content from Home.
Home's own markup, data sources, and layout (Today's Focus, Workspace
Overview, Health Dashboard, Recent Activity, Knowledge Graph Preview,
Quick Search) are untouched.

**Why**: Home already *is* a dashboard — Epic 4 built it as one — but
over a specific pipeline (Project Intelligence, the Advisor's
recommendations, the Epic 3 Graph). Sprint 7 asked for summary
cards/recent activity/system status/quick actions over a different
pipeline entirely (Importer, Explorer, Extraction, the Sprint 5 Knowledge
Graph, Advisor Search) — different endpoints, different metrics, no
overlap. Cramming a second, unrelated set of cards and activity feeds
into Home's existing two-column layout would have meant reworking a page
that already works, for no benefit: nothing about the two pipelines'
data relates closely enough to justify sharing one page's layout logic.

**How to apply**: A new "give me an overview of X" request is a case for
extending an existing overview page only when X is close enough to what
that page already summarizes that a shared layout still reads as one
coherent view. When X is a different pipeline with its own metrics and
no natural connection to the existing page's content, a new page (reusing
the same design-system pieces — card grids, animated counters, activity
lists — without reusing the *page*) keeps both simple.

## Workspace Adoption stores its overlay in its own table, not columns on `projects` — and Sprint 3's hierarchy is a new field, not a repurposed one

**Decision**: Adopting a discovered folder (Sprint 2) writes to a new
`adopted_projects` table in a new `role_os_workspace.db`, never to
`role_os_projects.db`'s `projects` table — a deviation from the original
`08_IMPORT_ENGINE_PROPOSAL.md` §14, which had proposed adding `root_path`
etc. columns directly onto `projects`. And Project Boundary (Sprint 3)'s
hierarchy fields (`item_kind`, `parent_item_id`, `is_top_level_project`,
...) are new fields on `DiscoveredProject`, kept entirely separate from
`classification` (Software Project/Website/Mixed Project/...) even though
both are "what kind of thing is this" questions about the same folder.

**Why**: Two different but related judgment calls, both resolved the same
way. For the overlay table: keeping it out of `role_os_projects.db`
means manually-created Projects are *structurally* guaranteed unaffected
by anything in `app/workspace/` — not just "tested to still work," but
physically incapable of being broken by it, since it isn't the same file,
table, or code path. For `item_kind` vs. `classification`: `classification`
answers "what kind of project is this" (a per-folder, parent-agnostic
question); `item_kind` answers "where does this sit in the real project
tree" (a question that can only be answered by looking at the whole
scan's parent/child relationships at once, in a corpus-level pass — see
`boundary/hierarchy.py`, modeled on the existing
`recommendation/container_override.py` corpus pass). Folding hierarchy
into `classification` would have meant a single field trying to answer
two unrelated questions — "Mixed Project, but also nested" has no clean
single value.

**How to apply**: When new state is *about* an existing domain object but
answers a genuinely different question than that object's existing
fields (or lives in a different domain's database on principle, as with
discovered-vs-manual projects), give it its own field/table rather than
overloading or extending an existing one — even if the two are almost
always shown together in the UI. The Sprint 3 Workspace page renders
`classification` and `item_kind` side by side on the same row; they never
needed to be the same field to do that.

---

## Project Intelligence Wiring (Sprint 4): a sibling Workspace Advisor, a separate Discovered Project Detail view, and adoption as the scoping gate

**Decision**: Three related choices, all made the same way. (1) Sprint 4's
rule-based recommendations over discovered projects live in a new
`app/workspace/advisor.py`, never inside `app/advisor/` (Epic 2's engine).
(2) Discovered/adopted projects get a new detail view (`#/dproject/{id}`,
`renderDiscoveredProjectDetail`), never an extension of the existing
`renderProjectDetail`/`#/project/{id}` built for manually-created `/pi/
projects`. (3) Home, Advisor, Assets, and Activity all scope to *adopted*
top-level projects only (`list_enriched_top_level_projects(adopted_only=
True)`), not every discovered-but-unadopted one, even though the latter
are equally real.

**Why**: (1)/(2) are the same judgment as Sprint 3's `item_kind` decision
above, applied again: Epic 2's advisor reasons over manually-entered
TODOs/deliverables/decisions with zero filesystem or git knowledge; a rule
like "dirty git tree" or "no tests detected" has no home there at all — a
new sibling file, not a rewrite, keeps Epic 2's tested engine at zero risk
while still letting both recommendation lists render on one Advisor page.
Same for the detail view: a manually-created Project's sections (Notes,
Capabilities, Dependencies, Related Projects) don't exist for a discovered
folder, and a discovered folder's sections (Git, real Documentation
status, discovered Assets) don't exist for a manual Project — forcing one
template to handle both would mean scattering `if isDiscovered` branches
through a 117-line render function that has worked, untouched, since v1.4.
(3) is a scoping call, not an architecture one: "adoption" is the
explicit, existing "yes, this is one of my real projects" signal Sprint 2
built specifically so the user decides what counts — Home/Advisor/Assets
honoring that boundary is the product working as designed, not a
limitation. A user can always adopt a project from the Workspace page to
bring it into these views.

**How to apply**: When a new capability's data model has *no field
overlap at all* with an existing similar-sounding feature (a "second
advisor," a "second project detail page"), that's the signal for a
sibling file/view, not a shared one with conditionals — the `container_
override.py` / `boundary/` precedent from Sprints 1-3 generalizes past
Discovery into any domain. Separately, when a feature already has an
explicit user-consent gate (adoption, in this case), route new dependent
views through that same gate by default rather than inventing a second,
looser one ("discovered" vs. "adopted") — one clear boundary is easier to
reason about than two overlapping ones, and the stricter gate is always
one click away from being satisfied.

## Project Unification (Sprint 5): a bidirectional nullable bridge, not a merged schema

**Decision**: Manually-created Projects (Epic 1) and discovered/adopted
projects (Discovery Engine + Workspace Adoption) are unified into one
user-facing concept, "Project," without merging their storage. The bridge
is two nullable columns — `projects.discovery_item_id` and
`adopted_projects.canonical_project_id` — resolved lazily and idempotently
by `app/workspace/identity.py::get_or_create_canonical_project_id()`. A
canonical Project row created this way holds only a name and the
`Discovered` workspace; every other field a discovered project has (git
status, health score, documentation status, assets) is never copied in —
it continues to live exclusively in the Workspace scan cache and is read
fresh on every request, the same "filesystem is the source of truth"
principle Sprint 2 established for the overlay table itself.

**Why**: AI Sessions, Snapshots, and Timeline are Epic 1 features built
against a real `projects.id` foreign key; rewriting them to also accept a
discovery-item hash would touch a tested, working subsystem for no
functional gain. A bridge lets every existing `/pi/projects/{id}/*`
endpoint keep working completely unmodified — verified by running the
pre-existing AI Sessions test suite (47 tests) against the refactor
untouched, and by a new integration test that calls those same endpoints
against a freshly-resolved canonical id. Keeping the canonical row minimal
(rather than copying discovery metadata into it) avoids the double-
maintenance problem Sprint 2 already solved once for the overlay table:
two copies of the same fact drift, and the filesystem/git state is always
the correct one to trust. The bridge is intentionally *lazy* (created on
first adoption or first read, not on scan) and *self-healing* (a stale
link — its Project row deleted out-of-band — silently re-resolves rather
than returning a dangling id), because the Workspace scan cache can be
rebuilt at any time and must never be blocked on Project Intelligence
being in a particular state.

**How to apply**: When two existing subsystems need to refer to "the same
real-world thing" but were built against different identity schemes,
prefer a small bidirectional nullable link resolved by one idempotent
function over a data migration that forces one scheme onto the other —
especially when (like here) one side owns rich, frequently-changing,
filesystem-derived data that must never be duplicated. Route every new
cross-cutting feature (Resume Work, Home's Quick Resume, Advisor's
recommendation links) through the *canonical id*, never through the raw
discovery-item id directly — `get_enriched_item`'s Sprint 4 bug (AI
Sessions silently querying with the wrong id and always returning empty)
is the concrete failure mode this guards against.

## ProjectContext (Sprint C1) is a thin composition layer over existing services, not a fifth "project" concept

**Decision**: `app/project_context/builder.py` introduces no new storage,
no new identity scheme, and no new enrichment logic. It calls
`app.workspace.identity`, `app.workspace.service.enrich_project_item`,
`app.projects.db`, `app.workspace.advisor`, and `app.advisor.engine`
exactly as they already exist, and assembles their output into one
`ProjectContext` dict. Every field in it can be traced back to a function
that was already computing that value somewhere; the builder's only new
logic is the health-score tier bucketing (three thresholds) and the
advisor-recommendation field-name normalization (mapping both engines'
native shapes into one output shape) — both pure, stateless, and
reversible.

**Why**: the consolidation audit that opened this sprint found four
independent "what is a project" concepts (manually-created Project
Intelligence, Discovery/Workspace-scanned items, Epic 2's Advisor, and
Workspace Advisor 2.0), plus a fifth, older, unrelated one
(`knowledge_cards.project`, a free-text field with no real identity link
to any of the above). Rewriting any of the four into the others was
explicitly out of scope and would have put four sprints of tested,
working behavior at risk for a purely organizational goal. A composition
layer gets the stated outcome — one object every page *can* request
instead of reassembling its own subset — without that risk: every
existing endpoint keeps its exact response shape (verified by the full
pre-existing suite passing unmodified), and `ProjectContext` is available
new API real estate, not a replacement for what's already there.

**How to apply**: When several already-correct subsystems need to be
presented as "one thing" to the UI, prefer a read-only assembly function
over a migration or a rewrite — especially when (as here) the sprint's
own instructions explicitly forbid rewriting the systems being
consolidated. Two real bugs (`get_home_portfolio`'s always-`None`
`latest_ai_session`, `get_enriched_item`'s duplicate AI-session query)
were found and fixed *as a side effect* of building this layer, without
touching any endpoint's contract — that is the kind of win a composition
layer should look for: not "what can I delete," but "what is quietly
wrong because nothing owns the full picture yet."

## A consolidation module is only real once production routes actually depend on it (Sprint C1B)

**Decision**: Sprint C1 built `ProjectContext` correctly-shaped but did not
rewire any screen's primary endpoint to use it — Cockpit's one optional
`/project-context/{id}` fetch, wrapped in a swallowed try/catch, was its
only production caller. An audit of the running system (not its docs)
found that deleting the module would have broken nothing. Sprint C1B's
job was narrowly "make the existing object load-bearing," not "build a
better object" — the shape from C1 was correct; the wiring wasn't. Every
production endpoint this sprint touched (`/workspace/home`,
`/workspace/discovered?view=top_level`, `/workspace/discovered/{id}`,
`/pi/projects`, `/pi/projects/{id}`, `/workspace/advisor`,
`/advisor/recommendations`) now embeds a `project_context` built from one
call to the canonical builder, computed from data the router already
fetched (no duplicate enrichment pass).

**Why**: a consolidation sprint that stops at "the unifying object exists
and is tested in isolation" produces a scaffold, not a fix — the audit's
own finding was that a health-tier bug the module claimed to prevent
(disagreeing 80/50 vs 70/40 thresholds) was still live in production,
because nothing consumed the module's opinion on the matter. The
correction standard adopted here — "prove that deleting the module would
break real screens" — is a stronger, falsifiable bar than "the module has
tests," and is the one this project will hold future consolidation sprints
to.

**How to apply**: When a follow-up sprint's brief says "make X load-
bearing" after a prior sprint built X, resist the urge to redesign X.
Verify first (by grep, not by re-reading the prior sprint's own
completion report) exactly which production code paths call it today, fix
the wiring gap specifically, and add a test *per screen* asserting the
dependency exists (not just that the module's own unit tests pass) — a
module with zero real callers and 100% test coverage on itself will still
report a misleadingly high "done" signal without that per-screen check.

## Dashboard composition reuses existing services; a genuinely missing rule can extend an existing rule set (Sprint C2)

**Decision**: `app/dashboard/service.py` introduces no new database, no new
identity scheme, and no new scoring engine. It calls `ProjectContext`
(workspace + manual-project variants), `workspace.service.get_home_
portfolio`, `workspace.advisor.generate_recommendations`, `workspace.
service.list_activity_feed`/`list_project_assets`, and `app.db`'s
Knowledge counts exactly as they exist, and shapes their output into one
executive-dashboard payload. The one exception — `rule_snapshot_blocker`,
added to `workspace/advisor.py`'s existing eleven-rule set — was added
only because the brief explicitly asked for "blocker from latest
snapshot" as Needs Attention evidence and no existing rule (or any other
service) surfaced it; it follows the identical pure-function-over-one-
enriched-item shape as every other rule, in the same file, in the same
list.

**Why**: the legacy Dashboard's zero-centric metrics were a wiring bug,
not a data-modeling problem — `/import/metrics` (Explorer's own extracted-
knowledge-object counts) was simply the wrong data source for a page
labeled "Dashboard," while the real project data (health, recommendations,
activity, assets, sessions) already existed and was already being served
correctly to Home/Workspace/Advisor. A parallel aggregation engine would
have re-solved a problem this codebase's Sprint C1/C1B consolidation work
had already solved once; the only new code this sprint needed was
composition and one honestly-missing piece of evidence surfacing.

**How to apply**: Before adding a new scoring/ranking function to answer a
dashboard-shaped question ("what should I do next," "what's healthy"),
check whether `workspace.advisor`, `workspace.portfolio`, or
`ProjectContext` already answers it — if the answer just needs a new
*evidence type* surfaced (like a snapshot blocker), extend the existing
rule set in place rather than starting a second one; if the answer needs
combining outputs from several already-correct services, write a thin
composition function (return their output, grouped/counted, never
recomputed) rather than an engine that re-derives what they already know.

## A generated cache directory must be excluded by its real resolved path, not an assumed one (Sprint C4)

**Decision**: `app/assets/service.py`'s exclusion of ROLE OS's own runtime
data directory (the folder holding the generated thumbnail cache and
per-domain SQLite files) is computed from `Settings.asset_thumbnail_cache_
dir`'s own resolved parent, not from a separately-assumed `repo_root /
"var"` path. Every `var/`-relative default in `config.py` is a *relative*
path, resolved via `Path(...).resolve()` against the process's current
working directory at `Settings()` construction time — not against
`repo_root`, which is derived from `__file__`. Launching the server with
cwd=`dashboard/` (the normal `uvicorn app.main:app` workflow) and cwd=
repo-root therefore resolve the same relative default to two different
physical directories.

**Why**: found live, not by a unit test — indexing ROLE_OS's own checkout
(a real adopted project, since it contains the running dashboard) walked
its own just-generated thumbnail cache back in as "discovered assets,"
which then got re-thumbnailed on the next scan, compounding. The first
fix attempt hardcoded the exclusion to `repo_root / "var"`, which matched
in one test run but not after a server restart from a different launch
cwd — the thumbnails had actually landed at `dashboard/var/...`, not
`var/...` at the repo root, because the exclusion check and the actual
cache-writing code weren't derived from the same value.

**How to apply**: when excluding a directory that this codebase itself
generates output into, never re-derive its expected location from a
different config field (`repo_root`, a literal, an assumption about
"where things usually are") — read the *same* resolved `Settings` field
the writer itself uses. Two independently-computed paths that are
"supposed to" describe the same directory will drift the moment either
one's resolution context (cwd, environment) changes; one shared value
can't drift from itself. This generalizes past this one exclusion: any
future check that says "this is where X lives" should import X's own
already-resolved `Settings` value rather than reconstructing it.

That single-value exclusion still has a blind spot, though: it only
knows about *this process's own* resolved runtime directory. A second,
unrelated process (a pytest run launched from the repo root, a second
dashboard instance, anything with a different cwd) can independently
resolve the same relative default to a *different* physical directory,
which the first process's single-path check has no way to see. The
actual fix layers a second, structural exclusion on top: `role_os_
dashboard` — the one literal path segment every `var/`-relative default
in `config.py` shares, regardless of which `var/` parent it resolves
under — is excluded by *name*, the same way `.git`/`node_modules` are,
so every physical copy is caught structurally instead of one path at a
time. When a resolved-path check is protecting against "our own
generated output," ask whether a second process with a different
resolution context could produce a second copy this check can't see —
if the directory name itself is a stable, code-owned constant, prefer
excluding by that name over (or in addition to) any one resolved path.

## A "resolved only in one caller" field is as dangerous as a second implementation (Sprint C4.1)

**Decision**: `AssetRecord.duplicate_group_id` is now resolved (nulled out
for non-duplicates) inside `index_project_assets` itself, the function
every direct caller uses, rather than left as a raw candidate value that
only `list_all_assets` (the `/assets` API's own aggregator) happened to
post-process via `group_duplicates`.

**Why**: found during the Sprint C4.1 canonicalization audit, not by a
unit test. `_build_record` set `duplicate_group_id = duplicate_hash`
unconditionally — a deliberate raw value, with a comment saying
"resolved to a real group only if 2+ share it — see `group_duplicates()`."
But `group_duplicates()` was only ever called inside `list_all_assets()`.
Every other direct caller of `index_project_assets` — Dashboard's recent
assets, Home's recent assets, `ProjectContext.assets_count`'s recent-
activity block, Project Hub's assets summary — got the *raw*, unresolved
value: every hashable file showed a non-null `duplicate_group_id`, even a
genuinely unique one, while `/assets`/`GET /assets/duplicates/{id}`
correctly treated the same file as not a duplicate. This is the same
class of bug as the "generated cache directory excluded by resolved path,
not an assumed one" decision earlier in this file (two code paths that
are "supposed to" agree, verified only by inspection, not by a shared
value or a test) — except here there was no second *implementation* to
point at, just a post-processing step one caller applied and every other
caller silently skipped.

**How to apply**: when a field's "real" value depends on a whole-list
pass (grouping, deduplication, ranking) rather than being computable from
a single record in isolation, don't leave that pass as something each
caller must remember to apply — apply it once, inside the function that
produces the list, so every caller gets the same already-correct value by
construction. If a genuinely raw/unresolved variant is ever needed by
some caller, name it differently (e.g. `duplicate_hash` already exists as
the honest "the raw signal" field) rather than let two callers disagree
about what the same field name means. This generalizes past duplicate
grouping: any "field X is only really valid after step Y" contract is a
latent cross-screen inconsistency until step Y is unconditional.

## A canonical asset system is proven by absence, not presence — the Sprint C4.1 audit method (Sprint C4.1)

**Decision**: Sprint C4.1 did not add a "does everything look right"
checklist — it searched for every symbol a second implementation would
need (`AssetRecord`, `duplicate_hash`/`_group_id`, classification
functions, MIME/dimension reading, override writes) across the entire
backend and frontend, and required every match to resolve to the one
canonical `app.assets` implementation or a documented, empty compatibility
shim. It also added source-tree-inspecting tests (`ast`-based, not
behavior-based) asserting *no second definition of these function names
exists anywhere in `app/`*, so the property the audit proved true stays
enforced automatically rather than needing to be re-audited by hand next
sprint.

**Why**: a screen-by-screen "looks correct" pass can miss a duplicate
implementation that happens to produce the same output today (e.g. two
classifiers that agree on the current test fixtures but would diverge on
a new file pattern) — the actual C4.1 bug found (`duplicate_group_id`
resolved in one caller, not others) was invisible to every existing
screen-level test because both the raw and resolved values were *usually*
similar-looking (both non-null for a hashable file), and no test compared
the same real asset's fields across two different endpoints.

**How to apply**: when auditing "is there one source of truth for X,"
search for the symbols a second implementation would necessarily define
or touch (not just the screens that display X), and verify the *absence*
of a second definition — then encode that absence as a test (source-
inspection if behavior-level testing can't distinguish "coincidentally
agrees today" from "provably the same code path"). A completion report
claiming full canonicalization is a claim to verify against the source,
not a fact to inherit from a prior sprint's own summary of itself.

## Where to go next

- [[../architecture/01_VISION]] and [[../architecture/02_PRINCIPLES]] — the
  standing principles these decisions are instances of.
- [[CHANGELOG_PRODUCT]] — the product-facing history these decisions shaped.
