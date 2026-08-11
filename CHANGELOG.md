# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- **Executive Decision Engine, Sprint C10** — ROLE OS moves from an
  information dashboard to a deterministic decision system: one call
  answers "what should I work on next?" using evidence from every
  existing domain (Project Context, Operational Intelligence, Project
  Ecosystem, Impact Analysis, Project Memory). No LLM, no embeddings, no
  AI API, no hidden weighting. New package, `app/executive_decision/`
  (`models.py`, `scoring.py`, `planner.py`, `service.py`, `api.py` inside
  the package itself, matching Sprint C9's convention), and one new
  endpoint, `GET /executive-decision`.
  - **Canonical `ExecutiveDecision`** (`models.py`): `generated_at,
    recommended_project, decision_score, confidence, reason,
    expected_benefit, estimated_effort, estimated_duration,
    blocking_projects, projects_unblocked, commercial_value,
    technical_value, risk, dependencies, today_plan, expected_result,
    evidence, limitations`.
  - **Scoring** (`scoring.py`): a fixed, additive, fully-documented point
    table -- never a learned/hidden weight. Nine contributors, each a
    pure function returning `(points, reason | None)`: Operational
    Intelligence priority (scaled), business value/launch-readiness,
    projects unblocked (capped), already-blocking-dependents bonus,
    Impact Analysis risk level, Project Memory pending work, recent
    activity (bonus) / staleness (penalty), project health score, and a
    paused/blocked status penalty. Every non-zero contribution is named
    in `evidence`, in the fixed order the function evaluates them --
    never a black box. Stale Discovery data discounts *confidence*, never
    the score itself.
  - **Conflict resolution** (`service._sort_key`): every adopted project
    is scored once and sorted by `(decision_score desc, health_score
    desc, canonical_project_id asc)` -- a total order with no ties
    possible, ever, regardless of how many projects score identically.
  - **Today's Plan** (`planner.py`): a single deterministic step for the
    recommended project -- `"09:00"` is a fixed label, not a real-clock
    computation; no scheduling engine, no calendar integration.
    Estimated effort/duration come from a static keyword lookup over the
    recommended action's own title, the same convention
    `operational_intelligence.models.expected_benefit_for` already
    established.
  - **No duplicate logic**: reuses Project Memory's own pending-work/
    next-action synthesis via direct import (never re-implemented), the
    Project Ecosystem graph's `dependents_of`/`blocks_of`/`dependencies_of`
    for blocking/unblocking, and Impact Analysis's `overall_risk` verbatim.
  - **Consumers**: Mission Control (`GET /mission-control`) gained
    `executive_decision`/`ranked_projects` fields, computed inside the
    same `request_scope()` that already collapses the shared-assets
    filesystem walk to once per request -- the frontend now leads with a
    "TODAY" card (recommended project, reason, expected benefit,
    estimated effort/duration, next action, expected result, evidence)
    and a "Portfolio Ranking" section (every adopted project, ranked,
    each with its own top reasons), both above the pre-existing
    operational cards, which are now supporting information. Explorer
    search gained a new result type, `"Executive Decision"` -- searching
    "today"/"decision"/"recommend"/"priority"/"focus"/"next", or the
    recommended project's own name, surfaces one card summarizing the
    current decision.
  - **Real bug found and fixed while wiring Mission Control**: the first
    integration placed the new `get_executive_decision` call just after
    Mission Control's existing `request_scope()` block closed, so
    Executive Decision's own `compute_relationships` call re-walked the
    filesystem for shared assets once per adopted project instead of
    reusing the walk `request_scope()` already collapsed to one --
    caught immediately by the existing
    `test_no_double_asset_walk_per_project_per_request` regression test;
    fixed by moving the call inside the shared scope.
  - **Real bug found and fixed while live-verifying Explorer**: the
    frontend's `RESULT_TYPE_ORDER` array (a render-order list separate
    from the backend's `RESULT_TYPES`) had never been updated for Sprint
    C8/C9's `"Ecosystem Relationship"`/`"Impact"` result types either --
    both had been silently invisible in the UI since those sprints
    shipped. Fixed by adding all three missing types
    (`"Executive Decision"` plus the two pre-existing ones) in the same
    pass.
  - **Real bug found and fixed by the full (not targeted) regression
    run**: a test assumed the workspace had zero adopted projects
    globally, relying on the `settings` fixture's fresh database paths --
    but the Workspace/Discovery overlay (where "adopted" status lives)
    is a single, session-wide store the fixture doesn't isolate, so real
    projects adopted by ~30 earlier test files were still present by the
    time this test ran in a full-suite pass. Reproduced deterministically
    and fixed by passing empty `all_contexts`/`enriched_items` directly
    to `get_executive_decision()` instead of depending on global
    emptiness.
  - **Performance**: reuses `all_project_contexts`/Operational
    Intelligence/`compute_relationships`/Impact Analysis exactly once per
    request; Executive Decision's own scoring/ranking/planning logic adds
    ~2ms on top (profiled on the real workspace). End-to-end latency is
    dominated by the pre-existing `all_project_contexts`
    (~750ms)/`compute_relationships` (~570ms) costs already documented in
    the C6/C8 reports for this real, ~18-project workspace -- the
    brief's 500ms target is not met on this workspace as a result, an
    inherited, already-known cost rather than one this sprint introduced.
  - **Tests**: `dashboard/tests/test_executive_decision.py` (31 tests) --
    every scoring contributor, the effort/duration lookup, Today's Plan
    shape, conflict resolution (never a tie, verified deterministic
    across repeated calls), portfolio ranking order, the adopted-only
    security boundary, the API, Mission Control integration, Explorer
    integration, and two performance-passthrough regressions.
  - **Real workspace verification**: live-verified against
    `C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS` --
    ROLE Commerce Factory, ROLE_OS, ROLE_KNOWLEDGE_OS, role-ecosystem, and
    ROLE MASTER all ranked, ROLE Commerce Factory winning deterministically
    (71.6 pts) on real evidence (Operational Intelligence priority 70,
    medium business value, launch-ready bonus, medium Impact Analysis
    risk) -- matching the brief's own worked example.
  - **Known limitations**: no scheduling engine or calendar integration
    (by design); estimated effort/duration are a static per-keyword
    lookup, not a per-project estimate; the 500ms performance target is
    not met on this real workspace (see Performance above); Today's Plan
    is always exactly one step, never a multi-item day plan.

- **Project Ecosystem Engine, Sprint C8** — ROLE OS now understands how
  adopted projects relate to each other, from deterministic evidence only
  (no LLM, no embeddings, no vector database). New package,
  `app/project_ecosystem/` (`models.py`, `detectors.py`,
  `relationships.py`, `graph.py`, `service.py`, `db.py`), and one new
  endpoint, `GET /project-ecosystem/{project_id}`.
  - **Canonical relationship model** (`models.py`): every relationship
    carries `relationship_id, source_project, target_project,
    relationship_type, confidence, evidence, detector, discovered_at,
    last_verified, manual_override, status`. `relationship_type` is always
    one of `SUPPORTED_TYPES`: `depends_on, uses, consumes, produces,
    extends, shares_assets, shares_prompts, shares_documentation,
    shares_knowledge, shares_sessions, blocks, blocked_by, related`.
  - **Detectors** (`detectors.py`), each a pure function over
    already-computed evidence, never re-scanning what another canonical
    domain owns:
    - `detect_dependencies` / `detect_capabilities` — PI's existing
      explicit dependency/capability tables (`app.projects.db`), reused
      verbatim (confidence 1.0). `blocks`/`blocked_by` are derived from a
      dependency edge whose target project's own status/health looks
      blocked -- not a separate detector.
    - `detect_shared_assets` — the canonical Assets index
      (`app.assets.service.list_all_assets`); two projects sharing a
      `duplicate_group_id` share an asset.
    - `detect_shared_knowledge` — Knowledge cards
      (`app.db.list_all_cards`), soft-matched to a project by the same
      case-insensitive `card['project']` name convention `ProjectContext`/
      Explorer already use; two projects referencing the same person/
      application/vendor tag share knowledge.
    - `detect_shared_documentation` / `detect_git_remote_references` —
      bounded (20KB, same cap as `discovery.next_action`) reads of each
      project's own README/ROADMAP/CHANGELOG/TODO/NEXT_ACTION and git
      remote URL, searched for another project's name as a literal text
      reference.
    - `detect_shared_prompts_and_sessions` — a project's latest Session
      Snapshot/AI Session mentioning another project by name.
    - `detect_sibling_projects` — two adopted projects under the same
      parent folder (`related`, low confidence).
  - **Conflict resolution & manual overrides** (`relationships.py`,
    `db.py`): same-pair-same-type relationships from different detectors
    merge (union of evidence, higher confidence kept). A new
    `role_os_ecosystem.db` (the "each domain owns its own database"
    convention) stores only manual dismiss/confirm overrides, keyed by the
    relationship's own deterministic id -- never the relationships
    themselves, which are always recomputed fresh.
  - **Impact Summary** (`graph.py`): `affected_projects, shared_assets,
    shared_documents, shared_prompts, shared_knowledge, shared_sessions,
    risk, confidence` -- bounded to direct (1-hop) relationships only, no
    multi-hop graph traversal, no destructive action ever taken.
  - **Consumers**: Explorer's Project Hub (`GET /explorer/project/{id}`)
    gained an `ecosystem` section (Dependencies/Consumers/Blocked By/
    Blocks/Shared Assets/Shared Prompts/Shared Knowledge/Shared
    Documentation/Impact Summary, rendered as clean cards, never a graph
    visualization) and a new relationship search (`_search_ecosystem`,
    result type `"Ecosystem Relationship"`) -- searching a project name
    surfaces "Used by ..." results, searching a relationship keyword (e.g.
    "shared assets") surfaces every relationship of that type. Mission
    Control's Operational Intelligence Engine gained a new rule,
    `rule_unblocks_dependents` ("Complete X to unblock Y, Z"), reading only
    the cheap dependency detector (plain SQL, never the full ecosystem's
    filesystem/knowledge scans). Project Memory gained a small, bounded
    `related_projects` section (top dependencies/consumers/recent shared
    decisions -- never a graph dump).
  - **Real bug found and fixed while building `detect_shared_assets`**:
    `app.assets.service.group_duplicates` only ever *cleared* a record's
    `duplicate_group_id`, never (re)set it -- `list_all_assets` calls it a
    second time on records that already went through it once (inside each
    project's own `index_project_assets` call), so a file whose only
    duplicate lived in a *different* project (correctly cleared to `None`
    within its own project's pass) could never be resolved back to a
    shared group id, contradicting `list_all_assets`'s own docstring
    guarantee. Fixed to positively (re)assign the group id in both
    branches; covered by a new regression test in `test_assets_os.py`.
  - **Performance**: every whole-workspace pass (`compute_relationships`,
    Explorer's `search()`/`project_hub()`, Resume Work, Cockpit's memory
    card) runs inside `app.assets.service.request_scope()` so the shared-
    assets detector's filesystem walk is never repeated within one
    request. Mission Control's OI rule reads only the cheap dependency
    detector, not the full ecosystem.
  - **Tests**: `dashboard/tests/test_project_ecosystem.py` (23 tests) --
    the canonical model, every detector, impact summary risk levels,
    manual overrides, the API, Project Hub/Explorer/Mission Control/
    Project Memory integration, the adopted-only security boundary, and a
    no-duplicate-asset-walk performance regression test.
  - **Known limitations**: import/package-reference scanning (parsing
    source code for cross-project imports) is out of scope -- too
    language-specific and too expensive to do safely at this sprint's
    scope; only filesystem/git/documentation/knowledge/PI-data evidence is
    detected. Shared-prompts/shared-sessions detection is a simple name-
    mention scan (low confidence), not a semantic match. See
    `docs/product/DECISIONS.md` for the full reasoning and C9 candidates.

- **Impact Analysis Engine, Sprint C9** — answers "if this project
  changes, what else is affected?" by reading the Project Ecosystem
  Engine's (C8) already-computed relationship graph, ProjectContext,
  Assets, Knowledge, Operational Intelligence (C6), and Project Memory
  (C7.1) -- no new relationship-detection pass, no new graph. New package,
  `app/impact_analysis/` (`models.py`, `scoring.py`, `service.py`, `api.py`
  inside the package itself), and one new endpoint,
  `GET /impact-analysis/{project_id}`.
  - **Canonical `ImpactReport`** (`models.py`): `project, generated_at,
    overall_risk, confidence, affected_projects, direct_dependencies,
    transitive_dependencies, shared_assets, shared_prompts,
    shared_documentation, shared_knowledge, shared_sessions,
    operational_effects, release_effects, recommended_actions, evidence,
    limitations`. `direct_dependencies`/`transitive_dependencies` name the
    projects *affected by* a change to this project (who depends on it),
    not what this project itself depends on.
  - **Risk scoring** (`scoring.py`): five explainable levels (`none, low,
    medium, high, critical`), each backed by a plain, documented
    count-based threshold (already-blocking dependents, direct/transitive
    dependent counts, shared-evidence counts) -- every level returns the
    exact reasons that produced it, never a bare label.
  - **Bounded transitive traversal** (`service.py`): a cycle-safe BFS over
    the Ecosystem Engine's `depends_on` edges (reversed), bounded to 3
    hops -- covers the brief's own worked example (ROLE OS -> ROLE
    Commerce Factory -> RoleValdez.com) with headroom, using a visited set
    keyed by project identity so no project is ever revisited or listed
    twice.
  - **Consumers**: Project Hub (`GET /explorer/project/{id}`) gained a new
    "Impact Analysis" section (Overall Risk, Affected Projects, Top
    Reasons, Recommended Actions -- concise cards, never a diagram).
    Mission Control's Operational Intelligence Engine gained a new rule,
    `rule_high_impact_change` ("Changing X today will affect N project(s)
    -- schedule accordingly"), reading only the cheap dependency-only
    relationships already in `bundle["ecosystem_dependencies"]` and doing
    its own bounded traversal (never calling the heavier Impact Analysis
    Engine). Project Memory gained a compact "Potential Impact" line
    (risk, affected count, up to 3 affected names). Explorer search gained
    a new result type, `"Impact"` -- searching a project name surfaces
    "Impact of changing X: <risk> risk".
  - **Two real bugs found and fixed while building this engine**:
    (1) `app/project_ecosystem/models.py`'s `BLOCKING_STATUSES` tuple
    incorrectly included `"critical"`, and `detectors.py`'s
    `detect_dependencies` treated a target project's computed *health
    tier* of `"critical"` the same as an explicit `blocked`/`at_risk`
    *status* -- since a fresh/thin project defaults to `health_score=0`
    (tier `"critical"`), nearly every brand-new project was falsely
    flagged as "blocking" its dependents. Fixed to check only the
    explicit `status` field; re-verified against the brief's own worked
    example and re-ran the full `test_project_ecosystem.py` suite (23
    tests, unaffected). (2) `build_project_memory()` was calling
    `get_operational_intelligence()` (a whole-workspace Epic 2 Advisor
    refresh) twice per invocation -- once for the Operational
    Recommendation field, again inside the new `potential_impact`
    computation. Fixed by computing it at most once per call and
    threading the same result into both.
  - **Performance**: reuses the Project Ecosystem graph and
    `request_scope()`-cached asset/knowledge data; every consumer
    (Project Hub, Project Memory, Explorer) that already computed
    `all_contexts`/`relationships`/`operational_intelligence_recs` in the
    same request passes them straight through -- no repeated filesystem
    scan, no repeated relationship detection, no repeated Operational
    Intelligence pass.
  - **Tests**: `dashboard/tests/test_impact_analysis.py` (27 tests) --
    every risk level with its reasons, transitive traversal against the
    brief's own example, cycle safety, bounded depth, shared-evidence
    detection, the API (including 404), Project Hub/Mission
    Control/Explorer/Project Memory integration, the adopted-only
    security boundary, and no-duplicate-scan performance regressions.
  - **Real workspace verification**: live-verified against
    `C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS` --
    ROLE_OS, ROLE Commerce Factory, ROLE_KNOWLEDGE_OS, ROLE MASTER, and
    role-ecosystem each returned an honest, evidence-backed `medium`-risk
    report (shared documentation only; no PI dependency edges declared
    yet in this workspace, so no direct/transitive dependents were
    fabricated).
  - **Known limitations**: transitive traversal follows only explicit
    `depends_on` relationships (Sprint C8) -- an undeclared dependency
    with no PI edge is not traversed. Shared-evidence detection inherits
    the Project Ecosystem Engine's own limitations (no import/package-
    reference parsing; name-mention detectors are literal substring
    matches). Operational/release effects are read from each affected
    project's existing Operational Intelligence recommendation and
    business_value/health, never independently assessed.

### Fixed

- **Resume Work Refactor, Sprint C7.1** — real-world validation exposed a
  product flaw: Resume Work resumed an *AI Session*, not a Project. If the
  session/snapshot were thin or generic, the copied prompt was too, and
  the assistant had to ask what the project even was. Corrected flow:
  `Project -> Project Memory -> Resume Prompt -> locate best AI Session ->
  open conversation -> copy prompt`. The AI Session is now only ever the
  transport (where the conversation happens to live); Project Memory
  (`app/project_memory/`) is the one source of truth for the prompt.
  - **Project Memory** (`app/project_memory/service.py`) composes the same
    already-computed `ProjectContext` (next action, git, latest snapshot)
    plus, for a real Resume Work click, the Sprint C6 Operational
    Intelligence Engine's top recommendation for that project.
  - **Resume Prompt** (`app/project_memory/prompt.py`) now always begins
    with exactly `Project:`, `Current Objective:`, `Where We Left Off:`,
    `Pending Work:`, `Next Action:`, `Operational Recommendation:`,
    `Conversation:`, in that order — the AI Session's own title/snapshot
    never drives any section except `Conversation:` (which conversation to
    continue in, and why).
  - **Conversation selection** (`app/project_memory/session_selection.py`):
    prefers 1) latest active session, 2) pinned (`favorite`), 3) preferred
    (`current`), 4) newest — every choice comes with a plain-English
    reason (`session_selection_reason`), never a silent decision.
  - **Session naming** (`app/project_memory/naming.py`): every session
    Resume Work creates (or retitles, if it inherited a generic name from
    the old flow) is named `<Project Name> — <Objective>` — never "Resume
    Work", "Untitled", or "Session 1". An existing session literally
    titled "Resume Work" (the old bug) is retitled the moment it's next
    resumed, not left mis-named forever.
  - **Cockpit**: Project Memory is now the primary card (`GET /pi/
    projects/{id}/memory`); AI Sessions is a secondary section below it.
  - **Mission Control**: Resume Work (unchanged endpoint,
    `POST /workspace/discovered/{id}/resume-work`) now builds its prompt
    from Project Memory automatically — no frontend changes needed.
  - **Recursion fix**: `ProjectContext`'s `resume_state` (built via
    `preview_resume_state`) now itself builds Project Memory to produce an
    accurate preview prompt — which would recurse forever against
    `build_project_context` if left unguarded. Fixed with two new,
    default-`True` (zero-behavior-change-for-everyone-else) cost knobs on
    `build_project_context`: `include_resume_state` and
    `include_epic2_recs`; `app.project_memory` is the one caller that
    passes `False` for both, since Project Memory needs neither
    `resume_state` (that would recurse) nor the embedded Epic 2
    `advisor_summary` (Project Memory never reads it, and calling it would
    duplicate the one Epic 2 refresh Operational Intelligence already
    triggers).
  - **Performance**: the real Resume Work click intentionally pays for one
    whole-workspace Operational Intelligence pass (required to populate
    `Operational Recommendation:`, matching the already-accepted cost of
    `/advisor/recommendations`); every other, more frequent caller
    (`preview_resume_state`, the per-session `/resume` endpoint, Cockpit's
    memory card) skips it (`include_operational_recommendation=False`) and
    stays cheap.
  - **Removed**: the old session-only `app.services.resume.
    build_resume_prompt` (and its now-obsolete test file,
    `test_resume_service.py`) — the AI Session never owns the prompt
    anymore, so no code path should be able to build one from session data
    alone. `app.services.resume` now only resolves *where* to open a
    conversation (`resolve_conversation_url`), never *what* to say.
  - **Tests**: `dashboard/tests/test_project_memory.py` (27 tests: naming,
    session selection tiers, prompt section order/labels, honest empty
    states, no-external-API guard) plus updates to
    `test_workspace_resume.py` (including the self-heal-old-title
    regression), `test_ai_sessions_api.py`, and `test_cockpit_redesign_ui.py`.
  - **Live-verified** against the real `ROLE Commerce Factory` project: a
    fresh Resume Work click produces a complete, project-grounded prompt
    with a real Operational Recommendation, and correctly explains which
    conversation was selected and why.

- **Operational Intelligence Engine, Sprint C6** — one canonical service,
  `app.operational_intelligence.get_operational_intelligence()`
  (`app/operational_intelligence/`), that turns evidence about a project
  (or the workspace as a whole) into a recommendation. Every recommendation
  carries exactly the seven fields the brief requires — `recommendation`,
  `priority`, `confidence`, `evidence`, `project`, `expected_benefit`,
  `suggested_action` — plus `reason`/`action_link`/`source`/`rule_id` for
  backward compatibility and readability. No LLM, no embeddings, no vector
  database, no external AI API — every recommendation is deterministic.
  - **No new recommendation engine — one canonical composition over the
    two that already existed**: the *discovery* rule pack
    (`workspace.advisor.generate_recommendations`, git/health/docs/tests/
    next-action/commercial-readiness evidence) and the *PI* rule pack
    (`app.advisor.engine.get_recommendations`, dependencies/capabilities/
    TODOs/deliverables/decisions evidence, reused as-is so Advisor's own
    persisted dismiss/complete/TTL lifecycle stays intact) are both run
    through this one engine and normalized into one shape. Three genuinely
    new, previously-uncovered evidence dimensions were added
    (`app/operational_intelligence/rules.py`): Knowledge freshness (new —
    no prior computation existed), Discovery scan freshness (already
    computed, never turned into an actionable recommendation before), and
    workspace status crossed with pending work (a paused/archived project
    that still has open next-action/pending-snapshot work).
  - **Conflict resolution**: recommendations are deduplicated by
    `(project, recommendation title)` — an identical title firing for the
    same project (or workspace-wide) from two different rule packs
    collapses to whichever has the higher priority, then confidence.
    Different recommendations for the same project are never collapsed.
  - **Priority calculation**: no new scoring formula — every rule pack
    already returns a documented 0-100 priority; the engine only sorts by
    it, never recomputes or renormalizes.
  - **`expected_benefit`**: a static, documented keyword → benefit-sentence
    lookup (`models.py`'s `_EXPECTED_BENEFIT_BY_KEYWORD`) — never inferred
    or generated, auditable in one place.
  - **Consumers**: Mission Control's Today's Focus/Needs Attention/Value
    Signal/Daily-Session-suggestion-text all now read this one engine
    instead of calling the discovery pack directly. Advisor gained an
    additive `GET /advisor/operational-intelligence` endpoint (the existing
    `GET /advisor/recommendations` and its dismiss/complete lifecycle are
    unchanged). Explorer's Recommendation search results now include an
    `evidence` field.
  - **Performance**: one call each to `all_project_contexts`,
    `workspace.advisor.generate_recommendations`, `app.advisor.engine.
    get_recommendations` (unfiltered, once — not once per project), and
    the two new freshness checks. Mission Control passes its already-
    computed `all_contexts`/`enriched_items` straight through so the engine
    never recomputes "every tracked project" a second time in the same
    request. On the real `1 - IA PROJECTS` workspace, `GET /advisor/
    operational-intelligence` responds in ~0.4s (14 recommendations).
  - **Tests**: `dashboard/tests/test_operational_intelligence.py` — the
    seven-field canonical shape, sort order, discovery-pack evidence, the
    PI pack's dependency rule (reused, not reimplemented), the new paused-
    with-pending-work rule, the dedup/conflict-resolution mechanism, the
    new Advisor endpoint, Explorer's evidence field, and Mission Control's
    consumption of the engine.
  - **Known limitation**: Resume Work's own prompt-building mechanics are
    unchanged (it doesn't need its own scoring); its integration point with
    Operational Intelligence is at the recommendation-context level — the
    Mission Control card that triggers Resume Work now explains *why*, via
    this engine, rather than Resume Work computing anything itself.
    Dashboard was not changed this sprint (optional per the brief, "may
    summarize"); it still reads the discovery pack directly via
    `ProjectContext.advisor_summary`, unchanged from Sprint C5.

- **Mission Control, Sprint C5** — the daily operating surface of ROLE OS.
  One new endpoint, `GET /mission-control` (`app/mission_control/
  service.py`), composes Primary Focus (the one dominant "continue this
  project" recommendation, with reasons), Today's Focus (up to 3 actionable
  items), Since Last Time (changes since your last Daily Session, or a
  labeled 24h fallback), Needs Attention (unresolved issues, most severe
  first), a Value Signal ("Closest to Launch," only when a project actually
  qualifies), a compact Portfolio strip, deduplicated Recent Activity,
  Daily Session state, Snapshot Continuity, and Quick Actions — all from
  one already-shaped payload, so the frontend performs no joining, ranking,
  or deduplication of its own.
  - **No new ranking/recommendation engine**: every section reuses an
    existing service exactly once — `ProjectContext`'s `all_project_
    contexts`, Home's `get_home_portfolio`/`suggested_project_to_continue`,
    and `workspace.advisor.generate_recommendations` (the same rule set
    Dashboard already calls). See `docs/product/DECISIONS.md` for the
    full reasoning.
  - **Home becomes Mission Control**: the sidebar's first nav item and the
    default route now render Mission Control (`renderMissionControlPage` in
    `static/js/app.js`); Dashboard is unchanged and remains the deeper
    executive analytics view.
  - **Performance fix (addresses the Sprint C4.1 finding)**: `GET /dashboard/
    summary` and `GET /mission-control` used to walk every adopted
    project's filesystem for assets up to 3-4 times per request
    (`ProjectContext.assets_count`, Home's recent-assets list, the activity
    feed). A new request-scoped cache, `app.assets.service.request_scope()`
    (`contextvars`-backed, keyed by resolved root path), collapses this to
    exactly one walk per adopted project per request. On the real
    `1 - IA PROJECTS` workspace (6 tracked projects), `GET /mission-control`
    responds in ~70-300ms.
  - **Tests**: `dashboard/tests/test_mission_control_api.py` — canonical
    ProjectContext reuse, primary recommendation + reasons, needs-attention
    severity sort, since-last-time baseline (real session + labeled
    fallback) and noise-event exclusion, daily-session present/absent
    states, snapshot continuity, portfolio dedup, and a regression test
    proving the double/triple asset-walk fix.
  - **Known limitation**: "Since Last Time" can only surface event types
    the existing Recent Activity feed already tracks (commits, filesystem
    changes, adoption, AI sessions/snapshots, discovered assets) — it
    cannot yet report project status changes, new blockers, or roadmap/TODO
    edits as discrete events; candidate for a future sprint.

- **Assets Canonicalization Audit, Sprint C4.1** — verifies and enforces
  that Assets/Explorer/Project Detail/Project Hub/Home/Dashboard/Advisor/
  ProjectContext all consume the same canonical `AssetRecord`/`app.assets`
  service, with no second implementation anywhere. An audit sprint, not a
  feature sprint: no new user-facing functionality, no UI redesign, no new
  database.
  - **Full caller audit**: every asset-related symbol (`AssetRecord`,
    `assets_count`, `duplicate_hash`/`duplicate_group_id`, `likely_logo`,
    classification, MIME/dimension reading, preview/thumbnail generation,
    open-file/open-folder/copy-path) traced across the entire backend and
    `app.js`. Result: every consumer either calls into `app.assets.*`
    (directly or via `app.workspace.assets_index`'s thin re-export shim)
    or performs only `sum`/`len`/`sort`/`filter` aggregation over
    already-canonical fields — zero independent classification, hashing,
    MIME-detection, or duplicate-grouping logic found anywhere else.
  - **Real bug found and fixed**: `index_project_assets` (the function
    Dashboard's recent assets, Home's recent assets, `ProjectContext.
    assets_count`'s recent-activity block, and Project Hub all call
    *directly*) never resolved `duplicate_group_id` to `None` for a file
    that doesn't actually share its hash with anything else — only
    `list_all_assets` (the function the `/assets` API uses) applied that
    correction. Every one of those direct callers was showing a
    `duplicate_group_id` for genuinely unique files, disagreeing with
    `/assets`/`GET /assets/duplicates/{id}`, which correctly treated the
    same file as not a duplicate. Fixed by applying `group_duplicates`
    inside `index_project_assets` itself, so every caller — not just the
    `/assets` API — sees the same resolved value.
  - **Live count-parity verification**: for the real `ROLE_KNOWLEDGE_OS`
    project, the Assets API, `ProjectContext.assets_count`, and Project
    Hub's `assets_summary.count` all independently agree (9 = 9 = 9), and
    the real asset `shot_4_logo.png` carries an identical `asset_id`,
    `category`, `reusable`, `likely_logo`, `preview_available`,
    `duplicate_group_id`, and `canonical_project_id` across the Assets
    API, Project Hub, Dashboard's recent assets, and Home's recent assets.
  - **Graph Asset node type is a documented, separate concept**: Epic 3's
    Knowledge Graph (`"Asset"` node) and Sprint 5's Conversation Graph
    (`"asset"` node) both predate Sprint C4 and represent knowledge-
    extraction/manually-entered "asset mentions" from imported
    conversations or PI Project records — no filesystem access, no
    category/dimensions/hash, no shared id or endpoint with `app.assets`.
    Confirmed as an intentional, pre-existing naming overlap, not a
    duplicate implementation of the filesystem `AssetRecord` concept —
    documented explicitly so a future engineer doesn't conflate
    `/graph?node_type=Asset` with `/assets`.
  - **Classification architecture**: `app/assets/classification.py` (163
    lines, a single fixed-priority rule tuple) reviewed for growth risk
    and left as-is — no duplication or structural risk found; a
    `assets/rules/` registry split would be premature for its current
    size.
  - **Duplicate detection boundary**: confirmed duplicate detection
    belongs inside `app.assets` for now (partial-content hash only,
    grouped, never auto-consolidated); documented extension points for a
    future sprint (full-file hashes, perceptual/near-duplicate image
    hashing, same-design-different-resolution detection) without
    implementing any of them now.
  - **Performance audit**: per-file metadata (dimensions, duplicate hash)
    is genuinely cached and never recomputed for an unchanged file
    (path+mtime+size-keyed). One real, measured inefficiency found and
    documented (not fixed, to stay within this audit's no-redesign scope):
    `GET /dashboard/summary` walks every adopted project's filesystem
    twice per request — once via `ProjectContext.assets_count` (per-
    project, for the count) and again via `workspace.service.
    list_project_assets` (for the actual recent/reusable asset records) —
    measured at ~500ms vs. `/assets`'s own ~280ms for the same real
    workspace. Recommended as a concrete C5 follow-up: thread the already-
    computed asset list through `ProjectContext` instead of re-walking for
    the count.
  - **9 new architectural guard tests**
    (`test_assets_canonical_architecture.py`) that inspect the source tree
    itself (via `ast`) rather than behavior, so a future change
    reintroducing a second classifier, a second duplicate grouper, a
    legacy shim growing real logic again, a second override-writing
    router, or client-side classification in `app.js` fails immediately
    instead of drifting until the next manual audit. Plus one new
    regression test (`test_index_project_assets_resolves_duplicate_group_
    id_directly`) locking in the bug fix above. Full suite: 1021 passed,
    0 failed (up from 1011 before this sprint's 10 new tests).
  - **No changes** to the Assets UI, no new endpoints, no new database, no
    LLM calls, no modification to any scanned project file.

- **Discovery Engine, Sprint 1** (`dashboard/app/discovery/`) — a strictly
  read-only, CLI-only audit of an arbitrary folder tree (configurable
  `--root`, never hardcoded), implementing Phase 1/Sprint 1 of
  `docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md`. Never moves, renames,
  edits, deletes, or creates a file under the scanned root, initializes
  git, or writes to a database — the only writes it can perform are the
  optional `discovery_audit.json`/`.md` report files under a caller-chosen
  `--output` directory, refused if that directory would resolve inside
  `--root`.
  - **Scanner** (`scanner.py`): depth-limited candidate discovery that
    skips VCS/dependency/build directories, never follows symlinks or
    Windows junctions (recorded, not descended into — cycle-safe), and
    looks one level deeper inside "container" folders that have no
    project markers of their own (monorepo-style `packages/*`).
  - **Detectors** (`detectors.py`): one read-only pass per folder producing
    languages (extension histogram), tech markers, README/ROADMAP/
    CHANGELOG/TODO/LICENSE presence, test file/folder detection, Docker/
    Docker Compose/GitHub Actions presence, image/video/SQLite/`.env`/
    launcher (`.bat`/`.ps1`) file inventories, image/document/design-file/
    font counts, Obsidian vault (`.obsidian`) and VS Code
    (`*.code-workspace`) detection, and a budgeted absolute-path-reference
    scan (Windows and POSIX patterns) over text/config files.
  - **Git Reader** (`git_reader.py`): branch, remote, last commit hash/
    date/message, commit count, and dirty-worktree state via local
    read-only `git` subcommands only (no fetch/pull/push/clone).
  - **Classifier** (`classifier.py`): explainable, non-ML weighted scoring
    — confidence, kind (`Software Project`/`Website`/`Mixed Project`/
    `Documentation Project`/`Brand / Asset Project`/`Unknown`/
    `Non-project`), **move-risk** (`low`/`medium`/`high`, reasoning over
    hardcoded absolute paths, `.env` files, launcher scripts, a
    local-filesystem git remote, an Obsidian vault, or a VS Code workspace
    file with absolute paths), maturity (`prototype`/`active`/`mature`/
    `stale`), and commercial readiness (`not-commercial`/`early`/
    `client-ready`/`production`) — every score paired with the specific
    reasons behind it.
  - **Health Score** (`health.py`): a 0-100 weighted score over eight
    independently-inspectable signals (documentation, tests, recent
    activity, roadmap, architecture, automation, commercial readiness,
    deployment), renormalized over whichever signals are available —
    mirrors the shape of `dashboard/app/projects/health/`'s existing
    Health Score engine (Epic 1) but scores filesystem evidence instead of
    a DB-backed project dict.
  - **Recommendation** (`recommendation.py`): one of six actions per
    folder (`Leave where it is`, `Move into IA PROJECTS`, `Archive`,
    `Merge with another project`, `Rename`, `Requires manual review`),
    each with the specific reasons behind it. A corpus-level pass
    (`apply_container_child_overrides`) flags a container folder whose
    *only* nested project shares its name (e.g. a folder wrapping a single
    same-named subfolder) as `Rename`, without touching the nested
    project's own recommendation.
  - **Reporters** (`reporters.py`): JSON, Markdown, and console-table
    renderers — the Markdown report's Summary section reports folders
    scanned, projects detected, git repositories, static websites, Python/
    Node projects, unknown folders, and safe-to-move/needs-review/
    high-risk counts; the Projects table is `| Project | Type | Git |
    Health | Move Risk | Recommendation |`; a Recommendations section
    lists every folder's action and reasoning; high-risk findings and
    skipped/inaccessible paths get their own sections.
  - **CLI** (`__main__.py`): `python -m app.discovery audit --root <path>
    [--output <dir>] [--max-depth N] [--basename NAME] [--quiet]`.
  - 38 new tests (`dashboard/tests/test_discovery.py`,
    `test_discovery_health_and_recommendation.py`) covering nested
    projects, git repos and non-git folders, paths with spaces/
    parentheses, absolute-path detection (Windows/POSIX), asset/document/
    design-file/font counting, LICENSE/Obsidian-vault/VS-Code-workspace
    detection, every classification/move-risk/maturity/commercial-
    readiness/health-score/recommendation branch, the container/child
    rename override, that the audit never modifies the scanned tree
    (byte-for-byte snapshot before/after), that reports only ever land
    outside `--root`, invalid/non-directory roots, permission-denied
    folders (recorded, not fatal), and symlink/junction cycles (verified
    to terminate and to never descend into the link). No database, no
    API route, and no external AI/LLM call anywhere in this module — see
    `docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md` for what Sprints 2-4
    would add on top of this (classifier-confirmed writes into Project
    Intelligence, health/advisor wiring, Mission Control ranking). Full
    suite: 651 passed, 0 failed.

- **Workspace Adoption, Sprint 2** (`dashboard/app/workspace/`) — the first
  writable layer on top of the read-only Discovery Engine (Sprint 1),
  implementing Phase 2/3 of `08_IMPORT_ENGINE_PROPOSAL.md`'s rollout plan,
  scoped down to exactly what was asked: adopt/ignore/review, no automatic
  project-table writes, no Advisor/Graph/Health/Mission Control changes.
  - **Own SQLite file** (`role_os_workspace.db`, `Settings.workspace_db_path`,
    default `var/role_os_dashboard/role_os_workspace.db`) with two tables:
    `workspace_scan_cache` (one cached copy of the last scan, so the page
    doesn't re-scan the filesystem on every request) and `adopted_projects`
    (per-folder overlay: `adopted`/`ignored` flags, `priority`,
    `business_value`, `status`, `tags`, `notes` — nothing else). No
    migration needed: both are brand-new tables in a brand-new file, same
    as every other domain's first release (advisor/imports/extraction).
  - **No metadata duplication**: name, git status, health score,
    confidence, move risk, classification, languages, etc. are never
    copied into a row — every read merges the cached scan (live discovery
    data) with the overlay by a stable id (`sha1(root_path)[:16]`), so the
    filesystem stays the single source of truth for everything except the
    six user-editable fields above.
  - **Service** (`service.py`): `rescan()` calls the real, unmodified
    `app.discovery.service.run_audit` (no mocking, no fixtures) and caches
    the result; `list_workspace_items()`/`get_item()` merge cache +
    overlay; `adopt_item()`/`ignore_item()`/`unignore_item()`/
    `update_item()`/`add_note()` mutate only the overlay row;
    `list_adopted_as_projects()` reshapes adopted items into the same
    field names `/pi/projects` already returns.
  - **API** (`/workspace/*`): `GET /summary`, `GET /discovered`
    (`?include_ignored=`), `GET /discovered/{id}`, `POST /rescan`
    (optional `root`/`max_depth` body, 400 on an invalid root), `POST
    /discovered/{id}/adopt|ignore|unignore`, `PATCH /discovered/{id}`,
    `POST /discovered/{id}/notes`, and `GET /adopted` (the Projects-page
    feed). New `ROLE_OS_DISCOVERY_ROOT` setting, defaulting to this
    checkout's own parent directory (the real, validated Sprint 1 root) —
    never a hardcoded literal path — and always overridable per-call.
  - **UI**: a new sidebar page ("Workspace" — nav item, hash route
    `#/workspace`) listing every discovered folder with Name/Folder/Type/
    Git/Health/Confidence/Move Risk, Adopt/Ignore/Review buttons (Review
    opens the existing detail overlay with the full discovery signal set
    and reasons), a "Rescan Workspace" button, and the four required
    summary stats (Last Scan/Projects Found/Projects Adopted/Ignored
    Projects). The existing Projects page now additionally fetches
    `/workspace/adopted` and renders adopted projects alongside manually-
    created ones (labeled "Discovered"), with the first-run onboarding
    check updated to require both lists empty — all additive; `/pi/*`, the
    manual Project CRUD, and its UI are untouched.
  - 43 new tests (`test_workspace_db.py`, `test_workspace_service.py`,
    `test_workspace_api.py`, `test_workspace_ui.py`) covering overlay CRUD,
    adopt/ignore/unignore idempotency and interaction, overlay survival
    across a rescan, real (unmocked) Discovery Engine runs against
    synthetic folder trees, 404s on unknown ids, invalid-root handling,
    read-only-w.r.t.-scanned-tree verification, and that `/pi/projects`
    keeps working unmodified. Also manually verified end-to-end against
    the real `1 - IA PROJECTS` folder (17 projects found, `ROLE_OS` itself
    adopted with health score 79). Full suite: 694 passed, 0 failed.

- **Project Boundary, Sprint 3** (`dashboard/app/discovery/boundary/`) —
  fixes the Workspace page presenting every discovered folder as a flat
  peer row (internal structure folders, nested repositories/components,
  and folders that should have been excluded all showing up next to real
  top-level projects). Reuses the Discovery Engine and Workspace Adoption
  unchanged; no rewrite of the project domain.
  - **Hierarchy model**: every `DiscoveredProject` gains `item_id`,
    `item_kind` (`project`/`repository`/`component`/`documentation`/
    `asset_library`/`internal_folder`/`excluded`/`non_project`/`unknown`),
    `parent_item_id`, `project_root_id`, `hierarchy_depth`, boolean flags,
    `exclusion_reason`, `boundary_confidence`, `boundary_evidence` --
    deliberately a separate field from `classification` (see
    `docs/product/DECISIONS.md`).
  - **Boundary rules** (`boundary/rules.py`, `boundary/hierarchy.py`): a
    depth-1 folder is a top-level project if it has its own `.git`/tech
    marker (checked at its own root only, not the deep-walked
    `tech_markers` list, to avoid a container inheriting evidence from its
    own nested children -- a real bug caught and fixed during this
    sprint), **or** contains a nested folder that does (the `ROLE Commerce
    Factory` → `RCOM-*-Adapter` case, solved generically, no name-specific
    logic), **or** has a README plus substantial internal structure (3+
    internal folders, or a roadmap/changelog -- the `ROLE MASTER` case). A
    nested repository/component is promoted to independent top-level
    status instead only with strong evidence of its own (own remote,
    roadmap/changelog, high confidence). A whole-scan corpus pass, run
    once after classification (same shape as the existing
    `recommendation/container_override.py` pass).
  - **Exclusions** (`boundary/exclusions.py` + one source-of-truth
    `boundary/exclusions_config.json`): exact names, case-insensitive
    names, glob patterns, relative-path patterns. Defaults include common
    technical folders and `OTROS - no proyectos`. An excluded folder is
    reported (with its reason) but never walked recursively -- no
    filesystem access beyond the name the scanner's own directory listing
    already had. Extra exclusions via `ROLE_OS_DISCOVERY_EXTRA_EXCLUSIONS`
    (comma-separated names/globs, never an absolute path) or CLI
    `--exclude` (repeatable).
  - **Workspace Adoption integration** (`app/workspace/`): additive-only.
    `GET /workspace/discovered` is unchanged when `view` is omitted
    (Sprint 2 contract preserved); `?view=top_level|repositories|excluded|
    needs_review|all` returns the new grouped hierarchy, with children
    embedded inline (no extra request to expand) and repository/component/
    documentation/asset-library/internal-folder counts per top-level
    project. Two new nullable columns on `adopted_projects`
    (`override_action`, `override_parent_id`, added via idempotent `ALTER
    TABLE`) back a new `/discovered/{id}/override` (`top_level` |
    `attach_to_parent`) / `.../override/clear` pair -- a user correction
    stored only in the overlay, never altering the Discovery Engine's own
    computed `item_kind`/`parent_item_id` (both stay visible side by side
    for comparison). Rescan preserves every adopted/ignored/override state
    by id; a renamed folder gets a new id (old overlay orphaned, not
    deleted); a removed folder simply disappears, with the summary counts
    never inflated by it.
  - **UI**: the Workspace page's single flat table is now four filter tabs
    (Top-level projects / Nested repositories / Ignored & excluded / Needs
    review), each top-level row shows child-kind counts with an Expand
    action revealing indented child rows, and the Review detail panel
    shows the full boundary evidence plus override actions. Discovered a
    real, unrelated latent bug while wiring this: content rendered inside
    `#view-root` with a `[data-nav]` attribute (e.g. a card linking to
    another page) was never clickable, because that delegation only
    existed for the sidebar's own fixed elements -- not applicable here
    since this sprint didn't add such a link, but flagged for awareness.
  - CLI (`__main__.py`): new repeatable `--exclude`. Reports
    (`reporters.py`) gained a "Project Hierarchy" section (top-level/
    nested/internal/excluded/needs-review breakdowns with evidence) and a
    false-positive-reduction comparison against the old flat view.
  - 53 new tests (`test_discovery_boundary.py`, `test_workspace_hierarchy.py`,
    `test_workspace_hierarchy_api.py`, `test_workspace_hierarchy_ui.py`)
    covering top-level detection, nested git repos, monorepo-like
    structures, numbered internal folders (with the own-markers exception),
    the nested-independent-project exception, exact/case-insensitive/glob/
    user exclusions, recursive-exclusion prevention, deterministic ids,
    real paths with spaces and parentheses, the read-only guarantee,
    grouped/filtered views, overrides (set/clear/dangling-parent fallback),
    rescan persistence, and renamed/removed-folder behavior. Also manually
    verified end-to-end against the real `1 - IA PROJECTS` folder: 17 flat
    rows collapse to 4 top-level projects (`ROLE_OS`, `ROLE Commerce
    Factory`, `ROLE MASTER`, `role-ecosystem`), `RCOM-Printful-Adapter`/
    `RCOM-Shopify-Adapter` nest under `ROLE Commerce Factory`, `ROLE
    MASTER`'s 8 numbered folders nest as internal folders, `OTROS - no
    proyectos` is excluded, and the override flow was exercised live on a
    real ambiguous folder (`ROLE_KNOWLEDGE_OS`, promoted to top-level via
    "treat as top-level project"). Full suite: 771 passed, 0 failed.

- **Project Intelligence Wiring, Sprint 4** — wires the discovered/adopted
  project data from Sprints 1-3 into Projects, Home, Advisor, and Assets,
  which previously showed empty/zero-centric content whenever no
  manually-created Project Intelligence data existed. Reuses the Discovery
  Engine and Workspace Adoption unchanged; no rewrite of the project
  domain, no Mission Control yet, no browser automation, no scanned
  project files ever modified.
  - **Next Action extractor** (`app/discovery/next_action.py`): a
    deterministic, non-LLM search over real project files, in priority
    order -- AI Session Snapshot hint (passed in, no DB access from this
    module) → `NEXT_ACTION.md` → `TODO.md`/a `## TODO` section → `ROADMAP.md`'s
    current milestone → README's "Next Steps" section → `CHANGELOG.md`'s
    unreleased section → the latest git commit message. Every result
    carries its source, source path, confidence, and extraction
    timestamp; finding nothing returns `text: None` ("Not yet defined"),
    never an invented value.
  - **Recent commits** (`git_reader.py`): one extra read-only `git log -5`
    per repo, feeding the unified activity feed and Home page with real
    commit history (previously only the single latest commit was read).
  - **Asset discovery index** (`app/workspace/assets_index.py`): walks
    each adopted project's real files (PNG/JPG/JPEG/WEBP/SVG/PDF/MP4/MOV/
    PSD/AI/fonts), producing filename/project/path/type/size/modified/
    category/reusable/duplicate-hash records -- no thumbnails, no copying,
    the filesystem stays the source of truth. Logos/fonts/design files are
    marked reusable by default; a partial (first-1MB) SHA-1 hash gives a
    practical duplicate-detection signal without hashing huge video files
    in full.
  - **Workspace Advisor 2.0** (`app/workspace/advisor.py`): 11 rule-based,
    evidence-only recommendations over real discovered-project signals
    (inactive-for-N-days, dirty git tree, no README, no roadmap/changelog,
    no tests, next-action-available, high-business-value-but-inactive,
    high move risk, momentum/continue, assets-without-commercial-output,
    near-completion) -- a sibling to Epic 2's `app/advisor/` (which has no
    filesystem/git knowledge at all), not a rewrite of it. Every
    recommendation carries project/reason/evidence/priority/confidence/
    action_link; a rule never fires without real supporting data.
  - **Unified Recent Activity** (`app/workspace/activity.py`): merges git
    commits, filesystem mtimes, adoption events, AI Sessions/Snapshots,
    and discovered assets into one deduplicated, time-sorted feed.
  - **Home portfolio** (`app/workspace/portfolio.py`): Last Active
    Project, Most Recently Modified, Projects Needing Attention, Recent
    Commits, Recent Assets, Latest AI Session, a Suggested Project to
    Continue (explainable scoring: has a next action + recent activity +
    business value), and a Quick Resume action.
  - **API** (all additive under `/workspace/*`): `GET /home`, `GET
    /advisor`, `GET /assets[?project_id=]`, `GET /activity[?limit=]`;
    `GET /discovered?view=top_level` is now enriched (next_action/
    documentation_status/test_status/asset_count) and `GET /discovered/{id}`
    now includes `next_action`/`ai_sessions` -- both purely additive,
    `WorkspaceItem`'s `extra="allow"` means no existing consumer breaks.
    `GET /summary` gained `is_stale`/`hours_since_scan`/
    `stale_threshold_hours` (§8 Data Freshness; stale after 24h).
  - **UI**: Projects page cards now show git branch/dirty state/last
    commit/last modified/documentation status/test status/asset count/
    nested repository-component counts/next action/adoption status,
    linking to a **new Discovered Project Detail view** (`#/dproject/{id}`,
    parallel to and never touching the existing manual-project detail
    view) with Overview/Git/Documentation/Repositories-Components/Assets/
    Tests/Recent Activity/AI Sessions/Latest Snapshot/Next Action/Risks-
    Blockers sections, each showing "Not yet defined" rather than a
    fabricated value when data doesn't exist. Home gained a "Your
    Projects" portfolio section above the existing Today's Focus (which is
    untouched). Advisor gained a "Discovered Projects" section alongside
    Epic 2's existing recommendations. Assets was rebuilt from an inert
    placeholder (riding on `/graph?node_type=Asset`, wired to nothing
    real) into a real table over `/workspace/assets`. The Workspace
    page's summary cards now show a stale-data warning badge.
  - Scoping decision: Home/Advisor/Assets/Activity all operate over
    *adopted* top-level projects only (not merely discovered-but-
    unadopted ones) -- adoption is the existing, explicit "yes, track
    this" signal from Sprint 2, and excluded/internal-folder items can
    never reach any of these views by construction (they all build on
    `list_enriched_top_level_projects`, itself built on Sprint 3's
    top-level-only hierarchy view).
  - 67 new tests (`test_discovery_next_action.py`,
    `test_workspace_assets_index.py`, `test_workspace_advisor.py`,
    `test_workspace_activity.py`, `test_workspace_portfolio.py`,
    `test_workspace_sprint4_api.py`, `test_workspace_sprint4_ui.py`)
    covering next-action priority order, asset indexing (extensions,
    categories, reusable flag, duplicate hashing, technical-directory
    exclusion), every advisor rule firing only with real evidence, activity
    dedup/sorting, home aggregation, the full API surface, excluded-folder
    non-leakage into Home/Advisor/Assets/Activity, the stale-data warning,
    real paths with spaces and parentheses, and that no scanned file is
    ever modified. Also manually verified end-to-end in a live browser
    against the real `1 - IA PROJECTS` folder: adopted `ROLE_OS`, `ROLE
    Commerce Factory`, `ROLE MASTER`, `role-ecosystem`, and
    `ROLE_KNOWLEDGE_OS`; Projects/Home/Advisor/Assets all populated with
    real git history, real next actions (`ROLE MASTER`: "Confirm
    TYPOGRAPHY.md font choices and licensing" from a TODO section;
    `ROLE_OS`: its actual latest commit message as the fallback), real
    evidence-based recommendations (dirty tree, high move risk with a real
    absolute-path count, momentum, near-completion), and real asset files
    (9 real images from `ROLE_KNOWLEDGE_OS`, correctly categorizing
    `shot_4_logo.png` as a reusable logo). Full suite: 845 passed, 0
    failed.

- **Project Unification, Sprint 5** — removes the conceptual split between
  manually-created Projects (Project Intelligence, Epic 1) and
  discovered/adopted projects (Discovery Engine + Workspace Adoption). From
  now on there is exactly one concept, "Project," bridged by a new
  **canonical Project Identity** layer rather than a rewrite of either
  side.
  - **Identity bridge** (`app/workspace/identity.py`, new): a bidirectional,
    nullable link — `projects.discovery_item_id` (Project → discovery
    item) and `adopted_projects.canonical_project_id` (discovery item →
    Project) — resolved lazily and idempotently by
    `get_or_create_canonical_project_id()`. Resolution order: reuse an
    existing valid link → link an existing *unlinked* manual Project with
    a case-insensitive matching name (backward-compatible migration,
    never overwrites existing Project fields) → create a minimal new
    Project (name + `Discovered` workspace only — never duplicates git/
    health/docs metadata, which continues to live exclusively in the
    Workspace scan cache). A stale link (the linked Project row was
    deleted out-of-band) self-heals by re-resolving instead of returning a
    dangling id. `service.adopt_item` now resolves a canonical identity as
    part of adoption itself, and `enrich_project_item` self-heals one for
    any already-adopted item that doesn't have one yet — so every adopted
    project has a working canonical identity with zero manual setup.
  - **Resume Work** (`app/workspace/resume.py`, new) — one primary action
    per project that automatically: finds or creates the latest AI
    Session (zero manual creation required), marks it current, builds the
    Resume Prompt from the latest Snapshot (existing, unmodified
    `app/services/resume.py::build_resume_prompt`), resolves the
    assistant conversation URL (or a homepage fallback), and touches
    `last_used_at`. Exposed via a new endpoint,
    `POST /workspace/discovered/{item_id}/resume-work` (404 until the
    item is adopted), and a shared frontend helper `triggerResumeWork()`
    that copies the prompt, opens the assistant URL, and navigates to
    Cockpit. Wired as the primary action on the Discovered Project Detail
    view, Home's Quick Resume card, and every Workspace Advisor
    recommendation card — all three now trigger real session creation
    instead of merely linking to a page.
  - **History wiring** — `get_enriched_item` now resolves the canonical id
    once and uses it for both AI Sessions (fixing a real Sprint 4 bug:
    it was previously querying with the raw discovery-item hash, which
    never matched a real `projects.id` and silently returned empty
    results) and a new `timeline` field
    (`projects_db.list_project_timeline`) — both now shown on the
    Discovered Project Detail view.
  - **Backward compatibility** — existing manually-created projects keep
    working unchanged (verified via a dedicated test); the name-match
    migration only ever sets the new nullable column, confirmed to leave
    notes/description/priority/collections untouched. The Projects page
    filters out canonical rows (`discovery_item_id` set) so an adopted
    project is never shown twice.
  - 46 new tests (`test_projects_identity.py`, `test_workspace_identity.py`,
    `test_workspace_resume.py`, `test_workspace_sprint5_api.py`,
    `test_workspace_sprint5_ui.py`) plus an updated
    `test_workspace_portfolio.py`, covering the identity bridge (creation,
    idempotency, name-match linking, no cross-item collisions, read-only
    vs. create semantics, stale-link self-heal, real paths with spaces/
    parentheses), Resume Work sequencing (zero manual creation, session
    reuse, snapshot-aware prompts, URL resolution, idempotency), and full
    API integration (404 before adopt, 200 after, canonical project
    visible in `/pi/projects`, every existing AI Sessions/resume/
    snapshot/timeline endpoint working unmodified against the canonical
    id, backward-compat migration, no scanned file ever modified). Also
    manually verified end-to-end in a live browser/API session against the
    real `1 - IA PROJECTS` folder: `ROLE_OS`'s Resume Work button created
    a real AI Session, copied a real prompt, opened `https://claude.ai`,
    a real snapshot was recorded through the existing `/pi/projects/*`
    endpoint, and the Timeline showed both events — all without creating
    any project by hand. Full suite: 891 passed, 0 failed.

- **Project Context, Sprint C1 (Consolidation)** — a single, reusable
  `ProjectContext` builder (`app/project_context/`) that assembles
  everything a UI screen needs to describe one project (identity, health,
  git, commits, next action, a normalized advisor summary, assets/
  documents/knowledge counts, timeline, resume state) from the existing
  Discovery/Workspace/Project Intelligence/Advisor services, in one place
  — reusing all four unchanged rather than rewriting any of them.
  - **`build_project_context()`** resolves either a Workspace discovery
    item id or a canonical/PI project id (or both) to the same object;
    **`build_project_contexts_for_workspace()`** is the bulk variant for
    list pages, reusing the existing enrichment pass with zero extra
    per-item cost.
  - New additive API: `GET /project-context` (bulk, adopted-only) and
    `GET /project-context/{identifier}` (404 if neither identity
    resolves).
  - **Two real, previously-undetected bugs fixed as part of centralizing**
    (not rewrites — the same functions, called once instead of
    inconsistently): `get_home_portfolio`'s `latest_ai_session` was
    silently always `None` (`enrich_project_item` never attached the AI
    session summary it already computed); `get_enriched_item` computed
    the same AI session summary twice per call. Both fixed by having
    `enrich_project_item` accept and attach a precomputed `ai_summary`.
  - **Real duplication removed at the frontend edge**: the Discovered
    Project Detail page's Recent Activity section used to fetch the
    *entire* activity feed (every adopted project) and filter it
    client-side; `GET /workspace/activity` and `GET /workspace/assets` now
    both accept an optional `project_id` that filters server-side,
    restricting the underlying git/filesystem work to just that project.
  - **Real duplication removed in Cockpit**: its "Next Action" card was
    computed entirely ad hoc from the current session's snapshot, with no
    fallback to git/filesystem heuristics the way the Workspace-side
    Discovered Project Detail view already had. Cockpit now consults
    `/project-context/{id}` for this field first (falling back to its
    prior computation if that fetch fails), so a project linked to a
    discovered folder shows the same richer, multi-source next action in
    both places.
  - Two structurally different recommendation shapes (Epic 2 Advisor's
    `priority_score`/`confidence_score`/`title` vs. Workspace Advisor's
    `priority`/`confidence`/`recommendation`) are normalized into one
    `advisor_summary` shape inside the builder — the two underlying
    engines are untouched; only the new consolidated surface merges them.
  - 23 new tests (`test_project_context_builder.py`,
    `test_project_context_api.py`, `test_project_context_ui.py`, plus
    additions to `test_workspace_sprint4_api.py`/`test_workspace_service.py`)
    covering identity resolution in both directions, the manual-project
    next-action fallback vs. discovery-extraction precedence, health-tier
    bucketing, advisor-summary normalization, the bulk/single-item cost
    difference, the two fixed bugs (with an explicit call-count
    regression test for the double AI-session lookup), the new
    `project_id` filters on `/workspace/activity`/`/workspace/assets`,
    and that no scanned project file is ever modified. Also manually
    verified end-to-end in a live browser against the real
    `1 - IA PROJECTS` folder: the Discovered Project Detail page's
    Recent Activity now issues a server-scoped `?project_id=` request
    instead of the old whole-feed-then-filter call; Cockpit's Next Action
    fetch to `/project-context/{id}` succeeds for both a purely-manual
    project and one linked to a discovered folder; and Home's "Latest AI
    Session" card — previously always blank — now shows the real,
    current session. Full suite: 926 passed, 0 failed.
  - **Known scope limit**: Home's "Today's Focus"/"Workspace Overview"
    sections and the Projects/Advisor *list* pages are not yet rewired to
    consume `ProjectContext` — the bulk endpoint exists and is tested, but
    swapping those five list-rendering call sites over (and deciding
    whether Epic 2's Advisor and Workspace Advisor should eventually
    become one engine, not just one normalized output shape) is
    recommended as a follow-up sprint, to keep this sprint's blast radius
    to the two single-project detail views plus the shared backend
    service. (Delivered as Sprint C1B, below.)

- **Project Context, Sprint C1B (Rewiring)** — a consolidation audit found
  Sprint C1's `ProjectContext` builder had exactly one production caller
  (Cockpit, one field, wrapped in a swallowed try/catch); every other
  project-oriented screen still independently assembled its own project
  data, and the builder's own health-tier thresholds (80/50) disagreed
  with the frontend's (70/40) — a project scoring 75 was "healthy" via the
  API and "warning" everywhere it was actually rendered. This sprint made
  `ProjectContext` load-bearing instead of a side door.
  - `GET /workspace/discovered?view=top_level`, `GET /workspace/home`,
    `GET /workspace/discovered/{id}`, `GET /pi/projects`,
    `GET /pi/projects/{id}`, `GET /workspace/advisor`, and
    `GET /advisor/recommendations` now all embed a real `project_context`
    per project (or per recommendation), built from the one canonical
    function — not a parallel shape.
  - Cockpit no longer makes a separate `/project-context/{id}` fetch; it
    reads `project.project_context` already present on the `/pi/projects`
    row it fetched anyway.
  - **Health tier**: one canonical `app/project_context/health.py`
    (`HEALTHY_THRESHOLD=80`, `WARNING_THRESHOLD=50`); the frontend's
    `healthTier` fallback is hand-synced to the same numbers and pinned by
    a test that parses the JS source. `health_score_source` names which of
    the two distinct scoring algorithms (`discovery.health`, 8 signals, vs
    `projects.health`, 6 signals) produced a given score, rather than
    leaving two unlabeled numbers pretending to be one concept.
  - **Next action**: the builder's C1-era inline mini-extractor (hardcoded
    0.6 confidence) is gone; a manual project's AI-session hint now routes
    through the same `discovery.next_action.extract_next_action` a
    discovered project uses, so the same source always carries the same
    confidence (0.95).
  - **Resume state**: `workspace/resume.py` gained `preview_resume_state()`
    — a real, read-only mirror of `resume_work()`'s own orchestration (no
    session creation, no mutation) — replacing a disconnected boolean stub
    nothing previously read.
  - **Asset count**: `ProjectContext.assets_count` now calls the same
    `assets_index.index_assets_for_project` the Assets page uses, instead
    of a cheaper, looser `discovery_detail` field-sum that could silently
    disagree with it.
  - Four separate JS status-badge functions now share one `badgeHtml()`
    presentation helper (their distinct status vocabularies — AI session,
    PI project, Daily Session, Workspace adoption state — were correctly
    left unmerged).
  - 13 new tests (`test_project_context_rewiring.py`) proving each screen's
    endpoint actually embeds `project_context`, asset-count parity against
    the real index, resume-state parity before/after a real resume call,
    health-tier parity between the Python constant and the JS source, and
    that manual + discovered projects both work end-to-end. Full suite:
    909 passed. Also verified live against the real workspace (17
    discovered projects, 5 adopted): Home/Cockpit/Workspace/Advisor all
    rendered real data with zero console errors, and Resume Work worked
    end-to-end for a real project.
  - **Known scope limits, left explicit rather than silently claimed
    fixed**: Workspace's nested child/repository rows don't carry their
    own embedded `project_context` (only top-level projects do); the AI
    Launcher's `_pending_tasks_block` still reads Daily Session's own
    manually-typed registry fields (a genuinely different domain, no
    discovery link); there is no CI guard yet that fails when a *new*
    project-oriented route bypasses `ProjectContext`.

- **Dashboard 2.0, Sprint C2** — replaces the legacy Dashboard (which
  showed Explorer's own `/import/metrics` — extracted-knowledge-object
  counts, honestly zero whenever no ChatGPT conversations had been
  imported, even though the real workspace already had adopted projects,
  commits, sessions, and recommendations) with an executive dashboard
  powered by `ProjectContext` and the existing Home/Advisor/Activity/
  Assets/Knowledge services.
  - One new additive endpoint, `GET /dashboard/summary`
    (`app/dashboard/service.py`), composing — never recomputing —
    `ProjectContext` (workspace + manual PI projects), `workspace.service.
    get_home_portfolio`, `workspace.advisor.generate_recommendations`,
    `workspace.service.list_activity_feed`/`list_project_assets`, and
    `app.db`'s Knowledge counts into one already-shaped payload: executive
    summary cards, portfolio status groups (Healthy/Warning/Critical/
    Active/Inactive/Launch-ready), a single Continue Work recommendation,
    a Needs Attention list, a deduplicated Recent Activity feed, Recent
    Assets, and Recent Knowledge.
  - **One genuinely missing rule added** to the existing Workspace Advisor
    rule set (`workspace/advisor.py`): `rule_snapshot_blocker` surfaces a
    blocker recorded in a project's latest AI session snapshot — real
    evidence (`AISessionSnapshot.blockers`) no existing rule exposed —
    added as a pure function alongside the other ten rules, not a new
    engine.
  - **Active/Inactive** and **Launch-ready** portfolio groups reuse
    `workspace.advisor`'s own `last_activity_age_days`/
    `INACTIVE_DAYS_THRESHOLD` and `rule_near_completion` directly — no new
    scoring heuristic.
  - **Continue Work** reuses `workspace.portfolio.suggested_project_to_
    continue` verbatim (the same ranking Home already computes), with the
    canonical `ProjectContext` embedded for its resume button/next
    action/latest snapshot.
  - The legacy `renderDashboardPage` implementation (10 zero-centric
    metric cards, Recent Conversations/Extracted Objects, System Status)
    is fully removed from `static/js/app.js` and replaced — not left
    underneath the new page. Explorer's own `/import/metrics` endpoint is
    untouched and still used by the Explorer page.
  - Frontend is presentation-only: health tier, next action, resume
    availability, and recommendation priority are all read directly off
    `ProjectContext`/recommendation fields, never recalculated client-side.
  - 21 new/rewritten tests (`test_dashboard_v2.py`,
    `test_dashboard_ui.py`) proving real adopted projects move the
    executive cards off zero, health/dirty-repo/next-action counts match
    the canonical per-project data exactly, Recent Activity is
    deduplicated, Needs Attention items link to canonical project
    identity, empty states are honest ("Knowledge has not been imported
    yet.", "No reusable assets detected.", etc.), the old zero-centric
    path is gone, and manual + discovered projects both populate the
    dashboard. Full suite: 920 passed. Also verified live against the real
    workspace: Adopted Projects showed 7 (not 0), ROLE_OS and ROLE
    Commerce Factory appeared correctly across the summary cards/portfolio
    groups/Continue Work, 2 dirty repositories and 6 recent commits were
    reflected accurately, Resume Work was exercised end-to-end from the
    Dashboard (created/opened a real AI session, opened claude.ai), and no
    scanned project file was touched. Zero application console errors.
  - **Known limitation**: a real, pre-existing data-quality artifact was
    observed (not introduced or fixed by this sprint) — "ROLE Commerce
    Factory" exists as two separate project rows (one discovery-linked,
    one purely manual with no `discovery_item_id`), so it appears twice in
    the portfolio-status groups. Deduplicating by name was deliberately
    not attempted (an unreliable heuristic, same rationale as
    `_knowledge_count`'s existing soft-match caveat) — flagged for the PI/
    Workspace identity model, not silently merged here.

- **Project Identity Reconciliation, Sprint C2.1** — fixes the exact
  duplicate Dashboard 2.0's live verification found: "ROLE Commerce
  Factory" existed as two `projects` rows (one discovery-linked, one
  purely manual). Adds `app.projects.db.merge_project` (one transactional,
  rollback-safe merge migrating AI Sessions/Snapshots/capabilities/
  dependencies/AI Workspace, union-merging notes/decisions/todos/etc.,
  and marking the duplicate `merged_into_project_id` — **never deleting**
  it) and `app.workspace.reconciliation` (evidence-based duplicate
  detection — name/root-path/git-remote/workspace/discovery-link — that
  only ever reports, never auto-merges; `POST /pi/projects/reconciliation/
  merge` requires an explicit `confirm: true`). `get_project`/`identity.py`
  now transparently resolve a merged id to its survivor, so every existing
  consumer deduplicated with zero code changes. 16 new tests; full suite
  935 passed. Executed live: merged the real duplicate, verified it
  appears exactly once across Projects/Workspace/Dashboard/Advisor/
  Cockpit.

- **Explorer 2.0, Sprint C3 (+ C3.1 hardening)** — turns Explorer into a
  universal search over every existing domain (Projects, AI Sessions,
  Snapshots, Commits, Knowledge Cards, Assets, Conversations, Markdown,
  Decisions, Capabilities, Dependencies, Recommendations, Timeline
  Events), via one new aggregation endpoint, `GET /explorer/search`
  (`app/explorer/service.py`) — no new storage, every result type reuses
  an existing lookup/search function exactly once. Adds a Project Hub
  (`GET /explorer/project/{id}`, `#/phub/{id}`) composing Overview/
  Sessions/Snapshots/Assets/Knowledge/Recent Activity/Commits/
  Recommendations from existing services. Results are grouped by type,
  collapsible, ranked by a documented point system (exact match, canonical
  project, title/filename/summary match, recency, ProjectContext
  priority). **C3.1**: live verification found Explorer's frontend still
  defaulted to the entire legacy Sprint B1.5 "Imported Conversations"
  browser (its own `/import/metrics` counters, filters, paginated table)
  as the page's dominant content, only hidden once a query was typed —
  removed entirely (8 functions, the metrics grid, the paginated table),
  and the universal search now runs immediately on load (empty query =
  a real bounded browse). Also found and fixed a genuine duplicated-
  aggregation violation: `app.dashboard.service` and `app.explorer.
  service` each kept a private copy of "every tracked project" — replaced
  with one shared `app.project_context.builder.all_project_contexts()`.
  33 + 5 new tests; full suite 968 passed. Verified live: `ROLE` → all 5
  real projects, `README` → 7 markdown docs, `Claude` → a real AI Session,
  `PNG` → 7 real assets, `TODO` → real documentation.

- **Assets OS, Sprint C4** (`dashboard/app/assets/`) — replaces the
  Assets page's flat technical file listing with a visual Asset Library:
  responsive gallery (default) and compact list views, real thumbnails
  (Pillow-generated, cached under `var/role_os_dashboard/asset_thumbnails/`
  — never inside a scanned project folder), type-specific placeholders for
  unsupported formats, and an Asset Detail panel (large preview, complete
  metadata, duplicate group, reusable/category/favorite overrides, Open
  File/Open Folder/Copy Path/Open Project — no destructive actions).
  - **Canonical `AssetRecord`** (`app/assets/model.py`): asset_id,
    canonical_project_id, discovery_item_id, filename, absolute_path,
    relative_path, extension, asset_type, category, mime_type, size_bytes,
    width/height, duration_seconds (honestly `None` — video/audio duration
    extraction is out of scope this sprint), modified_at, reusable,
    likely_logo, duplicate_hash, duplicate_group_id, preview_available,
    preview_url, source, favorite. One model, used by the Assets gallery,
    Explorer's Asset results, Project Hub, and Dashboard previews — no
    second asset mapper (`app.workspace.assets_index` is now a thin
    backward-compatible shim delegating here).
  - **Deterministic classification** (`app/assets/classification.py`, no
    LLM): 16 categories (Logo/Brand/Character/Photo/Illustration/
    Screenshot/Icon/Social Media/Thumbnail/Template/Video/Audio/Document/
    Font/Prompt Resource/Other) from filename/folder regex, image
    dimensions (icon-sized, common screenshot resolutions), and extension,
    in a fixed priority order. Reusable defaults to `True` only for
    Logo/Brand/Character/Template/Font/Icon; screenshots/photos/
    thumbnails/ordinary exports default to `False`, per the brief's
    explicit "do not mark ordinary screenshots and temporary exports
    reusable by default."
  - **Safe preview service** (`app/assets/preview.py`,
    `GET /assets/{id}/preview`): every request resolves the target
    exclusively through `resolve_safe_path`, which re-derives the real
    path from a validated `asset_id` already present in the live index
    and checks it resolves inside a currently-adopted project root — a
    client can never submit an arbitrary filesystem path. Raster images
    are resized (max 480px) and cached (keyed by asset id + source
    mtime, so an edited source is never served a stale thumbnail); SVG is
    served as its own file with an `image/svg+xml` type (safe to embed via
    `<img>`, no sanitizer dependency needed); unsupported formats report
    `preview_available: false` and the frontend shows a type placeholder.
  - **Cache** (`app/assets/db.py`, new `role_os_assets.db`): `asset_cache`
    (path+mtime+size-keyed dimensions/duplicate-hash, so an unchanged file
    is never re-opened or re-hashed) and `asset_overrides` (the only place
    a user's reusable/category/favorite choice lives — never written back
    into the scanned file).
  - **Duplicate detection**: the existing partial-content SHA1 hash, now
    resolved into a real `duplicate_group_id` only for files that actually
    share it with 2+ others; `GET /assets/duplicates/{group_id}` lists
    every member with its project/path. Never auto-deletes or consolidates.
  - **Canonical API** (`app/routers/assets.py`, namespaced under
    `/assets`): list/search/filter/paginate, detail, preview, raw file
    stream, `PATCH` for overrides, duplicate group, freshness, and (this
    dashboard's own machine only) `open-file`/`open-folder` OS-integration
    actions. `GET /workspace/assets` (Sprint 4) is unchanged and already
    delegates to this same canonical service.
  - **ProjectContext.assets_count parity**: unchanged from Sprint C1B —
    still the same canonical index, now richer; a dedicated test
    (`test_project_context_assets_count_matches_canonical_index`) pins the
    two numbers can never disagree.
  - **Explorer integration**: an Explorer "Asset" result's primary action
    now opens the real Asset Detail panel (`nav: "asset"`), the exact same
    panel the gallery uses — no second asset representation.
  - 43 new tests across `test_assets_os.py` (backend: canonical record
    shape, PNG/SVG dimension parsing, reusable/category classification,
    overrides never touching the source file, duplicate grouping, project
    filtering, search, pagination, path traversal + outside-adopted-root
    rejection, missing files, cache invalidation, oversized-image preview
    failing honestly instead of 500, ROLE OS's own runtime directory never
    leaking into the index from this process *or* a second, independent
    process resolving the same relative default elsewhere) and
    `test_assets_ui.py` (frontend: canonical
    API usage, no client-side category/reusable/duplicate computation, no
    destructive actions, view-mode persistence, Explorer/Project Hub
    wiring). 4 pre-existing Sprint 4 tests updated for the intentionally
    new category values. Full suite: 1011 passed, 0 failed. Verified live against the
    real `1 - IA PROJECTS` folder — see the Sprint C4 completion report
    for exactly which real images/logos were detected.
  - **New dependency**: Pillow (`>=10.0,<12.0`) — real thumbnail
    generation/resizing needs an image library; nothing else in this
    sprint required a new dependency.
  - **Bugs found and fixed during live verification** (none present in
    the unit-test suite, all now covered by regression tests): (1) a
    filename/folder classification regex used `\bword\b` boundaries, but
    Python's `re` treats `_`/`-` as word characters, so `shot_4_logo.png`
    never matched `\blogo\b` — fixed by normalizing `_`/`-` to spaces
    before matching; (2) a ~208-megapixel real image crashed the preview
    endpoint with an uncaught `PIL.Image.DecompressionBombError` (HTTP
    500) because `preview.py` never imported `image_meta`'s
    `Image.MAX_IMAGE_PIXELS` guard as a fixed side effect — fixed by
    importing it explicitly and catching the exception as an honest 422
    with a graceful frontend placeholder, not a crash; (3) classification
    matched the file's *entire absolute path* (all ancestor directories,
    including ones outside the scanned project — a Windows username, "My
    Drive", a pytest tmp dir named after the running test) instead of
    just the path relative to the scanned project root, which could
    misclassify a file based on an unrelated ancestor folder name
    elsewhere in the tree — fixed to match only the root-relative folder
    path; (4) the generated thumbnail cache directory was itself
    discovered and indexed as a project asset when a scanned root
    contained it (as ROLE_OS's own checkout does) — fixed by excluding
    `Settings.asset_thumbnail_cache_dir`'s resolved parent directory from
    every scan, reading the *actual* configured (and already-resolved)
    path rather than assuming it lives at a fixed location relative to
    the repo root (every `var/`-relative default in `config.py` is a
    relative path resolved against the process's current working
    directory at `Settings()` construction time, not against
    `repo_root` — the two can differ depending on the server's launch
    cwd); a resolved-path exclusion still only knows about *this
    process's own* runtime directory, though — a second, unrelated
    process (a pytest run launched from the repo root while a dev server
    was already running from `dashboard/`) independently resolved the
    same relative default to a *third* physical location, which leaked
    into the live asset list the same way. Fixed with a second,
    structural layer: excluding by the literal, never-varying
    `role_os_dashboard` directory name (the one path segment every
    `var/`-relative default in `config.py` shares regardless of which
    `var/` parent it resolves under), the same way `.git`/`node_modules`
    are excluded by name rather than by one specific resolved location.
  - **Known limitations**: video/audio duration extraction not
    implemented (`duration_seconds` always honestly `None`); no Range-
    request/seek support for video/audio streaming (full-file playback
    only); Open File/Open Folder only implemented for Windows (the
    platform this dashboard is built to run on); no real duplicate assets
    currently exist in the verified real dataset, so duplicate-group
    grouping was verified only via unit tests, not against live data.

### Changed

- UX Sprint UX-001 "Cockpit Redesign" — turns the v1.4 Cockpit from an
  administration form into a daily work dashboard. **Frontend-only**: no
  backend, API, database, or migration changes — same
  `/pi/projects/{id}/ai-sessions*` and `/pi/projects/{id}/timeline`
  endpoints as before, including the previously-unused
  `GET .../ai-sessions/{id}/snapshots` (now called from the UI for the
  first time to derive the new insight cards).
  - New **project header** (`.cockpit-header`): project name, workspace,
    status, and last activity (the later of the project's `updated_at`
    and the current session's `last_used_at`), replacing the bare "New AI
    Session" form that used to open the page.
  - New prominent, primary **Resume Work** button at the top of the page,
    wired through the same `[data-resume]` handler as the per-session
    Resume buttons (`data-resume` set to the current session's id, or the
    most recently started session if none is flagged current) — no
    duplicated resume logic.
  - **New AI Session is collapsed by default** and only expands via its
    own `+ New AI Session` toggle button; it **auto-collapses again**
    after a successful creation (failures leave it open with the error
    shown inline, matching every other form in the app).
  - **Current AI sessions are promoted**: the session list is sorted
    current-first and the current session's card gets a distinct
    highlight and a "Current" badge.
  - **Project Timeline entries now carry an icon** (a session-start marker
    vs. a snapshot marker) via a new `timelineIcon()` helper.
  - New **Today's Objective / Next Action / Last Snapshot** cards, derived
    from the current session's latest snapshot's `pending_work`,
    `next_prompt`, and `summary` fields respectively (with a friendly
    fallback when no snapshot exists yet).
  - **Secondary session actions** (Open, Favorite, Set current, Snapshot,
    Delete) are now hidden behind a per-session overflow (`&#8942;`) menu
    — only Resume stays visible by default. The page-level project
    switcher moved into a matching header overflow menu.
  - Reuses the existing responsive `.home-grid` two-column layout (main
    column + Project Timeline sidebar, collapsing to one column under
    1100px) and adds a matching responsive rule for the new header.
  - 19 new tests in `test_cockpit_redesign_ui.py` covering the header,
    Resume Work prominence and wiring, collapsed/expanded/auto-collapse
    states (including that a failed creation does *not* auto-collapse),
    current-session promotion, timeline icons, the three insight cards,
    both overflow menus, the responsive layout, and that only the
    pre-existing endpoints are used. `test_cockpit_ui.py` (the v1.4
    Cockpit test file) was left completely unmodified and all 9 of its
    tests still pass unchanged. Full suite: 583 passed, 0 failed.
  - Verified live against a running server: created a project with two AI
    sessions, set one current, added a snapshot with distinct
    accomplishments/pending-work/next-prompt/summary values, and
    confirmed the sessions, snapshots, timeline, and resume API responses
    all carry exactly the data the redesigned Cockpit needs — plus
    confirmed the served HTML/JS/CSS actually contain the new header,
    Resume Work button, collapsible form, overflow menus, and timeline
    icons.

### Added

- First Run Experience — when Project Intelligence has zero projects, the
  Projects page is replaced by a guided onboarding screen with a
  "Create your first Project" wizard, instead of the old empty-state
  message. Once at least one project exists, the normal Projects list
  returns with a permanent **+ New Project** button. **Frontend-only,
  additive**: no backend or API changes — the wizard creates the project
  through the existing, unmodified `POST /pi/projects`.
  - Detection is based on the true, unfiltered project total
    (`fetchJSON("/pi/projects")` with no query string), not whatever the
    header's workspace filter currently shows — so a workspace filter
    matching zero projects is never mistaken for a genuinely empty
    account.
  - Both the onboarding wizard and the normal-mode "+ New Project" inline
    form are built from one shared field generator
    (`renderCreateProjectFieldsHtml()`, reusing the same header
    `workspacesCache`) and submitted through one shared handler
    (`handleCreateProjectSubmit()`, parameterized only by which status
    `<div>` to write progress/errors into) — no duplicated, potentially-
    diverging form logic between the two paths.
  - On success: a toast ("Project created. Let's start your first AI
    Session!") via the existing `showToast()`, then automatic navigation
    to the new project's **Cockpit** (`navigate("cockpit", project.id)`)
    to prompt starting the first AI Session, reusing the v1.4 Cockpit
    (Context Engine) page as-is.
  - On failure: an inline `error-box` with the server's error message and
    a re-enabled submit button — no navigation, no toast, same failure
    pattern as every other form in the app.
  - 12 new tests in `test_first_run_ui.py` covering first run, normal
    mode, successful creation, API failure, and automatic navigation
    (plus the shared-form/shared-handler and unfiltered-detection
    invariants above), in the same string-assertion style against the
    served `app.js` as `test_cockpit_ui.py` / `test_launcher_ui.py` (no
    JS runtime/browser test harness exists in this repo). Full suite:
    594 passed, 0 failed.
  - Verified live against a running server: `/pi/projects` returning `[]`
    confirmed to trigger the onboarding path, a project created through
    `POST /pi/projects` (the wizard's own endpoint), the list correctly
    switching to normal mode afterward, and the new project's Cockpit
    endpoints (AI Sessions, Timeline) loading correctly.

- v1.4 "Context Engine" — replaces v1.3's single AI Workspace record per
  project with an **AI Sessions collection**: any number of assistant
  conversation sessions per project, each with a title, assistant,
  conversation URL, role, preferred model, started/last-used timestamps,
  status, favorite/current flags, and notes. Adds **Session Snapshots**
  (accomplishments / blockers / pending work / next prompt / decisions /
  summary), a **Resume Engine** that turns the latest snapshot into a
  one-click continuation prompt, a **Project Timeline** aggregating
  session starts and snapshots in order, and a new unified **Cockpit**
  page tying all of it together. **Two new tables in the existing
  `role_os_projects.db`** (no new SQLite file); v1.3's `ai_workspace`
  table, its API, and `/launcher/*` (v1.2) are all left fully intact and
  functional — unchanged, not just additive.
  - New `ai_sessions` and `ai_session_snapshots` tables plus a real,
    tracked migration mechanism (`schema_migrations` table,
    `0001_ai_sessions_from_ai_workspace`) in `app/projects/db.py`: on
    first connection to an existing v1.3 database, every non-empty
    Claude/ChatGPT/Gemini URL in `ai_workspace` is **copied** (never
    moved or deleted) into a new, `current`-flagged AI Session — runs at
    most once per database file, and is a no-op for a brand-new install.
  - New `dashboard/app/routers/pi/ai_sessions.py`, nested under the
    existing `/pi/projects/{id}` prefix: full CRUD for sessions,
    `set-current` (scoped per project+assistant, so a project can have a
    current Claude session and a current ChatGPT session at once),
    `open` (saved URL or the assistant's homepage), snapshot
    create/list, `resume` (Resume Engine), and `/pi/projects/{id}/
    timeline`.
  - New `dashboard/app/services/resume.py`: `build_resume_prompt()`, a
    pure function assembling a "Resume ROLE OS AI Session" prompt from a
    session and its latest snapshot — no AI/LLM call, same pattern as
    `app.services.launcher` (v1.2).
  - New **Cockpit** page (`#/cockpit`, new sidebar item): a project
    selector, a New AI Session form, one card per session (Resume / Open
    / Favorite / Set current / Snapshot / Delete), and the Project
    Timeline. Resume copies the prompt to the clipboard and opens the
    saved (or fallback) URL client-side, reusing the same toast pattern
    as v1.2/v1.3 — no browser automation anywhere.
  - The Project detail page's old single-record AI Workspace card is
    **replaced** by a lean AI Sessions summary (top 3 sessions + a link
    into the Cockpit for this project) — the v1.3 UI code
    (`renderAiWorkspaceCardHtml`/`wireAiWorkspaceCard`) was removed as
    dead code once superseded; the v1.3 *backend* it called remains
    fully live and tested.
  - 74 new tests across `test_ai_sessions_migration.py` (8, including an
    explicit "runs at most once" and "no-op on a fresh database" check),
    `test_ai_sessions_db.py`, `test_resume_service.py`,
    `test_ai_sessions_api.py` (including explicit backward-compatibility
    checks against `/launcher/start` and `/pi/projects/{id}/ai-
    workspace`), and `test_cockpit_ui.py`; `test_ai_workspace_ui.py` was
    updated to assert the old card is gone and the new summary card
    replaced it, while its backend-contract siblings
    (`test_ai_workspace_db.py`, `test_ai_workspace_api.py`) were left
    untouched. Full suite: 582 passed, 0 failed.
  - Verified live against a running server: two Claude sessions for one
    project, `set-current` correctly scoped per assistant, a real
    snapshot, a Resume Engine call returning the exact saved URL and an
    assembled prompt, a Project Timeline in chronological order, and
    confirmation that `/launcher/start` and `/pi/projects/{id}/ai-
    workspace` behave exactly as before.

### Added

- AI Workspace (v1.3) — a per-project panel storing a saved Claude/
  ChatGPT/optional-Gemini conversation URL, a role, a preferred model,
  and a last-opened timestamp, so "Open Claude" reuses the actual
  conversation instead of always landing on the homepage. **Additive
  only**: one new table in the existing Project Intelligence database,
  one new router file, one new card on the Project detail page; no
  existing endpoint (including every `/launcher/*` route from v1.2) was
  changed.
  - New `ai_workspace` table in `role_os_projects.db` (Project
    Intelligence's existing SQLite file — no new database file):
    `claude_url`, `chatgpt_url`, `gemini_url`, `role`,
    `preferred_model`, `last_opened_at`, one row per project. Persisted
    server-side in this same store the Project Intelligence page already
    reads from — never browser `localStorage`.
  - New `dashboard/app/routers/pi/ai_workspace.py`, nested under the
    existing `/pi/projects/{id}` prefix (same pattern as capabilities/
    dependencies): `GET`/`PUT .../ai-workspace` (Save Conversation,
    partial-update semantics — saving just one field doesn't clear the
    others), `POST .../ai-workspace/open` (`{"tool": "claude"|"chatgpt"|
    "both"}` → for each tool, the saved URL if one exists, otherwise
    that tool's homepage, and records `last_opened_at` either way).
  - New **AI Workspace** card on the Project detail page: connection
    status (Connected/Not connected) per tool, role, preferred model,
    last opened; **Open Claude** / **Open ChatGPT** / **Open Both**
    buttons; a **Save Conversation** form. Reuses the v1.2 toast
    (`showToast`) for "No conversation saved yet." when an Open action
    falls back to a homepage — no new toast infrastructure.
  - No browser automation of any kind — opening a saved or fallback URL
    is a plain client-side `window.open`, identical in kind to the v1.2
    AI Launcher's approach; verified by a UI test asserting no
    automation-library name appears in the served JS.
  - 28 new tests: `test_ai_workspace_db.py`, `test_ai_workspace_api.py`,
    `test_ai_workspace_ui.py`, including an explicit check that
    `/launcher/start` is unaffected. Full suite: 515 passed, 0 failed.
  - Verified live against a running server: created a real project,
    saved a Claude conversation URL, and confirmed "Open Both" correctly
    returned the saved Claude URL alongside the ChatGPT homepage
    fallback, with `any_missing: true` — exactly the mixed-state
    behavior requirement 5 describes.

### Added

- AI Launcher (v1.2) — one-click session start. **Additive only**: one
  new service module, one new router, three new buttons on the Session
  page; every existing endpoint, page, and database is unchanged.
  - New `dashboard/app/services/` package (a new category alongside
    domains: a service reads existing data and performs a local action,
    without owning any persistence of its own) with `launcher.py`:
    `build_launch_prompt()` assembles a session-initialization prompt
    from the active session (project, mode, objective), the linked
    project registry entry's milestone/next action ("Pending Tasks"),
    and the three most recent ecosystem decisions (via the existing
    `app.session.decisions_adapter`); `resolve_launch_urls()` maps
    `"claude"` / `"chatgpt"` / `"both"` to `https://claude.ai` /
    `https://chatgpt.com`. Pure functions, no AI/LLM call, no OS-level
    action of any kind.
  - New `dashboard/app/routers/launcher.py`, namespaced under
    `/launcher`: `POST /launcher/start` (409 if no session is active,
    422 for an unrecognized tool), returning the assembled prompt and
    target URL(s) only — it never touches the clipboard or the browser
    itself.
  - New **AI Launcher** card on the Session page (visible while a
    session is active): **Start Claude**, **Start ChatGPT**, **Start
    Both** buttons. Each copies the prompt to the clipboard
    (`navigator.clipboard.writeText`) and opens the target site(s) in a
    new tab (`window.open`) client-side, then shows a toast: "Prompt
    copied. Press Ctrl+V and Enter." New `.toast` component in
    `components.css`, honoring the existing `prefers-reduced-motion`
    rule with no new animation infrastructure.
  - **No typing automation, no browser-driving library (no Playwright,
    no Selenium, no Puppeteer) anywhere** — reducing session startup to
    one click is achieved entirely by clipboard + new-tab, per v1.2's
    explicit scope. Verified by both a unit test asserting the service
    module's only imports are `__future__`/`typing`, and a UI test
    asserting none of those libraries' names appear in the served JS.
  - 23 new tests: `test_launcher_service.py`, `test_launcher_api.py`,
    `test_launcher_ui.py`. Full suite: 487 passed, 0 failed.
  - Verified live against a running server: a real session for `ROLE
    Commerce Factory` correctly pulled that project's actual, real
    milestone/next-action into "Pending Tasks", and the launcher call
    left the active session completely untouched (read-only).
  - App version intentionally **not** bumped in this change — per this
    project's established practice (see the `v1.1.0` history), a
    dedicated release/LAUNCH-mode pass performs the version bump,
    `CHANGELOG.md` dating, and tag once a milestone is ready to ship.

### Added

- One-Click Windows Launcher — `Start ROLE OS.bat` / `Stop ROLE OS.bat`
  (thin double-click wrappers) plus `scripts/Start-RoleOS.ps1`,
  `scripts/Stop-RoleOS.ps1`, `scripts/RoleOS.Common.ps1`, and
  `CREATE_DESKTOP_SHORTCUT.ps1`. **Tooling only — no application code
  changed.**
  - Detects an already-running instance via a live `/health` probe
    (checking the JSON body's `app` field, not just the port), opens the
    browser without starting a second server if so.
  - Otherwise resolves Python (preferring a local virtual environment in
    a documented priority order, falling back to `py`/`python`/`python3`
    on `PATH`), verifies required packages, starts
    `uvicorn app.main:app --host 127.0.0.1 --port 8000` as a separate,
    minimized process, waits for health, opens the browser.
  - Clear, specific error handling for: missing `dashboard` folder,
    missing Python, missing dependencies (with the exact install command
    printed), port 8000 occupied by a different application, the server
    failing to become healthy, and an invalid/broken virtual environment.
  - `Stop ROLE OS.bat` stops only the specific process it started
    (PID file, cross-checked against that PID's own command line before
    killing anything) — never an unrelated Python/uvicorn process; stale
    or mismatched PID files are detected and removed safely.
  - Runtime files (`role_os.pid`, `launcher.log`, `uvicorn.out.log`,
    `uvicorn.err.log`) are written to `dashboard\var\role_os_dashboard\`
    — already git-ignored, no `.gitignore` change needed.
  - `CREATE_DESKTOP_SHORTCUT.ps1` creates a `ROLE OS` Desktop shortcut via
    Windows' own Desktop special folder (correctly handling a redirected
    Desktop, e.g. OneDrive), with a fallback icon chain (project `.ico` →
    standard Windows icon → the batch file's own icon). No Administrator
    privileges required anywhere in the launcher.
  - Verified against the real repository path (which contains both
    spaces and parentheses) for every scenario above, plus a genuine
    second-launch-no-duplicate check and a full stop/restart cycle.
  - See `docs/product/DECISIONS.md` for the three material design
    decisions behind this (PowerShell-with-batch-wrappers, live-health-
    probe over PID-trust, and the shared runtime directory choice).

### Fixed

- Launcher: the Knowledge page reported "SQLite database not found at:
  ROLE_OS\dashboard\samples\role_os_sample\00_SYSTEM\role_os.db" —
  `app/config.py`'s `ROLE_OS_DB_PATH` default is relative to the
  process's working directory, and the launcher starts uvicorn with
  `dashboard\` as that directory, so the default resolved one level too
  deep. `Start-RoleOS.ps1` now sets `ROLE_OS_DB_PATH` (and, since they
  share the identical root cause, `ROLE_OS_PROJECTS_DB_PATH`,
  `ROLE_OS_ADVISOR_DB_PATH`, `ROLE_OS_IMPORTS_DB_PATH`,
  `ROLE_OS_EXTRACTION_DB_PATH`) as absolute paths anchored to the
  repository root (`scripts/RoleOS.Common.ps1`'s new
  `Resolve-RoleOSDatabaseEnv`), logs each resolved path to
  `launcher.log`, and refuses to start — with a clear error, no server
  left running — if the Knowledge database isn't actually there.
  **No application code changed**; this is a launcher-only fix.
  - New opt-in `ROLE_OS_WORKSPACE_DIR` environment variable lets a user
    point the launcher at their own, permanent workspace (e.g. one
    generated by `builder/builder.py`) instead of the bundled sample
    fixture — explicit and inspectable, never automatic, never migrates
    or copies any data. See `INSTALLATION.md`'s "Which database does the
    launcher use?" section.
  - Verified live: `/health` reports `database_connected: true`, the
    Knowledge page's actual data endpoints (`/ui/recent`, `/projects`)
    return real sample content, the same failure-to-start behavior was
    confirmed against a genuinely missing database file, and the
    workspace override was verified against a real, pre-existing
    `ROLE_KNOWLEDGE_OS` workspace outside the repository.
  - Cleanup: `.gitignore` now narrowly re-excludes
    `samples/role_os_sample/00_SYSTEM/role_os_projects.db` and
    `role_os_advisor.db` specifically (auto-created runtime state, not
    curated fixture data) while still preserving the general
    `!samples/**/*.db` exception that keeps the real `role_os.db` fixture
    committable. The two files (confirmed to hold only default seed rows
    and zero real data) were removed from the working tree.
    `INSTALLATION.md` now states plainly that `samples/role_os_sample/`
    is demo data only, that `ROLE_OS_WORKSPACE_DIR` is the recommended
    configuration for real use, and exactly how to set it persistently
    on Windows via `setx` (no code or launcher behavior changed).

## [1.1.0] - 2026-07-30

### Added

- ROLE OS Dashboard MVP: Daily Session — the first functional MVP of a
  personal-operating-system daily workflow, per the ROLE Ecosystem's
  `SYSTEM.md`/`PRODUCT_LIFECYCLE.md` Build stage. **Additive only**: one
  new domain, one new router, one new SQLite file, one new sidebar page;
  every existing endpoint, page, and database is unchanged.
  - New `dashboard/app/session/` domain: `modes.py` (the single reusable
    source of truth for the six operation modes — PLAN, BUILD, CREATE,
    LAUNCH, OPERATE, LEARN — each with a name, purpose, expected AI
    behavior, and primary ROLE Ecosystem resources), `db.py` (SQLite
    persistence for sessions and a local project registry, following the
    exact same idempotent-schema/seed pattern as `app/projects/db.py`),
    `models.py` (Pydantic schemas), `markdown.py` (pure-function
    generation of the Claude session-initialization prompt and the
    Obsidian-compatible daily Markdown record — no AI/LLM call anywhere),
    and `decisions_adapter.py` (an adapter that reads the ROLE Ecosystem's
    own `DECISION_LOG.md` live when `ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH`
    is configured, falling back to a small, explicitly-labeled snapshot
    otherwise — never duplicates the full log).
  - New `dashboard/app/routers/session.py`, namespaced under `/session`:
    `GET /session/modes`; `GET`/`PATCH /session/registry[/{id}]`; `GET
    /session/current`, `GET /session/recent`, `GET /session/{id}`, `POST
    /session/start` (409 if a session is already active), `POST
    /session/{id}/complete`; `GET /session/{id}/prompt`, `GET
    /session/{id}/markdown`, `GET /session/{id}/markdown/download`, `POST
    /session/{id}/save-to-vault` (writes the record into an optional,
    never-hardcoded `ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR`), `GET
    /session/vault/config`; `GET /session/decisions/recent`.
  - Three new `Settings` fields (`app/config.py`): `session_db_path`
    (`ROLE_OS_SESSION_DB_PATH`, defaulting under the git-ignored `var/`
    directory rather than `samples/`, since session data is real personal
    data, not a checked-in fixture), `obsidian_daily_notes_dir`
    (`ROLE_OS_OBSIDIAN_DAILY_NOTES_DIR`, empty by default), and
    `ecosystem_decision_log_path` (`ROLE_OS_ECOSYSTEM_DECISION_LOG_PATH`,
    empty by default).
  - New sidebar page, **Session** (`#/session`), in
    `dashboard/app/static/js/app.js`: shows today's date, mode, project,
    objective, expected result, and session status (Not Started / Active
    / Completed) at a glance; a Start My Day form; the copyable Claude
    prompt once a session is active; an End My Day form; the generated
    Markdown record (copy, download, or optional save-to-vault) once
    completed; the local project registry (seeded with ROLE OS, ROLE
    ECOSYSTEM, ROLE MASTER, ROLE Commerce Factory, Brand Character OS,
    RoleValdez, and SUPER FACIL, editable inline); and Recent ecosystem
    decisions. Built as its own page rather than folded into the existing
    Home page, per the same reasoning as the Sprint 7 Dashboard decision
    (see `docs/product/DECISIONS.md`) — different data, different
    question, no natural shared layout.
  - Light-theme support added to `app/static/css/colors.css` via a
    `@media (prefers-color-scheme: light)` override block, purely
    additive: every existing rule already reads color exclusively through
    the custom properties that block redefines, so this alone re-themes
    the entire Command Center for a light OS preference, not just the new
    Session page.
  - 48 new tests: `test_session_db.py`, `test_session_markdown.py`,
    `test_session_decisions_adapter.py`, `test_session_api.py`,
    `test_session_ui.py`. Full suite: 464 passed, 0 failed.

## [1.0.0] - 2026-07-28

ROLE OS v1.0 release. See [`RELEASE_NOTES_v1.0.md`](RELEASE_NOTES_v1.0.md)
for the release-facing summary of highlights, known limitations, and
roadmap.

### Added

- Sprint 9: Release — the v1.0 release package. **Documentation only**: no
  code, API, database, or UI behavior changed except the version string
  itself.
  - New root-level release docs: `QUICK_START.md`, `INSTALLATION.md`,
    `ARCHITECTURE.md`, `RELEASE_NOTES_v1.0.md`, `LICENSE.md`,
    `FINAL_RELEASE_CHECKLIST.md`, `CONTRIBUTING.md`.
  - `README.md` reorganized with explicit Features, Architecture overview,
    Requirements, Running locally, Repository structure, and License
    sections (content already accurate elsewhere in the repo, now
    consolidated in one place).
  - `dashboard/README.md` updated to document the Settings domain
    (Sprint 8), which had shipped in code but was undocumented: the
    Settings page description, the `/settings/*` API table and response
    shape, a "Settings domain (Sprint 8)" narrative section, the
    Advisor Search default-limit change, and project-layout tree entries
    for every router/domain package that had been added since Epic 3
    (`imports/`, `extraction/`, `conversation_graph/`, `advisor_search.py`,
    `settings.py`) but was missing from that tree.
  - App version bumped from `1.0.0-alpha` to `1.0.0`
    (`dashboard/app/config.py`, `pyproject.toml`).

- Sprint 8: Settings — a Settings page backed by a real API, replacing the
  earlier placeholder that only read `/health`. **Additive only**: one new
  router, two new `Settings` fields, one default-value change to an
  existing endpoint; every other endpoint and page is unchanged.
  - Two new fields on `app/config.py`'s `Settings`: `license` (fixed
    `"Proprietary"`, matching `pyproject.toml`), `repo_root` (for git
    commit lookup), `default_import_path`
    (`ROLE_OS_DEFAULT_IMPORT_PATH`, informational only — nothing pre-fills
    an import dialog with it yet), and `search_result_limit`
    (`ROLE_OS_SEARCH_RESULT_LIMIT`, default 100).
  - `GET /advisor/search`'s `limit` query param now defaults to
    `Settings.search_result_limit` instead of a value hardcoded in the
    endpoint signature; passing `limit` explicitly still overrides it.
  - New `dashboard/app/routers/settings.py`, namespaced under `/settings`:
    `GET /settings` (general config, system status, about info,
    maintenance status in one response), `GET /settings/export` (download
    current settings as JSON), `POST /settings/import` (validate an
    uploaded configuration file and preview which `ROLE_OS_*` environment
    variables it maps to — never applies it to the running process, since
    there is no mechanism to safely mutate a live server's environment),
    `POST /settings/maintenance/rebuild-graph` (force a fresh
    `build_graph()` call and report node/edge counts), `POST
    /settings/maintenance/clear-cache` (clear the in-memory
    `get_settings()` `@lru_cache`).
  - Settings page (`dashboard/app/static/js/app.js`) rewritten to consume
    the new API: General/System status/About tables, an Export button, an
    Import-and-preview form, and Rebuild graph/Clear cache actions with
    their own status panel — replacing the old four-row `/health`-only
    table.
  - 16 new tests: `dashboard/tests/test_settings_api.py` (overview shape,
    export, import preview/validation/never-applies, maintenance actions,
    regression check that other endpoints are unaffected),
    `test_settings_ui.py` (nav/route/markup/endpoint-wiring regression
    checks), plus 2 new tests in `test_advisor_search_api.py` covering the
    new default-limit behavior. 386/386 passing repo-wide.

- Sprint 7: Dashboard — a new executive-summary sidebar page over the
  Importer/Explorer/Extraction/Knowledge Graph/Advisor Search pipeline.
  **Additive only, UI-first**: one new nav item/route, two thin new
  endpoints; zero new storage, zero new client- or server-side
  calculation beyond "most recent N" queries, zero changes to Home or any
  other existing page's content.
  - New API on the existing Extraction router (`routers/extraction.py`,
    zero changes to its existing endpoints): `GET /extraction/recent?limit=`
    (most recently extracted objects across every conversation, reusing
    the already-written `search_objects()` unfiltered) and `GET
    /extraction/runs?limit=` (most recent extraction runs across every
    conversation — the extraction-domain analogue of the already-existing
    `GET /import/history`). Backed by two additive functions in
    `app/extraction/db.py`: `_row_to_run()`, `list_recent_runs()`.
  - New **Dashboard** page (`dashboard/app/templates/index.html`,
    `dashboard/app/static/js/app.js`): sidebar nav item placed right after
    Home, route `#/dashboard`. Ten summary cards (Conversations, Projects,
    People, Tasks, Decisions, Ideas, Documents, Assets, Graph Nodes, Graph
    Edges) read verbatim from the existing `GET /import/metrics` — no
    field is recomputed, only displayed (reusing the same
    `health-dashboard-grid` + `animateCount()` pattern Home and the
    Explorer already use). Recent Activity (`GET /import/conversations`
    + the new `GET /extraction/recent`). System Status (`GET
    /import/history` for last import, the new `GET /extraction/runs` for
    last extraction, the same `graph_nodes`/`graph_edges` fields already
    in `/import/metrics` for graph status, and "Connected" once every
    other panel's fetch succeeds for database status — no separate
    health-check endpoint was added). Quick Actions: four buttons that
    just call `navigate()` to Knowledge (where the import panel lives),
    Explorer, Knowledge Graph, and Advisor (where Search Knowledge lives)
    — no new pages behind them. Loading/empty/error states throughout,
    matching the pattern already established by the Explorer and
    Knowledge Graph pages. Zero new CSS — every element reuses existing
    classes.
  - 17 new tests: `dashboard/tests/test_extraction_dashboard_endpoints.py`
    (ordering, limit, empty state for the two new endpoints),
    `test_dashboard_ui.py` (nav/route/metrics-mapping/quick-actions/
    empty-state/error-state regression checks, plus a check that Home and
    every other existing page's render function is still present
    unchanged). 400/400 passing repo-wide.

- Sprint 6: Advisor Search — keyword/partial-match search over imported
  conversations and extracted knowledge objects, surfaced as a new
  "Search Knowledge" section on the existing Advisor page. **Additive
  only**: two new files inside the existing `app/advisor/` package, a
  new router, a new UI section — every Epic 2 recommendation-engine file
  (`db.py`, `engine.py`, `rules/`, `scoring.py`, `narrative.py`,
  `routers/advisor.py`) and every existing `/advisor/*` route is
  byte-for-byte untouched.
  - New `dashboard/app/advisor/search.py` (`search(q, result_type, limit)`:
    unifies two existing, already-tested search paths — `app.imports.db
    .list_conversations_page(q=...)` for conversation matches (title,
    message content, source, id) and a new `app.extraction.db
    .search_objects(q=..., object_type=...)` helper for extracted-object
    matches — into one result list sorted by date. `get_object_result()`/
    `get_conversation_result()` back the two lookup endpoints. New
    `dashboard/app/advisor/search_models.py` (`SearchResult`,
    `SearchResponse` — `object_type`, `name`, `conversation_id`,
    `conversation_title`, `date`, `confidence` (`null` for conversations),
    `graph_node_id`).
  - New API on `/advisor/search`, registered via a **separate router**
    (`dashboard/app/routers/advisor_search.py`) from Epic 2's
    `routers/advisor.py`, so this sprint carries zero risk to the
    existing router: `GET /advisor/search?q=&type=&limit=`,
    `GET /advisor/search/objects/{id}`, `GET
    /advisor/search/conversations/{id}`. `type` must be one of
    `Conversation`/`Project`/`Person`/`Task`/`Decision`/`Idea`/`Document`/
    `Asset` or the request 400s. `graph_node_id` in every result matches
    the Sprint 5 Knowledge Graph's node id format exactly
    (`GET /conversation-graph/nodes/{id}`), so "Open Graph" needs no
    translation.
  - Advisor page (`dashboard/app/static/js/app.js`): a new "Search
    Knowledge" section at the top (search box, live/debounced ~250ms;
    type-filter `<select>`; Clear button; scrollable result list with
    *Open Conversation* / *Open Graph* actions per result) inserted above
    the existing Daily Brief/recommendations UI, which is otherwise
    unchanged. *Open Conversation* reuses the same
    `pendingExplorerConversationFocus` handoff the Knowledge Graph page
    introduced in Sprint 5; *Open Graph* navigates to
    `#/conversation-graph/{conversation_id}`. One new CSS rule
    (`.advisor-search-results { max-height: 420px; overflow-y: auto; }`
    in `components.css`) for the scrollable results container — no other
    new styling, everything else reuses existing card/badge/button
    classes.
  - 35 new tests: `dashboard/tests/test_advisor_search.py` (keyword
    search, partial matching, "show all X", type filters, result shape,
    conversation/object lookup), `test_advisor_search_api.py` (full API
    surface, invalid-type 400, a search result's `graph_node_id`
    resolving against `/conversation-graph/nodes/{id}`, and a regression
    check that `/advisor/recommendations`/`/advisor/daily-brief` are
    unaffected), `test_advisor_search_ui.py` (nav/route/cross-link
    regression checks). 383/383 passing repo-wide.

- Sprint 5: Knowledge Graph — a second, independent graph visualizing
  imported conversations connected to the knowledge objects extracted
  from them. **Additive only**: new domain, new API namespace, new UI
  page; extends (does not replace) the Explorer's conversation detail
  view and `GET /import/metrics`. Deliberately kept separate from the
  Epic 3 Knowledge Graph rather than merged into it — see below and
  [[DECISIONS]] for why.
  - New `dashboard/app/conversation_graph/` package: `models.py` (`Node`/
    `Edge`/`Graph`, 8 lowercase node types — `conversation`, `project`,
    `person`, `task`, `decision`, `idea`, `document`, `asset` — and
    exactly one relationship type, `contains`; edges deduplicated by
    `(source, target, type)`, edges referencing a missing node silently
    dropped), `engine.py` (`build_graph()`: one node per imported
    conversation + one node per extracted object + a `contains` edge from
    each conversation to every object extracted from it, computed fresh
    from the imports/extraction databases on every call — no new
    persisted store). One additive helper added to the frozen Sprint 4
    extraction module: `app.extraction.db.list_all_objects()` (read-only,
    used only by the graph engine).
  - New API on `/conversation-graph`: `GET /conversation-graph?conversation_id=&node_type=`
    (structured `{nodes, edges, metrics}` response), `GET
    /conversation-graph/nodes/{id}`, `GET
    /conversation-graph/nodes/{id}/neighbors`.
  - Why a second graph instead of extending Epic 3's `/graph`:
    `dashboard/tests/test_graph_api.py` hard-asserts exactly 12 node
    types / 12 relationship types via `/graph/meta/types`, and three
    architecture docs document that "12/12" as fixed. This sprint's types
    (`task`, `idea`, `document`, `contains`) aren't in that vocabulary,
    and this sprint's same-named types (`conversation`, `person`,
    `project`, `decision`, `asset`) come from an entirely different
    pipeline (imports/extraction, not Builder/PI/Advisor) — merging risked
    both breaking a passing test and silent node-id collisions across two
    unrelated data sources. A second, small, independent graph avoids
    both, at the cost of not being one unified graph.
  - New **Knowledge Graph** page: sidebar nav item + `#/conversation-graph`
    route (`dashboard/app/templates/index.html`,
    `dashboard/app/static/js/app.js`). Reuses the existing
    `createGraphView()` SVG zoom/pan/reset engine and
    `.graph-page`/`.graph-toolbar`/`.graph-detail-panel` CSS as-is; only
    new CSS is 3 additional node colors (`--node-task`, `--node-idea`,
    `--node-document` in `colors.css`) and a small `#kg-loading-msg`/
    `#kg-empty-msg` overlay-centering rule in `layout.css`, scoped to this
    page's own ids so the Epic 3 Graph page's markup/CSS is untouched.
    Filters: conversation, node type, Clear filters — exactly the two
    filters in scope. Two-way navigation with the Conversation Explorer:
    a "View in Knowledge Graph" button in the conversation detail overlay,
    and an "Open in Conversation Explorer" action in the graph's node
    detail panel.
  - `GET /import/metrics` (Explorer dashboard metrics) gains
    `graph_nodes`/`graph_edges`, real counts from `build_graph()`.
  - 32 new tests: `dashboard/tests/test_conversation_graph_engine.py`
    (node/edge validation, dedup, full graph construction, empty/
    orphaned/incomplete data), `test_conversation_graph_api.py` (full API
    surface, filters, node detail, neighbors, dashboard metrics),
    `test_conversation_graph_ui.py` (nav/route/cross-link regression
    checks, same string-assertion style as `test_ui.py`). 348/348 passing
    repo-wide.

- Sprint 4: Knowledge Extraction — deterministic, rule-based extraction of
  structured objects from imported conversations. **Additive only**: new
  domain, new database, new API namespace; extends (does not replace) the
  Explorer's conversation detail view and `GET /import/metrics`.
  - New `dashboard/app/extraction/` package: `rules.py` (pattern-based
    extractors for exactly seven object types — Project, Person, Task,
    Decision, Idea, Document, Asset — regex/keyword-line matching only, no
    AI/LLM call, styled after `builder/extractors/` but self-contained,
    not imported from it), `db.py` (owns its own SQLite file,
    `role_os_extraction.db`, with `extracted_objects` and
    `extraction_runs` tables, schema auto-created on first use), and
    `service.py` (`run_extraction()`: read a conversation from the
    imports domain -> run every extractor -> deduplicate -> persist ->
    report).
  - Deduplication mirrors the importer's own fingerprint strategy, scoped
    per-conversation: `sha256(conversation_id | object_type | normalized_title)`.
    Re-running extraction never duplicates — new candidates are inserted
    (`created`), changed ones updated in place (`updated`), unchanged ones
    just get `updated_at` bumped (`unchanged`). Objects removed via
    `DELETE /extraction/objects/{id}` are never silently recreated except
    by an explicit re-run finding the same match again.
  - New API on `/extraction`: `POST /extraction/conversations/{id}/run`
    (run/re-run, same idempotent endpoint), `GET
    /extraction/conversations/{id}/objects?object_type=`, `DELETE
    /extraction/objects/{object_id}`, `GET /extraction/metrics`.
  - `GET /import/metrics` (Sprint B1.5) now reads real counts from the
    extraction domain for `knowledge_objects` and all seven per-type
    fields (`projects`, `people`, `tasks`, `decisions`, `ideas`,
    `documents`, `assets` — the last two are new response fields);
    `pending_processing`/`processed` remain `0` (no per-conversation
    processing-state tracking yet, out of scope for this sprint).
  - Explorer conversation detail view (`dashboard/app/static/js/app.js`)
    gained a **Knowledge** section: an "Extract Knowledge" button and
    seven object-type lists (with confidence badge + per-object Delete),
    reusing existing `.activity-list`/`.badge`/`.link-btn`/`.page-section`
    styling — no new CSS classes were needed.
  - 32 new tests: `dashboard/tests/test_extraction_rules.py` (per-type
    extractor behavior), `test_extraction_service.py` (persistence, dedup,
    re-run, deletion+recreation), `test_extraction_api.py` (full API
    surface plus a regression check that `/import/*` and `/health` are
    unaffected). 316/316 passing repo-wide.

- Sprint B1.5: Conversation Explorer — browse, search, filter, inspect, and
  manage imported conversations. **Additive only**: extends Sprint B1's
  `/import/*` API and imports database; no existing endpoint, table, or UI
  page changed behavior.
  - `dashboard/app/imports/db.py`: two-column migration on the existing
    `imported_conversations` table (`status`, `import_run_id`), applied via
    idempotent `ALTER TABLE` wrapped in a duplicate-column guard so it's
    safe to run against a database created by Sprint B1 before this
    column existed. New `list_conversations_page()` (search/filter/sort/
    paginate, parameterized SQL), `get_conversation()` (full detail incl.
    content), `delete_conversation()`, `list_facets()`,
    `count_conversations()`. `service.run_import()` now generates the
    `import_run_id` up front and threads it through both
    `insert_conversation()`/`update_conversation()` and `record_run()` so
    every persisted conversation can be traced back to the run that
    produced its current state.
  - New API on the existing `/import` router: `GET /import/conversations`
    now accepts `page`/`page_size`/`sort_by`/`sort_dir`/`q`/`source`/
    `status`/`imported_after`/`imported_before` and returns a paginated
    envelope (`{items, total, page, page_size}`) instead of a bare list —
    the only contract change in this sprint, and one with no prior
    consumer (nothing was wired to the old shape yet). New
    `GET /import/conversations/{id}` (detail incl. content),
    `GET /import/conversations/{id}/export` (JSON file download),
    `DELETE /import/conversations/{id}`, `GET /import/facets` (distinct
    source/status values present, so filter dropdowns need no hard-coded
    provider list), `GET /import/metrics` (dashboard metrics — only
    `imported_conversations` is real; `pending_processing`, `processed`,
    `knowledge_objects`, `projects`, `decisions`, `assets` are `0` by
    design, since none of those pipelines exist yet).
  - New **Explorer** page: sidebar nav item + `#/explorer` route
    (`dashboard/app/templates/index.html`, `dashboard/app/static/js/app.js`).
    Reuses existing design-system pieces rather than introducing new ones
    where one already fit: the Home page's `health-dashboard-grid` +
    `animateCount()` for the metrics strip, the Graph page's
    `.graph-toolbar` for the filter bar, and the same shared
    `#detail-overlay`/`#detail-body` the Knowledge page's card detail
    already uses for the conversation detail view (message timeline with
    USER/ASSISTANT/SYSTEM color-coded via new minimal `.message-item`
    rules, search-within-conversation, metadata table, Copy/Export/Delete
    actions). New `.explorer-table`/`.explorer-pagination`/`.message-*`
    rules added to `components.css`, consistent with its existing
    per-feature section convention. Delete requires a native `confirm()`
    dialog.
  - 31 new tests: `dashboard/tests/test_explorer_api.py` (list/pagination/
    sort/search/filters/detail/export/delete/facets/metrics, all via
    `TestClient`) and `dashboard/tests/test_import_db.py` (pagination
    edge cases, sort-field whitelist fallback, migration idempotency).
    284/284 passing repo-wide.

- Sprint B1: ChatGPT Conversation Importer — a dashboard-owned pipeline for
  importing ChatGPT conversation exports without regenerating the whole
  Builder-generated knowledge base. **Additive only**: no existing
  endpoint, table, or UI behavior changed.
  - New `dashboard/app/imports/` package: `parser.py` (validates the
    export, normalizes each conversation — title, timestamps, message
    count, participant roles, content — ignoring individually malformed
    records without aborting the import), `db.py` (owns its own SQLite
    file, `role_os_imports.db`, with `imported_conversations` and
    `import_runs` tables, schema auto-created on first use, same pattern
    as Epic 1/2), `service.py` (`run_import()`: parse -> normalize ->
    deduplicate -> persist -> report; shared by both the API route and the
    CLI so they can't drift), `models.py` (pydantic schemas).
  - Deduplication: each conversation is fingerprinted by
    `id:<external_id>` when the export provides one, otherwise a
    deterministic `hash:<sha256>` of title/timestamps/content. Re-imports
    are classified `imported` / `updated` (content changed) / `skipped`
    (unchanged) / `invalid` (malformed record) — never silently
    duplicated.
  - New API: `POST /import/chatgpt` (multipart upload, returns a
    structured `ImportRun` summary), `GET /import/history`,
    `GET /import/conversations` — namespaced under `/import`, new
    `python-multipart` dependency for file upload support.
  - New CLI: `python scripts/import_chatgpt.py <path>`, following the
    `scripts/seed_alpha_demo.py` sys.path pattern, calling the same
    `run_import()` the API uses.
  - New UI: an "Import ChatGPT conversations" panel on the Knowledge page
    (file picker, Import button, loading state, success/error summary) —
    calls the existing `/import/chatgpt` endpoint only, no new backend
    surface introduced for it.
  - Explicitly out of scope for this sprint (by design): AI knowledge
    extraction, project/capability matching, Advisor recommendations, and
    Knowledge Graph linking for imported conversations — those remain the
    Builder's job.
  - 27 new tests across `dashboard/tests/test_import_parser.py`,
    `test_import_service.py`, `test_import_api.py`, and repo-level
    `tests/test_import_chatgpt_cli.py`; 253/253 passing repo-wide.

- Epic 4: ROLE OS Command Center — a full UX/UI redesign of the
  dashboard. **UI-only**: no API, database, or backend logic was touched;
  every view is built entirely on the existing Milestone 1 knowledge API,
  Epic 1 `/pi/*`, Epic 2 `/advisor/*`, and Epic 3 `/graph/*` endpoints.
  - New reusable design system under `dashboard/app/static/css/`:
    `colors.css` (every color as a custom property, including a palette
    entry per Knowledge Graph node type), `layout.css` (the app shell
    grid, page containers, responsive breakpoints), `components.css`
    (nav items, buttons, cards, badges, the health ring, the search
    dropdown, the graph detail panel), and `animations.css` (subtle
    fade/rise-in, hover lift, and health-ring transitions, respecting
    `prefers-reduced-motion`). `style.css` is now a four-line `@import`
    entry point — no inline styles anywhere in the generated markup
    except the health ring's live score gradient and each graph node's
    live type color, which are inherently per-instance runtime values.
  - Replaced the Milestone 2/3 tab-based page with a single-page Command
    Center shell: a persistent icon sidebar (Home, Projects, Knowledge,
    Advisor, Graph, Assets, Settings) and a header (global search,
    workspace selector, live date/time, quick actions), with a small
    hash-based client-side router (`#/home`, `#/projects`,
    `#/project/{id}`, `#/knowledge`, `#/advisor`, `#/graph`, `#/assets`,
    `#/settings`) swapping pages in and out of one `#view-root` — no new
    server route was added for any of these pages.
  - **Home**: Today's Focus (top 3 Advisor recommendations with project,
    health ring, priority, estimated effort, expected impact, suggested
    action, and an Open Project button), Workspace Overview (a card per
    workspace with healthy/warning/critical project counts), an animated
    Health Dashboard (Projects, Knowledge Cards, Advisor Recommendations,
    Graph Nodes, Graph Relationships, each counting up on load), Recent
    Activity (timeline, recent decisions, recent deliverables, recent
    conversations), a Knowledge Graph Preview (a small non-interactive
    render of the Project subgraph that opens the full Graph page on
    click), and a Quick Search box whose results are grouped into
    Projects / Knowledge Cards / People / Applications / Vendors / Assets
    — all six of which map directly onto existing Knowledge Graph node
    types, so grouping is one `/graph/search` call away with no new
    endpoint required.
  - **Project page**: redesigned into a three-column layout — left
    (health ring, status, workspace, priority, Advisor summary), center
    (overview, notes, recent decisions, open to-dos, deliverables), right
    (capabilities provided/consumed, dependencies both directions,
    related projects, the project's live Advisor recommendations, and a
    Knowledge Graph preview that jumps into the full Graph page focused
    on this project).
  - **Graph page**: promoted to a dedicated full-screen page with mouse
    wheel zoom and click-drag pan (via an SVG viewport transform) added
    on top of Epic 3's existing click / expand / collapse / search /
    filter-by-type-workspace-relationship / highlight-dependencies /
    highlight-capabilities interactions, plus a new impact-analysis
    action wired to `GET /graph/impact/{id}` with its own highlight
    color. The graph rendering code was refactored into a reusable
    `createGraphView()` factory so the same engine now powers the Home
    preview, the Project page preview, and the full Graph page.
  - **Advisor page**: Daily Brief at the top, recommendation cards
    grouped by workspace (each showing evidence, impact, estimated
    effort, and Dismiss/Mark completed actions) — the same
    `/advisor/daily-brief` and `/advisor/recommendations` endpoints as
    before.
  - **Assets** and **Settings** pages added to round out the sidebar:
    Assets lists every `Asset` graph node; Settings shows read-only
    system status from the existing `/health` endpoint.
  - Regression: `dashboard/tests/test_ui.py` and
    `test_advisor_api.py::test_dashboard_page_includes_advisor_tab` were
    updated to check for the new sidebar/router markup instead of the
    retired `data-tab="..."` panels (the old assertions were testing DOM
    structure the spec explicitly requires replacing, not backend
    behavior); every Builder, Knowledge, Project Intelligence, Advisor,
    and Knowledge Graph API test is unchanged and still passing. New
    tests confirm the sidebar, header, and all four design-system CSS
    files are served, and that app.js's router/views still call only the
    pre-existing API surface. 226/226 passing repo-wide.
  - Updated root `README.md` and `dashboard/README.md` with the Command
    Center UI description and a screenshots placeholder section.

- Epic 3: Knowledge Graph engine. ROLE OS gains a first-class,
  explainable relationship engine — not just a visualization — built on
  top of the existing Builder, Project Intelligence, and Advisor
  databases with **no data duplication**: the graph is recomputed from
  those three databases on every call, the same recompute-on-read pattern
  the Advisor (Epic 2) uses for recommendations.
  - New domain under `dashboard/app/graph/`:
    - `models.py` — dependency-free `Node`/`Edge`/`Graph` data structures.
      Exactly 12 node types (`Project`, `KnowledgeCard`, `Person`,
      `Application`, `Vendor`, `Capability`, `Workspace`, `Decision`,
      `Deliverable`, `Prompt`, `Asset`, `Conversation`) and exactly 12
      relationship types (`DEPENDS_ON`, `PROVIDES`, `USES`, `REFERENCES`,
      `RELATED_TO`, `BELONGS_TO`, `CREATED_BY`, `MENTIONS`,
      `GENERATED_FROM`, `UNBLOCKS`, `IMPLEMENTS`, `SHARES_CAPABILITY`).
    - `builders/` — one file per relationship family, each a pure
      `build(...) -> (nodes, edges)` function: `project_graph.py`
      (Projects, Workspaces, and a project's own Decisions/Deliverables/
      Prompts/Assets), `dependency_graph.py` (`DEPENDS_ON` + the
      precomputed reverse `UNBLOCKS`), `capability_graph.py`
      (`IMPLEMENTS`/`USES`/`SHARES_CAPABILITY`), `knowledge_graph.py`
      (KnowledgeCard/Conversation nodes, `GENERATED_FROM`, `RELATED_TO`
      via Milestone 3's `related_conversations`, `BELONGS_TO` a linked
      Project), `people_graph.py`, `application_graph.py`, and
      `vendor_graph.py` (Person/Application/Vendor nodes deduplicated by
      slugified name, `MENTIONS`, aggregated `USES`, and a deterministic
      co-occurrence-based `PROVIDES` from Vendor to Application).
    - `engine.py`: `build_graph()` reads the Builder DB
      (`app.db.list_all_cards`, a new internal-only function — no new
      public API endpoint), the Project Intelligence DB, and the Advisor
      DB, runs every builder, and merges the results into one `Graph`
      (all nodes added before any edges, so cross-builder edges are never
      dropped for referencing a node contributed by a different builder).
    - `queries.py`: the Query Engine — `neighbors()` (filterable BFS),
      `shortest_path()` (unweighted BFS pathfinding), `impact_analysis()`
      (cascading traversal grouped by node type, e.g. "if ROLE MASTER
      changes → which Projects/Assets/Conversations/Capabilities are
      affected, and which Advisor recommendations exist for them"),
      `search_nodes()`, and named convenience wrappers matching the Epic's
      example questions (`projects_related_to`, `capabilities_used_by`,
      `applications_connected_to`, `conversations_mentioning`,
      `people_involved_in`, `projects_blocked_by`,
      `projects_unlocked_by_finishing`). All pure functions over an
      already-built `Graph` — no I/O beyond an optional Advisor lookup, so
      any future AI provider can reason over the graph headlessly.
  - New Graph API, entirely additive and namespaced under `/graph`:
    `GET /graph` (optionally filtered by node_type/workspace),
    `GET /graph/project/{id}`, `GET /graph/node/{id}`,
    `GET /graph/neighbors/{id}` (direction/edge_type/node_type/depth
    filters), `GET /graph/path` (shortest path between two nodes),
    `GET /graph/impact/{id}` (impact analysis), `GET /graph/search`, and
    `GET /graph/meta/types` (the fixed node/relationship vocabularies, for
    the dashboard's filter dropdowns).
  - Dashboard UI: a new "Knowledge Graph" tab (plain HTML/CSS/JS, no
    frontend framework, no CDN dependency) with a hand-rolled SVG graph
    view, a click-to-open detail panel, expand/collapse neighbors, search,
    filters by node type/workspace/relationship, and highlight toggles for
    the shortest path, dependencies, and capabilities. The visualization
    is entirely optional presentation over the standalone `/graph/*` API —
    the Graph Engine works completely independently of it.
  - The four Milestone 1 API endpoints, the Milestone 2 UI, and the full
    Epic 1 `/pi/*` and Epic 2 `/advisor/*` APIs and UI are completely
    unchanged; only new, additive endpoints and UI elements were
    introduced.
  - 48 new tests: unit tests for the `Node`/`Edge`/`Graph` primitives and
    every builder, integration tests for `build_graph()` against real
    Project Intelligence and knowledge databases (including graceful
    degradation when the knowledge DB is missing), traversal/pathfinding/
    impact-analysis tests, API tests for every `/graph/*` endpoint, and
    dashboard/regression tests confirming every previous API and UI
    surface is unaffected. 225/225 passing repo-wide.
  - Updated `dashboard/README.md` and root `README.md` documenting node
    types, relationship types, graph generation, and impact analysis.

- Epic 2: explainable AI Advisor. ROLE OS analyzes Projects, Knowledge
  Cards, Capabilities, Dependencies, Health Scores, TODOs, Deliverables,
  and Decisions to recommend what to do next — deterministic by default,
  fully explainable, and requiring no external AI API.
  - New domain under `dashboard/app/advisor/`:
    - Eight independent, single-responsibility rules under `rules/`:
      `stale_project`, `near_completion`, `blocked_dependency`,
      `critical_health`, `overdue_todos`, `missing_deliverables`,
      `inactive_high_priority`, `capability_opportunity`. Each is a pure
      function `evaluate(project, context) -> list[RecommendationCandidate]`.
      `critical_health` dynamically picks `review_risk` or
      `review_decision` depending on which Health Score signal is weakest.
    - `scoring.py`: a shared, deterministic toolkit (priority weighting,
      staleness, completion ratio, confidence-from-availability,
      weighted-signal-combination with graceful renormalization over
      missing signals) used by every rule. No randomness anywhere.
    - `engine.py`: orchestrates all eight rules across every Project,
      refreshing each project's Health Score first so cross-project checks
      (e.g. `blocked_dependency`) always use current data; merges
      same-key candidates (even from two different rules) before
      persisting, so duplicates never reach the database.
    - `narrative.py`: `AdvisorNarrativeProvider` interface (AI-ready seam
      for a future LLM-backed implementation) plus
      `DeterministicNarrativeProvider`, the only implementation used in
      this Epic — builds every string from the rule engine's own
      structured output, no network calls, fully reproducible.
    - `db.py`: recommendations persisted in their own SQLite database
      (`ROLE_OS_ADVISOR_DB_PATH`), separate from both the knowledge DB and
      the Project Intelligence DB, which the Advisor only ever reads.
      Deduplicated by `(project_id, recommendation_type)`: a new row is
      only inserted if none is still "live" (unexpired); dismissed and
      completed rows keep their state forever and continue to suppress
      regeneration until they expire, at which point a fresh
      recommendation may be generated if the condition still holds.
  - Every `Recommendation` includes: `id`, `project_id`, `workspace`,
    `title`, `summary`, `recommendation_type`, `priority_score`,
    `confidence_score`, `reason`, `evidence`, `suggested_action`,
    `estimated_effort`, `impact`, `created_at`, `expires_at`, `dismissed`,
    `completed` — the `reason`/`evidence`/`impact` fields make every
    recommendation self-explaining.
  - New Advisor API, entirely additive and namespaced under `/advisor`:
    `GET /advisor/recommendations` (filterable by workspace, project_id,
    recommendation_type, minimum_priority_score, include_dismissed),
    `GET /advisor/recommendations/{id}`, `GET /advisor/daily-brief`,
    `POST /advisor/recommendations/{id}/dismiss`,
    `POST /advisor/recommendations/{id}/complete`.
  - Daily Brief: top 3 recommended projects, critical risks, blocked
    projects, near-completion projects, stale high-priority projects, and
    capability reuse opportunities, each with a short explanation.
  - Dashboard UI: a new "Advisor" tab (plain HTML/CSS/JS, no framework)
    with a workspace filter, the Daily Brief, and recommendation cards
    showing priority, estimated effort, impact, full evidence/explanation,
    and Dismiss/Mark completed buttons.
  - The four Milestone 1 API endpoints, the Milestone 2 UI, and the full
    Epic 1 `/pi/*` API and UI are completely unchanged; only new, additive
    endpoints and UI elements were introduced.
  - 65 new tests: unit tests for every rule and every scoring function,
    persistence/duplicate-prevention tests, engine-level tests (including
    cross-rule dedup and Daily Brief structure), API tests for every
    `/advisor/*` endpoint, and a regression test confirming every previous
    API and UI surface is unaffected. 177/177 passing repo-wide.
  - Updated `dashboard/README.md` and root `README.md` explaining rule
    generation, scoring, explainability, and the AI-ready narrative
    provider seam.

- Epic 1: Project Intelligence layer. ROLE OS gains first-class Projects,
  Workspaces, Capabilities, Dependencies, and a modular Health Score engine.
  - New domain model under `dashboard/app/projects/`:
    - `db.py` — dashboard-owned SQLite persistence (separate database file,
      `ROLE_OS_PROJECTS_DB_PATH`, from the builder-generated knowledge DB),
      with automatic idempotent schema creation and default-workspace
      seeding (`Personal`, `Kontoor`, `Unger`, `Products`, `Ideas`,
      `Library`) on first use.
    - Every Project has: `id`, `workspace`, `name`, `description`, `status`,
      `health_score`, `priority`, `tags`, `owner`, `created_at`,
      `updated_at`, and collections: `notes`, `decisions`, `todos`,
      `deliverables`, `assets`, `prompts`, `conversations` (linked
      knowledge-base conversation ids), `related_projects`, `capabilities`,
      and `dependencies`.
    - Capabilities: a project may expose reusable capabilities that other
      projects can consume (e.g. `ROLE Master` exposing "Brand Identity",
      consumed by `SUPER FACIL`).
    - Dependencies: projects may depend on one another, fully queryable in
      both directions (`/pi/projects/{id}/dependencies` and
      `/pi/projects/{id}/dependents`).
  - New modular Health Score engine under
    `dashboard/app/projects/health/`: one independent, pure-function signal
    per file (`activity.py`, `todos.py`, `decisions.py`, `deliverables.py`,
    `conversations.py`, `commits.py`), combined by `__init__.py` into a
    weighted 0-100 score that gracefully renormalizes when a signal (e.g.
    commits, with no git integration yet) is unavailable.
  - New Project Intelligence API, entirely additive and namespaced under
    `/pi` to avoid any collision with the existing `/projects` endpoint:
    workspaces, projects (CRUD + filtering), the six collection types,
    conversation/related-project links, capabilities (expose/consume/list),
    dependencies (add/remove/list/reverse-lookup), and health score
    (recompute + persist, single project or bulk).
  - Dashboard UI: a new "Projects" tab alongside the existing "Knowledge"
    tab (plain HTML/CSS/JS, no framework) with a workspace selector, a
    project list with color-coded Health Score indicators, and a project
    detail page showing the health breakdown, capability section
    (provided/consumed), dependency section (depends on/dependents), and
    all collections.
  - The four Milestone 1 API endpoints and the Milestone 2 UI are
    completely unchanged; only new, additive endpoints and UI elements
    were introduced.
  - 61 new tests (unit tests for every health signal and every `db.py`
    function; integration tests for every new `/pi/*` endpoint; a UI test
    for the new Projects tab), for 103/103 passing repo-wide.
  - Updated `dashboard/README.md` and root `README.md`.

- Milestone 3: Knowledge Engine 2.0 — a modular knowledge extraction
  pipeline under `builder/extractors/` that enriches every Knowledge Card.
  - New extractors, one responsibility each: `summary.py`, `decisions.py`
    (decisions + deliverables), `todos.py`, `prompts.py`, `entities.py`
    (people, applications, vendors, urls, files, project/tag
    classification), `relationships.py` (related conversations).
  - `extractors/__init__.py` defines the extended `KnowledgeCard` and
    `build_knowledge_card()`, which merges every extractor's output into
    one card.
  - New fields on every Knowledge Card: real `vendors` extraction
    (previously always empty), `files` (previously only exposed via the
    `assets` alias, which is kept for backward compatibility), and
    `related_conversations` — computed in a second, corpus-level pass
    (`attach_related_conversations`) via weighted overlap of project, tags,
    people, and applications across all cards.
  - New `VENDORS.json` cross-reference index alongside the existing
    PROJECTS/PEOPLE/APPLICATIONS/TAGS/TIMELINE indexes.
  - `builder.py`'s SQLite write (`role_os.db`) now happens after the
    relationship pass, so `related_conversations` and real `vendors` are
    persisted automatically.
  - `knowledge_extractor.py` is now a thin backward-compatible wrapper
    (`build_card`) around `extractors.build_knowledge_card` — the builder
    CLI, its arguments, and its output folder layout are unchanged.
  - No dashboard changes were required: the existing `/knowledge/{id}`
    endpoint already passes new fields through (`extra="allow"`).
  - New regression tests under `builder/tests/`: per-extractor unit tests,
    pipeline tests (including a backward-compatibility check that
    `knowledge_extractor.build_card` matches `extractors.build_knowledge_card`),
    and an end-to-end integration test asserting enriched output and
    updated SQLite.
  - Regenerated `samples/role_os_sample` with the new pipeline.

- Milestone 2: first usable ROLE OS web dashboard, served directly by the
  existing FastAPI app at `/`. Built with plain HTML, CSS, and JavaScript —
  no frontend framework.
  - Global search bar (uses the existing `GET /search?q=` endpoint).
  - Project list with conversation counts (uses the existing `GET /projects`
    endpoint); clicking a project filters the card list.
  - Recent knowledge cards list (new additive `GET /ui/recent` endpoint).
  - Knowledge card detail view/modal showing summary, decisions,
    deliverables, to-dos, people, applications, and tags (uses the existing
    `GET /knowledge/{id}` endpoint).
  - Basic chronological timeline (new additive `GET /ui/timeline` endpoint).
  - The four Milestone 1 API endpoints (`/health`, `/projects`, `/search`,
    `/knowledge/{id}`) are unchanged; `/ui/recent` and `/ui/timeline` are
    additive, UI-only endpoints and do not alter existing API contracts.
  - UI tests (`dashboard/tests/test_ui.py`) covering page rendering, static
    asset serving, the new `/ui/*` endpoints, and a regression check that
    the original API responses are unaffected.

- Repository project structure: `/builder`, `/dashboard`, `/docs`, `/tests`,
  `/scripts`, `/samples`.
- Migrated the existing ROLE OS Builder (`builder.py`,
  `knowledge_extractor.py`, `run_windows.bat`) into `/builder`, unchanged
  functionally, with an updated README and `requirements.txt`.
- New FastAPI dashboard application under `/dashboard` exposing:
  - `GET /health`
  - `GET /projects`
  - `GET /search?q=`
  - `GET /knowledge/{id}`
  Backed by the SQLite database produced by the builder. No AI features.
- Sample ChatGPT export and generated ROLE Knowledge OS output under
  `/samples` for local smoke-testing.
- Repo-level and dashboard-level test suites (pytest).
- Root `README.md`, `pyproject.toml`, and `.gitignore` additions.
