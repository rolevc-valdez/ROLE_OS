# 11 — Discovery Engine Domain Model

Status: **DOCUMENTATION ONLY — defines vocabulary and boundaries, commits
to no schema, no API, no algorithm.** Written after Sprint 1 (read-only
audit engine) and Sprint 1.5 (detector-registry/rule-engine hardening),
before any persistence, identity resolution, or API work begins.

Purpose: give Sprint 2+ one authoritative vocabulary to build against, so
"Project" doesn't quietly mean three different things across `projects/`,
`discovery/`, and whatever ships next. Every concept below is cross-checked
against what `dashboard/app/discovery/` actually does today (Sprint
1/1.5), not aspirational behavior — where this model describes something
that doesn't exist in code yet, it says so.

---

## 0. Executive Summary

ROLE OS today has exactly one durable notion of "a project": the
**Managed Project** (`app/projects`, Epic 1) — a hand-curated database row
with notes, decisions, priority, and a health score, entirely independent
of whether any folder on disk backs it.

The Discovery Engine (Sprint 1/1.5) introduced a second, entirely
*computed, in-memory, never-persisted* notion: the **Discovered Project**
— what a read-only filesystem walk plus a rule-based classifier concludes
about one folder, right now, this scan.

These are deliberately not the same thing, and this document's central
job is to keep them that way as persistence gets added. A Discovered
Project is evidence. A Managed Project is a decision a human (or, later,
a human-approved automation) made. Sprint 2+ is the bridge between them —
**Identity Resolution** proposes links, **Human Confirmation** approves
them, and only after confirmation does discovered data get to influence a
Managed Project, and even then only by filling gaps, never by overwriting
something a human already typed.

Everything else in this document — Scan Runs, Findings, Health Signals,
Recommendations, Project Families, the future Workspace Graph — exists to
make that one bridge trustworthy: explainable, reversible, and never
silently destructive.

---

## 1. Concept Inventory

Each entry: definition, purpose, attributes, lifecycle, ownership,
relationships, persistence expectation, API exposure, provenance kind, and
a real example where one exists (drawn from `09_DISCOVERY_ENGINE_
SPRINT1_REPORT.md`'s actual runs against `Documents` and
`1 - IA PROJECTS`).

### 1.1 Workspace

**Definition**: An existing Project Intelligence concept (`app/projects`,
Epic 1) — a named grouping of Managed Projects (`Personal`, `Kontoor`,
`Unger`, `Products`, `Ideas`, `Library` are the seeded defaults). **Not a
new Discovery concept** — see §2.1 for why Discovery reuses this rather
than inventing a second "workspace."

**Purpose**: The organizing unit a human thinks in ("which of my six
buckets does this belong to?"), independent of where anything lives on
disk.

**Required attributes**: `id`, `name` (unique).
**Optional attributes**: `description`.

**Lifecycle**: Created manually or auto-seeded; effectively permanent
(no delete path exists today). Not scan-driven.

**Ownership**: `app/projects/db.py`, `role_os_projects.db`.

**Relationships**: Has many Managed Projects. A Discovered Project has no
Workspace until/unless it becomes linked to a Managed Project (see §1.6).

**Persistence**: Durable, existing SQLite table (`workspaces`).

**API**: Public today (`GET /pi/workspaces` family). Unaffected by
Discovery.

**Provenance kind**: User-created/manually curated.

**Example**: `Products` workspace containing the `role-content-factory`
Managed Project (once one exists for it).

---

### 1.2 Discovery Root

**Definition**: A filesystem path the Discovery Engine is pointed at for
scanning — e.g. `C:\Users\rolev\Documents` or
`C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS`. Today: a raw
string/`Path` argument (`--root` on the CLI, `Settings.discovery_root` if
configured); **not yet a persisted, identified entity**.

**Purpose**: Names *where* discovery looks, as a stable reference a Scan
Run can be attributed to, independent of any one run's results.

**Required attributes**: normalized absolute path.
**Optional attributes**: a human label (e.g. "Documents", "IA Projects"),
an exclusion list (proposal §4.4's `OTROS - no proyectos` case),
`max_depth` default.

**Lifecycle**: Registered (first time a path is scanned) → Active → (future)
Archived/Retired if the folder is deleted or superseded. No transitions
exist in code today — every CLI invocation treats `--root` as ephemeral.

**Ownership**: Would be Discovery-owned if persisted (proposed
`discovery_roots` table, §5).

**Relationships**: Has many Scan Runs. Contains many Folder Candidates
(transitively, via scanning).

**Persistence**: **Not persisted today.** Proposed future table (§5).

**API**: Internal only until Sprint 2+; a future `POST /discovery/scans`
would reference one by path or id.

**Provenance kind**: User-declared (a human points Discovery at a root;
nothing infers this today).

**Example**: The two roots already exercised for real: `Documents` (29
folders, 2 real projects) and `1 - IA PROJECTS` (17 folders, ROLE OS's own
home).

---

### 1.3 Scan Run

**Definition**: One execution of the discovery pipeline against one
Discovery Root at one point in time. Today: represented in-memory only,
as a `ScanResult` (`app/discovery/models.py`) — `root`, `scanned_at`,
`duration_seconds`, `projects`, `skipped_paths`, `errors`, `max_depth`.

**Purpose**: The unit of "what did we find, when, how long did it take,
what went wrong" — the operational/audit record of one invocation.

**Required attributes**: id (future), discovery_root reference, started_at,
status (see §4.2's lifecycle), max_depth.
**Optional attributes**: completed_at, duration_seconds, error summary,
triggered_by (CLI/API/schedule, once more than one exists).

**Lifecycle**: See §4.2.

**Ownership**: Discovery-owned (future `discovery_runs` table, §5).

**Relationships**: Belongs to one Discovery Root. Produces many Folder
Candidates → Discovered Projects (one set per run). A Scan Run's result
set, once persisted, becomes the newest Discovery Snapshot (§1.23) for
each Discovered Project it touched.

**Persistence**: **Not persisted today** — `ScanResult` is a return value,
discarded after the CLI prints/writes it. Proposed durable in Sprint 2+.

**API**: `POST /discovery/scans` would create one; `GET /discovery/scans/{id}`
would read one back (both proposed, not designed here — see §7).

**Provenance kind**: System-generated event (not user-authored data).

**Example**: The real run against `Documents`: 29 folders, 0.9s, 3 skipped
paths (`My Music`/`My Pictures`/`My Videos`, permission-denied), 0 errors.

---

### 1.4 Folder Candidate

**Definition**: A folder the scanner (`scanner.discover_candidates`)
decided is *worth analyzing* — either a depth-1 folder under the root
(always included) or a depth-2+ folder that showed a minimal project
signal (`.git`, a marker file, or a README). Today: `scanner.Candidate`
(`path`, `depth`, `parent_path`).

**Purpose**: The pre-analysis admission gate — separates "worth spending
a full detector pass on" from "not even looking at this."

**Required attributes**: path, depth, parent_path (nullable).
**Optional attributes**: none today.

**Lifecycle**: Created by the scanner → consumed once by `analyze_folder`
→ discarded (becomes a Discovered Project's `root_path`/`depth`/
`parent_path`, or is dropped if analysis fails). Ephemeral, in-memory,
never independently persisted — see §2.2 for why this is a distinct
concept from Discovered Project even though it's short-lived.

**Ownership**: Discovery, transient.

**Relationships**: Produced by one Discovery Root/Scan Run. Becomes
exactly one Discovered Project (analysis always runs, even if the result
is low-confidence) — **a Folder Candidate is never itself persisted**;
only its outcome (the Discovered Project) is.

**Persistence**: Never persisted on its own.

**API**: Never exposed directly.

**Provenance kind**: Derived (computed by the scanner's admission rules).

**Example**: `packages/app-a` inside a `monorepo-container` folder that
has no markers of its own — admitted as a depth-2 candidate because
`app-a` has a `package.json`.

---

### 1.5 Discovered Project

**Definition**: The full output of running every detector, the
classifier, health scoring, and the recommendation engine against one
Folder Candidate. Today: `DiscoveredProject` (`app/discovery/models.py`)
— the ~50-field dataclass that is the Discovery Engine's actual product.

**Purpose**: "Here is everything the filesystem and git history can tell
us about this folder, right now" — evidence, not a decision.

**Required attributes**: `root_path`, `name`, `depth`, `classification`,
`confidence_score`, `move_risk`, `maturity`, `commercial_readiness`,
`health_score`, `recommendation`, `stage` (`PipelineStage`).
**Optional attributes**: everything detector-populated (git info, doc/
tech/test/asset signals, absolute-path findings) — optional in the sense
that a detector may find nothing, not that the field is absent.

**Lifecycle**: `NEW → DETECTED → CLASSIFIED → SCORED → RECOMMENDED`
(`PipelineStage`, enforced by `pipeline.require_stage`) — see §4.4.

**Ownership**: Discovery, currently in-memory only for the duration of
one Scan Run.

**Relationships**: Produced from exactly one Folder Candidate. May later
be linked (via an Identity Candidate → Human Confirmation) to zero or one
Managed Project. Contains, conceptually, one or more Technology Signals,
Structural Signals, a Risk Finding, a Health Signal breakdown, and exactly
one winning Recommendation — **today these are all flattened into
`DiscoveredProject`'s own fields rather than being separate persisted
records; §2.9 and §5 discuss splitting them out.**

**Persistence**: **Not persisted today.** Proposed `discovered_candidates`/
`discovered_projects` (§5) once Sprint 2 lands.

**API**: `GET /discovery/scans/{id}/candidates` would list these
(proposed, not designed — see §7). **Must never be returned as the raw
dataclass** — see the API-boundary invariant in §3.

**Provenance kind**: Fully derived/discovered — no human input.

**Example**: `role-content-factory` (Documents root): classification
`Mixed Project`, confidence `1.00`, maturity `mature`, commercial
readiness `client-ready`, health score `85`, recommendation
`Move into IA PROJECTS`.

---

### 1.6 Managed Project

**Definition**: The existing Project Intelligence concept (`app/projects`,
Epic 1) — a hand-curated database row (`id`, `workspace_id`, `name`,
`description`, `status`, `health_score`, `priority`, `tags`, `owner`,
`notes`, `decisions`, `todos`, `deliverables`, `assets`, `prompts`,
`conversations`, `related_projects`). **This document introduces the term
"Managed Project" as documentation vocabulary only** — the table stays
named `projects`, the API stays `/pi/projects`; "Managed Project" exists
so this document (and future ones) can say "Managed" vs "Discovered"
without ambiguity. See §2.3 for the full distinction.

**Purpose**: The thing a human actually manages day to day: priority,
notes, decisions, AI sessions, health score, Advisor recommendations.

**Required/optional attributes**: unchanged — see `app/projects/models.py`.

**Lifecycle**: Unchanged — manual CRUD via `/pi/projects`, plus (proposed,
Sprint 3+) a `root_path`/`discovery_source`/`last_scanned_at` extension
once Identity Resolution can link one to a Discovered Project.

**Ownership**: `app/projects`, `role_os_projects.db`. Unaffected by
Discovery until a human explicitly confirms a link.

**Relationships**: Belongs to one Workspace. May (future) be linked to one
Discovered Project's lineage via a confirmed Identity Candidate. Already
has a `related_projects` field (Epic 1) — prior art that Project
Relationship (§1.21) should reconcile with, not duplicate.

**Persistence**: Durable, existing.

**API**: Public today, unaffected.

**Provenance kind**: User-authored (manually created), or — once Sprint 3+
identity resolution ships — user-authored *and* discovery-linked.

**Example**: None yet — no Managed Project in this ROLE OS instance
currently has a `root_path` set, because that column doesn't exist yet
(proposal §14, not implemented).

---

### 1.7 Repository

**Definition**: A `.git` working tree found under a folder, with its own
identity (remote URL, branch, commit history) independent of the folder's
classification. Today: represented only as `GitInfo`, a field *on*
`DiscoveredProject`, not a standalone entity — i.e., today's model assumes
exactly zero-or-one Repository per Discovered Project.

**Purpose**: Captures git-specific evidence (branch, last commit, dirty
state, remote) separately from folder-structure evidence, since a folder
can be a real project without git (early prototype) or contain more than
one repository (a folder holding several unrelated cloned repos).

**Required attributes** (as `GitInfo` today): `is_repo`.
**Optional attributes**: `branch`, `remote_url`, `last_commit_hash`,
`last_commit_date`, `last_commit_message`, `commit_count`, `is_dirty`,
`error`.

**Lifecycle**: Read fresh on every Scan Run via read-only `git`
subcommands (`git_reader.read_git_info`); never cached, never mutated.

**Ownership**: Discovery (read-only), reading a filesystem-owned `.git`
directory.

**Relationships**: Today, 1:1 with a Discovered Project (assumed). The
proposal's own §20 Definition-of-Done anticipates "one project containing
multiple repositories" (§6.5's example) as a real case this 1:1 assumption
doesn't cover — flagged as an open gap, not solved here.

**Persistence**: **Not persisted today.** Proposed `discovered_repositories`
(§5), decoupled from `discovered_projects` specifically to support the
multiple-repos-per-project case later without a breaking change.

**API**: Never exposed as a bare `GitInfo`; would appear nested inside a
Discovered Project or Repository resource.

**Provenance kind**: Discovered (read-only `git` command output).

**Example**: `ROLE_OS` itself — branch `main`, last commit `470d56c`
(at the time of the Sprint 1 report), 97 hardcoded absolute-path
references found in its own tracked files (expected — its own config
defaults document real paths).

---

### 1.8 Project Container

**Definition**: A folder that itself carries weak/no project signal but
wraps one or more folders that do (a "container" or monorepo-style
folder, per `scanner.has_own_strong_markers`'s inverse case) — including
the specific "wraps exactly one same-named child" pattern
(`AGUA-AZUL-APP/agua-azul-app`) that `recommendation.container_override`
already detects and flags `Rename`.

**Purpose**: Distinguishes "this folder is itself the project" from
"this folder is scaffolding around the real project(s) inside it" — so
neither gets misclassified as the other.

**Required attributes**: root_path, list/count of child Folder Candidates
found inside it.
**Optional attributes**: whether it's a "redundant wrapper" (exactly one
same-named child — today's specific override case) vs. a genuine
monorepo (multiple distinct children, e.g. `packages/*`).

**Lifecycle**: Identified during scanning (`has_own_strong_markers`
returning false) and re-confirmed after classification (the container/
child override pass, `apply_container_child_overrides`, run once per Scan
Run across all its Discovered Projects).

**Ownership**: Discovery, computed, not separately persisted today —
today it's a *classification of a Discovered Project* (via its
`recommendation` field being overridden to `Rename`), not its own entity.

**Relationships**: One Project Container has one-to-many child Folder
Candidates/Discovered Projects. See §2.4 for the full Container-vs-Project
distinction.

**Persistence**: **Not persisted today** as a distinct thing — implied by
`parent_path` on the children it contains, and reconstructible from that.

**API**: Not exposed as its own resource.

**Provenance kind**: Derived (structural inference from folder nesting).

**Example (real)**: `AGUA-AZUL-APP` (depth 1) wrapping `agua-azul-app`
(depth 2) — the actual case caught by `apply_container_child_overrides`
in the real `Documents` scan. `ROLE Commerce Factory` (real
`1 - IA PROJECTS` scan) is the *other* kind: a genuine multi-child
container (`RCOM-Printful-Adapter`, `RCOM-Shopify-Adapter`,
`ROLE_OS_BUILDER`, plus eight numbered content folders) — see §2.4.

---

### 1.9 Asset

**Definition**: One reusable file of creative/reference value discovered
inside a folder — an image, video, document, design file, or font.
Today: **not a first-class entity** — only aggregate counts
(`image_count`, `video_count`, `document_count`, `design_file_count`,
`font_count`) plus a `logo_files` path list exist on `DiscoveredProject`
(`detectors/assets.py`).

**Purpose**: The individual unit the proposal's §9 "Asset Discovery"
section anticipates persisting (`discovered_assets`: path + type + size +
mtime), enabling a future Assets page/browse view over real files instead
of just a count.

**Required attributes** (proposed, not implemented): path, asset_type
(`image`/`video`/`document`/`design-file`/`font`/`logo`), size_bytes,
modified_at.
**Optional attributes**: a human-assigned tag/caption (future,
user-authored layer).

**Lifecycle**: Would be created/refreshed per Scan Run once persisted;
today, exists only as a tally, recomputed fresh every run.

**Ownership**: Discovery (read-only discovery of the fact that the file
exists); a future user-authored caption/tag would be a separate,
Managed-Project-style overlay, never overwriting the discovered fact.

**Relationships**: Belongs to exactly one Discovered Project. Many Assets
form an Asset Collection (§1.10) when a whole folder is *itself*
classified as being mostly assets, but an individual Asset can also exist
inside a Software Project (e.g. a `logo.png` in a web app's `public/`).

**Persistence**: **Not persisted today** (aggregate counts only).
Proposed `discovered_assets` (§5), matching the proposal's §9 design
essentially unchanged.

**API**: Would appear under a Discovered Project's asset list (proposed).

**Provenance kind**: Discovered (file enumeration).

**Note — already-ambiguous prior art**: The Managed Project schema
(Epic 1) already has an `assets` JSON field that is a free-form
note/URL blob (per `08_IMPORT_ENGINE_PROPOSAL.md` §2's own critique: "no
`Asset` class/table exists... same shape as a note"). A discovered Asset
and a Managed Project's manual "asset note" must stay clearly distinct —
see the Source-of-Truth Matrix (§6).

---

### 1.10 Asset Collection

**Definition**: A folder whose dominant signal is assets rather than code
or documentation — today, the `Brand / Asset Project` classification
bucket (`classifier.classify_kind`'s `heavy_assets` branch: image+video
count ≥ 10 and no strong code/doc signal).

**Purpose**: Distinguishes "this is a place I keep brand/creative files"
from "this is a codebase that happens to contain some images."

**Required attributes**: same as a Discovered Project, with
`classification == "Brand / Asset Project"`.
**Optional attributes**: none beyond the Discovered Project's own.

**Lifecycle**: Same as Discovered Project (§4.3) — it's a *classification
value*, not a separate lifecycle.

**Ownership**: Discovery.

**Relationships**: Is-a Discovered Project (a subtype by classification,
not a distinct persisted entity). Contains many Assets (§1.9), once those
are individually tracked.

**Persistence**: Same record as its parent Discovered Project — no
separate table.

**API**: Filterable view of Discovered Projects (`classification=Brand /
Asset Project`), not its own endpoint.

**Provenance kind**: Derived (classification result).

**Example**: None yet in the two real corpora scanned — closest real
candidates would be the numbered folders under `ROLE Commerce Factory`
(`04_ASSETS`, `09_ASSET_LIBRARY`), which today classify as `Unknown`
rather than `Brand / Asset Project` (see §1.13's real example and the
Sprint 1 report's §7 "known limitation").

---

### 1.11 Documentation Collection

**Definition**: A folder whose dominant signal is documentation rather
than code or assets — today, the `Documentation Project` classification
bucket (`heavy_docs`: README plus ROADMAP/CHANGELOG/a docs folder, and no
competing code/asset signal).

**Purpose**: Distinguishes a folder of reference material *about* a
project (or product line) from the project itself.

**Attributes/lifecycle/ownership/persistence/API**: Same pattern as Asset
Collection (§1.10) — a classification value on a Discovered Project, not
a separate entity.

**Relationships**: Is-a Discovered Project. `recommendation_rules.
documentation_project` always routes these to `Requires manual review`
— a human must decide which real project (Managed or Discovered) this
documentation actually belongs to; Discovery does not guess.

**Provenance kind**: Derived.

**Example (real)**: `ROLE MASTER` (`1 - IA PROJECTS` root) — classified
`Documentation Project`, health score 48, recommendation `Requires manual
review`.

---

### 1.12 Archive

**Definition**: Two related but distinct meanings that must not be
conflated:
1. **Archive (the recommended action)** — one of the six
   `recommendation.VALID_ACTIONS`, meaning "this folder shows no ongoing
   value; move it out of active view." Produced today by
   `rules.non_project`, `rules.brand_asset_project`, and `rules.real_project`
   for stale folders.
2. **Archive (a folder state/classification)** — a folder a human has
   already confirmed is a superseded/inactive copy. **This second meaning
   does not exist in code today** — there is no `classification ==
   "Archive"` value; a stale folder is still classified by its content
   (`Non-project`, `Mixed Project`, etc.) and *separately* recommended
   `Archive` as an action.

**Purpose of the distinction**: A Recommendation is advisory (§2.7); an
Archive-the-state is a fact about a folder a human has acted on. Conflating
them would make "this project was archived" indistinguishable from "the
engine currently suggests archiving it," which are very different claims.

**Lifecycle**: The action has no lifecycle of its own (see §2.7). The
state, if ever implemented, would be a Human Confirmation outcome (§1.24),
not something Discovery assigns unilaterally.

**Ownership**: The action is Discovery's rule-engine output. The state
(if built) would be human-authored.

**Provenance kind**: Action = derived. State = would be human-confirmed.

**Example**: `ACID Pro Suite Projects` (Documents root) — classified
`Non-project`, recommended `Archive` (stale, 3 files) — the *action*
meaning; no folder in either real corpus has ever been marked Archived in
the *state* sense, since that concept doesn't exist yet.

---

### 1.13 Unknown Folder

**Definition**: A folder with real, non-trivial content (files, possibly
even a moderate confidence score) that doesn't cleanly match any of
Software Project / Website / Mixed Project / Documentation Project /
Brand-Asset Project / Non-project — today, `classification == "Unknown"`
(`classifier.classify_kind`'s final fallback).

**Purpose**: An honest "we don't know" bucket, deliberately distinct from
`Non-project` (which means "this doesn't look like a project at all").
Per `classify_kind`'s logic, `Unknown` is reached only when there *is*
some signal (confidence ≥ 0.15, or heavy assets/docs) but it doesn't
cleanly fit one category.

**Required/optional attributes**: same as any Discovered Project.

**Lifecycle**: Same as Discovered Project.

**Ownership**: Discovery.

**Relationships**: Is-a Discovered Project. `rules.fallback` always
recommends `Requires manual review` for these — the lowest-confidence,
highest-human-attention bucket.

**Persistence/API**: Same as any Discovered Project.

**Provenance kind**: Derived.

**Example (real, and a known limitation)**: The eight numbered content
folders under `ROLE Commerce Factory` in the real `1 - IA PROJECTS` scan
(`01_BRAND_CORE`, `02_PROMPT_SYSTEM`, `03_PROJECTS`, `04_ASSETS`,
`05_DOCUMENTATION`, `07_PROMPT_ENGINE`, `08_REFERENCE_LIBRARY`,
`09_ASSET_LIBRARY`) — all health score 37, all `Requires manual review`.
As the Sprint 1 report's §7 already notes, several of these (`04_ASSETS`,
`09_ASSET_LIBRARY`) look like they *should* be Asset Collections but the
classifier's signal at `max_depth=2` wasn't strong enough — a concrete,
already-observed case for future classifier tuning, not something this
document fixes.

---

### 1.14 Technology Signal

**Definition**: The subset of a Discovered Project's evidence describing
*what it's built with* — today, `detectors/markers.py`'s `MarkerFindings`
(`tech_markers`, `languages`) merged onto `DiscoveredProject.tech_markers`/
`languages`. `frameworks` is part of the shape but has no detector yet
(always empty — a known, documented gap, not new).

**Purpose**: Answers "what languages/tools/package managers does this
folder use," feeding classification (`is_web`, `has_code`) and,
eventually, the Source-of-Truth Matrix's "technology stack" row.

**Required/optional attributes**: `tech_markers` (list of marker file
paths), `languages` (dict of language → file count).

**Lifecycle**: Computed once per Scan Run by `detectors.markers.detect`;
never cached, never persisted independently.

**Ownership**: Discovery.

**Relationships**: One per Discovered Project. Contributes to
`classifier.classify_kind`'s `is_web`/`has_code` signals and
`classify_confidence`'s scoring.

**Persistence**: Bundled into the Discovered Project record today; could
become its own row in a future `discovery_findings` table (§5), tagged
`finding_type = "technology"`.

**API**: Exposed only as part of a Discovered Project resource, not
independently.

**Provenance kind**: Discovered.

**Example**: `role-content-factory` — `tech_markers` include
`pyproject.toml`; `languages` histogram dominated by Python.

---

### 1.15 Structural Signal

**Definition**: The subset of evidence describing *how the folder is
organized* — documentation presence (`detectors/documentation.py`), test
presence (`detectors/testing.py`), Docker/CI presence (`docker.py`,
`ci.py`), Obsidian/VS Code markers (`obsidian.py`, `vscode_workspace.py`),
database files (`databases.py`), environment files (`environment.py`),
launcher scripts (`scripts.py`).

**Purpose**: The broadest evidence category — everything that isn't
"what language is this" (Technology Signal) or "does this look risky to
move" (Risk Finding) or "how healthy is this" (Health Signal, which is
itself *derived from* Structural + Technology + Repository signals, not a
peer collected the same way).

**Required/optional attributes**: whichever detector-specific fields
apply (see each detector's own `Findings` dataclass, §1 of
`09_DISCOVERY_ENGINE_SPRINT1_REPORT.md`'s §7c addendum for the full list).

**Lifecycle**: Computed once per Scan Run, one detector at a time, merged
by `detectors.registry.run_all` (Sprint 1.5's registry architecture).

**Ownership**: Discovery.

**Relationships**: Many Structural Signals per Discovered Project (one
per applicable detector). Feed `classify_kind`, `classify_maturity`, and
`health.compute_health`.

**Persistence**: Bundled into the Discovered Project record today; same
future-splitting note as Technology Signal.

**Provenance kind**: Discovered.

**Example**: `charcos-site` — has a `README.md`, no `tests/` folder, no
Docker — a Structural Signal profile that (combined with its Technology
Signal) yields `Mixed Project` at confidence 0.65.

---

### 1.16 Risk Finding

**Definition**: The move-safety conclusion and its specific evidence —
today, `DiscoveredProject.move_risk` (`low`/`medium`/`high`) plus
`move_risk_reasons`, computed by `classifier.classify_move_risk` from
absolute-path references, `.env` files, launcher scripts, an Obsidian
vault, a VS Code workspace file, or a git remote pointing at a local
filesystem path.

**Purpose**: Answers "what would break if this folder were relocated?" —
the specific, explainable evidence a human needs before trusting
`Move into IA PROJECTS`.

**Required attributes**: `move_risk` (three-value enum today, informally),
`move_risk_reasons` (list of human-readable strings, each traceable to a
specific detector's raw finding — e.g. `absolute_path_refs`, `env_files`).

**Lifecycle**: Computed once per Scan Run, part of the `CLASSIFIED` stage.

**Ownership**: Discovery.

**Relationships**: One per Discovered Project. Directly consumed by
`recommendation.rules.high_move_risk` (priority 90 — the second-highest
in the whole rule table, see §4 of `DECISIONS.md`'s Sprint 1.5 entry).

**Persistence**: Bundled into the Discovered Project record today. Future
`discovery_findings` (§5) with `finding_type = "risk"` would let a Risk
Finding be queried/displayed independent of a full project record (e.g.
"show me every high-risk folder across all Scan Runs").

**API**: Part of a Discovered Project resource today (proposed);
`GET /discovery/scans/{id}/candidates` would need to surface `move_risk`
prominently given how safety-critical it is (see §7).

**Provenance kind**: Derived (a scored conclusion), backed by discovered
raw evidence (the absolute-path scan, file inventories).

**Example (real, high risk)**: `SUPER-FACIL` — 6 hardcoded absolute-path
references, `move_risk = high`, recommendation forced to
`Requires manual review` regardless of its `Mixed Project` classification.

---

### 1.17 Health Signal

**Definition**: One named, independently-scored component (0-100 or
`None`) of `health.compute_health`'s breakdown — `documentation`, `tests`,
`recent_activity`, `roadmap`, `architecture`, `automation`,
`commercial_readiness`, `deployment` — plus the weighted overall
`health_score`.

**Purpose**: Makes the single `health_score` number explainable —
"why is this 37?" always has an answer (see the weight table in
`health.py`'s `SIGNAL_WEIGHTS`).

**Required attributes**: signal name, score (0-100 or `None` if
unavailable), the weight it was given in the final average.
**Optional attributes**: none.

**Lifecycle**: Computed once, at the `SCORED` pipeline stage — guarded
(`pipeline.require_stage`) to only run after `CLASSIFIED`, since several
signals (`commercial_readiness`, `roadmap`) read classifier output.

**Ownership**: Discovery.

**Relationships**: Eight per Discovered Project (today's fixed set).
Feeds `recommendation.rules.real_project`'s `HEALTH_SCORE_THRESHOLD`
check (50).

**Persistence**: Bundled into the Discovered Project record
(`health_breakdown` dict) today. Could become rows in `discovery_findings`
(`finding_type = "health"`) later, matching how `projects/health/` already
separates each signal into its own module (Epic 1 precedent this mirrors
closely — see the alignment review, §8).

**Provenance kind**: Derived.

**Example**: `role-content-factory` — `health_score = 85`, the highest of
any Discovered Project in either real corpus.

**Relationship to Managed Project Health — decided** (`DECISIONS.md`,
decision on health ownership): this `health_score` is **Discovered
Project Health** — evidence read from the filesystem/git — and is, and
must remain, a distinct concept and number from **Managed Project
Health** (`projects/health/compute_health_score`, Epic 1's DB-driven
score over `notes`/`decisions`/`todos`/`deliverables`/activity/commits).
The two evaluate different things (technical/structural filesystem
evidence vs. the curated operational record) and **must never be silently
merged into one displayed number**, even once a Discovered Project is
linked to a Managed Project via a confirmed Identity Candidate. Showing
both, clearly labeled, side by side is fine and expected. Any future
single composite score combining them is out of scope for this document
and must, when it is designed, be its own explicitly-defined,
explainable, and *versioned* computation (so "why did the composite
change" is always answerable) — never an implicit average and never a
silent replacement of one score by the other.

---

### 1.18 Recommendation

**Definition**: The single winning action for a Discovered Project, plus
its reasons — `DiscoveredProject.recommendation`/`recommendation_reasons`,
produced by `recommendation.engine.recommend`'s highest-priority-rule-wins
selection over `recommendation.rules.RULES` (Sprint 1.5 architecture).

**Purpose**: The Discovery Engine's actual "so what" — one of exactly six
actions (`Leave where it is`, `Move into IA PROJECTS`, `Archive`,
`Merge with another project`, `Rename`, `Requires manual review`), always
paired with why.

**Required attributes**: `action` (one of the six), `reasons` (list of
strings), the winning rule's `priority` (for debugging/audit, not shown to
the end user today).
**Optional attributes**: none today; a future confidence/priority score
separate from the rule's static priority is plausible (see open questions,
§10).

**Lifecycle**: Computed once per Discovered Project per Scan Run, at the
`RECOMMENDED` stage — the last pipeline stage. Never persisted
independently of its parent Discovered Project today.

**Ownership**: Discovery.

**Relationships**: Exactly one per Discovered Project (winner-take-all;
see §2.7 for why this differs from Advisor's multi-recommendation model).
May be overridden post-hoc by the container/child pass
(`recommendation.container_override`) for Project Containers.

**Persistence — decided** (`DECISIONS.md`, "A formal Discovery Engine
Domain Model..."): a future persisted scan result or Discovery Snapshot
**may** retain the Recommendation's `action`, `reasons`, a generated
timestamp, and the rule/engine version that produced it — a plain,
recorded *value*, no different in kind from persisting any other derived
judgment (Health Signal, classification). What is explicitly **deferred**,
not merely unresolved, is full recommendation *lifecycle* behavior:
dismiss, accept, snooze, a recommendation-history UI, and — independent of
persistence entirely — automatic execution of the recommended action,
which remains permanently out of scope regardless of what gets persisted
(see the advisory-only invariant, §3, and §2.7). Whether Discovery
eventually grows Advisor's full persist-many-and-dismiss model on top of
this recorded value remains open (§10) — but "record the value" and
"manage its lifecycle" are now two separately-decided questions, not one.

**API**: Part of a Discovered Project resource (proposed).

**Provenance kind**: Derived. **Never itself an executed action** — see
the "Recommendation vs. command or action" boundary, §2.9.

**Example**: `role-ecosystem` — `Move into IA PROJECTS`, reason: "mixed
project with health score 55 and low move risk -- safe to consolidate
into IA PROJECTS."

**`Merge with another project` — reserved, not a gap** (`DECISIONS.md`):
`Merge with another project` stays a valid, permanent member of
`VALID_ACTIONS` even though **no rule currently emits it** — the closest
existing behavior (the container/child override) produces `Rename`, not
`Merge`, for the one duplicate-like case observed so far
(`AGUA-AZUL-APP`/`agua-azul-app`). This is deliberate, not an oversight to
fix: a future rule may emit `Merge with another project` only once it can
show **strong identity evidence *and* relationship evidence together**
(§9.2, §1.21) — e.g. a confirmed-duplicate Discovery Candidate
Relationship, not name similarity alone — and, like every other action,
it never executes anything by itself; consolidating two folders, projects,
or Managed Project records always requires an explicit Human Confirmation
first (§1.20), the same as any other identity or relationship decision.
Until such a rule exists, `Merge with another project` is documented here
as **reserved and inactive**, kept in the vocabulary specifically so a
future rule has a name to target rather than inventing a seventh action.

---

### 1.19 Identity Candidate

**Definition**: **Entirely new concept — no code today.** A proposed link
between a Discovered Project (or a Repository within one) and a Managed
Project, scored by however much evidence supports "these are the same
real-world project," pending human review.

**Purpose**: The missing piece between "we discovered a folder" and
"this updates a Managed Project" — see the conceptual identity-resolution
discussion, §9, for the actual reasoning this would apply.

**Required attributes** (proposed): the Discovered Project reference, the
candidate Managed Project reference (nullable — "no match found" is a
valid outcome, meaning "create new"), a confidence tier
(exact/strong/weak/conflicting — §9.2), the specific evidence list.
**Optional attributes**: a human-assigned note explaining an override.

**Lifecycle**: See §4.5.

**Ownership**: Would be Discovery-owned (`identity_candidates`, §5) since
it's discovery's proposal, not yet a Managed Project fact.

**Relationships**: One Discovered Project may have zero, one, or several
competing Identity Candidates (e.g. two similarly-named Managed Projects).
Resolved by exactly one Human Confirmation (§1.24) — or none, if left
pending indefinitely.

**Persistence**: Proposed only (§5). **Confidence scoring alone must
never auto-resolve one of these** — this is a hard invariant (§3).

**API**: Proposed identity-confirmation endpoints (§7) would list/act on
these; never auto-applied via a bare `GET`.

**Provenance kind**: Derived (a proposal), requiring human action to
become fact.

**Example (hypothetical, no real case yet)**: A `role-content-factory`
folder rediscovered after being moved to a new path — same name, same git
remote, different `root_path` — would generate a "strong evidence"
Identity Candidate linking the new Discovered Project to the existing
Managed Project, per §9's "same project moved to another folder" case.

---

### 1.20 Human Confirmation

**Definition**: **Entirely new concept — no code today.** The recorded
decision a person made about an Identity Candidate (or, more broadly, any
Discovery proposal requiring approval before it affects a Managed
Project) — confirm, reject, or defer.

**Purpose**: The one and only mechanism by which discovered data is
allowed to touch a Managed Project. See the hard invariant in §3:
"Identity resolution never silently merges user-authored Projects."

**Required attributes** (proposed): which Identity Candidate (or proposal)
it resolves, the decision (`confirmed`/`rejected`/`deferred`), timestamp,
(future) which human/session made it.
**Optional attributes**: a free-text reason.

**Lifecycle**: Created once, by one human action; immutable after
creation (a changed mind creates a new Human Confirmation superseding the
old one, never edits history in place — same "append, never rewrite"
discipline this codebase already uses for `schema_migrations` and
`role-ecosystem/DECISION_LOG.md`).

**Ownership**: Would be Discovery-owned (`identity_confirmations`, §5),
since it's a decision *about* a Discovery proposal, even though its
effect (once confirmed) may write into the Projects domain.

**Relationships**: Resolves exactly one Identity Candidate. A confirmed
one is what makes a Discovered Project's evidence eligible to enrich its
linked Managed Project (additively — see §3's invariant on human-authored
fields).

**Persistence**: Proposed only (§5). Must be durable and auditable —
never recomputed, unlike a Health Signal.

**API**: Proposed confirm/reject endpoints (§7).

**Provenance kind**: Human-authored (the one concept in this whole model
that just *is* human input, not evidence about it).

---

### 1.21 Project Relationship

**Definition — two tiers, ownership decided** (`DECISIONS.md`, decision
C): a directional or symmetric link between two Managed and/or Discovered
Projects — "depends on," "related to," "part of the same family" (§1.22).
This concept now has two explicitly separate tiers, not one:

- A **confirmed Project Relationship** is authoritative — it exists in,
  and is owned solely by, the **Projects domain**. Managed Projects
  already have a `related_projects: list[str]` field and a separate
  `dependencies` table (both Epic 1); any future confirmed relationship
  involving a formerly-Discovered Project lives there too, once linked.
- A **Discovery Candidate Relationship** is Discovery's own, lesser
  claim: a *proposal*, never authoritative, always labeled to make clear
  it is unconfirmed. Discovery's only relationship-shaped behavior
  today (the container/child override) is structural (nesting) and
  already effectively produces one of these — see the labeled types
  below.

**Purpose**: Lets the eventual Workspace Graph (§1.25/§1.26) express "these
things go together" beyond simple folder nesting — e.g. two Discovered
Projects that are actually the frontend and backend of one product —
while keeping a hard line between "Discovery thinks these go together"
and "a human has said these go together."

**Required attributes** (proposed, Discovery Candidate Relationship):
source, target, one of the labeled candidate types: `possible duplicate
of`, `possible archived copy of`, `possible fork of`, `possible child
module of`, `possible member of project family`, `possible successor or
predecessor of`. **Every candidate type name starts with "possible"** —
this is not a style choice, it is how a candidate stays visually and
programmatically distinguishable from a confirmed relationship at every
layer (data, API, UI) that might display it.
**Optional attributes**: the evidence tier (§9.2) and specific evidence
list that produced it, a human's override note if rejected.

**Lifecycle**: A Discovery Candidate Relationship is always derived
(never human-asserted directly — a human who wants to assert a
relationship uses the existing Epic 1 `related_projects` mechanism
instead, in the Projects domain). It becomes a confirmed Project
Relationship only through the same explicit Human Confirmation step
Identity Resolution already requires (§1.20, §4.5) — **there is no path
by which a Discovery Candidate Relationship becomes authoritative on its
own**, regardless of evidence strength (restated as invariant 15, §3).

**Ownership**: **Decided.** Confirmed Project Relationships: Projects
domain, exclusively (existing `related_projects`/`dependencies` tables,
unchanged). Discovery Candidate Relationships: Discovery, exclusively,
and only ever as proposals (future `discovery_candidate_relationships`,
§5) — Discovery never writes to `related_projects`/`dependencies`
directly, even after a human confirms a candidate; confirmation is
recorded as a Human Confirmation (§1.20), and *that* record is what
authorizes (a person, or a well-scoped future automation acting strictly
on that record) writing the confirmed relationship into the Projects
domain's own tables.

**Relationships**: N:N between any two Projects (Managed or Discovered),
at either tier.

**Persistence**: Confirmed tier: existing Epic 1 tables, unchanged.
Candidate tier: proposed only (§5), Discovery-owned.

**API**: Existing Epic 1 endpoints for the confirmed tier; unspecified for
the candidate tier (§7) — but any future candidate-relationship endpoint
must return the `possible ...` label prominently, per invariant 15.

**Provenance kind**: Confirmed tier: human-asserted (via Epic 1) or
human-confirmed (via a resolved Identity Candidate). Candidate tier:
always derived, never anything else.

**Example**: `AGUA-AZUL-APP` → `agua-azul-app` is a `possible duplicate
of`/structural-containment case today (implicit via `parent_path` and the
`Rename` recommendation override, §1.8) — a Discovery Candidate
Relationship in spirit, though not yet materialized as a named,
persisted record.

---

### 1.22 Project Family

**Definition**: A named group of Managed and/or Discovered Projects that
together make up one product or initiative, even though they live in
separate folders/repositories — a specific, coarser kind of Project
Relationship (§1.21), and therefore subject to the same two-tier
ownership split decided there. **Entirely new concept — no code today.**

**Purpose**: Answers "which of these folders are actually one thing?" —
the proposal's own §6.5 example ("multiple folders belonging to one
product family") and a real, already-observed case (below).

**Required attributes** (proposed): family name, member list (Managed
and/or Discovered Project references), and — mirroring §1.21 — whether
this is a *candidate* family (Discovery-proposed, labeled `possible member
of project family` per member) or a *confirmed* family (Projects-domain-
owned, no "possible" qualifier).
**Optional attributes**: a description, a designated "primary" member.

**Lifecycle**: A candidate Project Family is proposed by Identity
Resolution (weak-to-strong evidence, §9) from discovered structural
evidence (e.g. a Project Container wrapping several distinct children,
§1.8); it becomes a confirmed Project Family only through a Human
Confirmation (§1.20), exactly like any other candidate relationship.

**Ownership**: **Decided**, mirroring §1.21: candidate Project Families
are Discovery-owned proposals; confirmed Project Families are owned by
the Projects domain. Discovery never asserts a confirmed family on its
own authority.

**Relationships**: One Project Family has many member Projects (Managed
or Discovered). A Project Container (§1.8) is a *structural* special case
(nesting) of the more general Project Family (which doesn't require
nesting at all — siblings in unrelated folders can be one family).

**Persistence**: Proposed only (§5).

**Provenance kind**: Derived (proposed) until human-confirmed.

**Example (real)**: `ROLE Commerce Factory` (real `1 - IA PROJECTS` scan)
— contains `RCOM-Printful-Adapter`, `RCOM-Shopify-Adapter`, and
`ROLE_OS_BUILDER` as depth-2 children. Today the scan reports these as
four separate Discovered Projects with a `parent_path` relationship
(structural/Container); whether they're *actually* one Project Family
(one commerce product with three components) is exactly the kind of
judgment this concept exists to let a human make explicit, rather than
leaving it as an accident of folder nesting.

---

### 1.23 Discovery Source

**Definition**: A tag on a piece of data recording *where it came from* —
filesystem discovery, git, user input, a derived engine computation, or a
human confirmation. **Not implemented as a general per-field concept
today.** The closest existing precedent is the proposal's own §14
`discovery_source` column (`'manual' | 'discovered'`) — but that's a
single flag on a whole Managed Project row, not fine-grained per-field
provenance.

**Purpose**: Lets the Source-of-Truth Matrix (§6) be enforced in code, not
just documented — e.g. so a UI can show "priority: set by you" vs.
"languages: detected from files" on the same project's page.

**Required attributes** (proposed): field name, source kind (one of:
filesystem discovery / git / user input / derived / human confirmation),
timestamp of last update from that source.

**Lifecycle**: Set whenever a field is written; would need updating on
every rescan (filesystem/git-sourced fields) or every user edit
(user-input fields).

**Ownership**: Cross-cutting — would live alongside whichever record it
annotates.

**Relationships**: Every persisted field, in a fully-realized future
model, would carry one. Not attempted at that granularity in this
document's proposed persistence model (§5) — flagged as a refinement for
whichever sprint actually designs the schema, not committed to here.

**Persistence**: Proposed conceptually; the coarse Managed-Project-level
version (`discovery_source` per proposal §14) is a reasonable first cut.

**Provenance kind**: Meta — describes provenance, isn't itself evidence.

---

### 1.24 Discovery Snapshot

**Definition**: An immutable, point-in-time capture of one Discovered
Project's state as produced by one specific Scan Run — distinct from the
Scan Run itself (the *event* of scanning) and from the live/current
Discovered Project (which a *new* Scan Run would replace). **Not
implemented today** — every Scan Run's `ScanResult` is transient and
discarded once printed/written; there is no history.

**Purpose**: Enables "what did this folder look like last Tuesday"
history/trend views (health score over time, when a folder's
classification changed, when its move risk first became high) without
needing every historical detail duplicated into the live record.

**Required attributes** (proposed): scan_run_id, discovered_project
identity (folder path or future durable id), the full Discovered
Project state as of that run, captured_at.

**Lifecycle**: Created once, at the end of a Scan Run, per Discovered
Project found; immutable thereafter (never edited, only superseded by a
later Snapshot from a later Scan Run).

**Ownership**: Discovery (`discovery_snapshots`, §5).

**Relationships**: Many Snapshots per Discovery Root over time (one per
Scan Run that touched it). The *current* Discovered Project, in a
persisted future, would simply be "the latest Snapshot" — not a
separately-maintained mutable row (avoids the exact "duplicate data into
a new store" anti-pattern Rule #2 of `06_DEVELOPMENT_RULES.md` warns
against; a Snapshot *is* the record, not a copy of one).

**Persistence**: Proposed only (§5). Historical — must be retained, not
recomputed (see §5's retention notes).

**API**: A future `GET /discovery/projects/{id}/history` shape, not
designed here.

**Provenance kind**: Derived + timestamped (a historical fact about a
derived computation, not new evidence itself).

---

### 1.25 Workspace Graph Node

**Definition**: **Entirely new concept — no code today**, and
deliberately a *third*, independent graph vocabulary alongside two that
already exist in this codebase: Epic 3's `/graph` (12 node types, computed
from Project Intelligence + the Builder knowledge base) and Sprint 5's
`/conversation-graph` (8 node types, computed from imported conversations).
A Workspace Graph Node would represent a Discovery-sourced entity —
a Discovery Root, a Discovered Project, a Repository, a Project
Container/Family — as a graph node.

**Purpose**: A future visual/queryable view of "how does everything
Discovery has found relate to everything else" — containers, families,
shared repositories, links to Managed Projects — mirroring what Epic 3's
Graph already does for Project Intelligence data, but for filesystem-
sourced structure instead.

**Required attributes** (proposed, mirroring `app/graph/models.py`'s
existing `Node` shape for consistency): `id`, `type`, `label`, `data`.

**Lifecycle**: Would be computed on demand from Discovery's persisted
data (Scan Runs, Discovered Projects, confirmed links), the same
"computed fresh, no dedicated graph database" pattern Epic 3 and Sprint 5
both already use — **not stored as its own persisted node**, per
Development Rule #2.

**Ownership**: Would be Discovery-owned computation, consuming Discovery's
own persisted tables plus (read-only) the Projects domain's, exactly as
Epic 3's `/graph` reads from three domains without owning any of them.

**Relationships**: See Workspace Graph Edge (§1.26).

**Persistence**: **Never persisted as such** — computed on demand, same
as every existing graph in this codebase.

**API**: A future `/discovery/graph` (or similarly named — see the
terminology-conflict note in §8) namespace, entirely separate from
`/graph` and `/conversation-graph`.

**Provenance kind**: Derived (a computed view over other, already-typed
data).

---

### 1.26 Workspace Graph Edge

**Definition**: A typed relationship between two Workspace Graph Nodes —
`contains` (Project Container → child), `same_family` (Project Family
membership), `linked_to` (Discovered Project → confirmed Managed
Project), `shares_repository` (two Discovered Projects, one Repository).

**Required attributes** (proposed, mirroring `app/graph/models.py`'s
`Edge`): `source`, `target`, `type`.

**Everything else**: Same as Workspace Graph Node (§1.25) — computed on
demand, never persisted, entirely new, no code today.

---

## 2. Boundaries and Distinctions

### 2.1 Workspace vs. Discovery Root

**Workspace** is an existing, human-curated *category* for Managed
Projects (`Personal`, `Products`, ...) — it has no filesystem meaning at
all. **Discovery Root** is a *filesystem path* Discovery scans — it has
no notion of "category" at all. A single Discovery Root (e.g.
`1 - IA PROJECTS`) will, after Identity Resolution, contribute Managed
Projects to *several different* Workspaces (a discovered `role-content-
factory` folder might become a Managed Project in the `Products`
Workspace; a discovered personal notes vault might become one in
`Personal`). **These are orthogonal axes, not synonyms** — this document
deliberately reuses the existing "Workspace" term rather than inventing a
second one, to avoid exactly the kind of silent terminology collision
§8 warns about.

### 2.2 Folder Candidate vs. Discovered Project

A Folder Candidate is an *admission decision* ("this folder is worth
analyzing") — cheap, structural, made before any deep signal extraction.
A Discovered Project is the *result* of fully analyzing one Folder
Candidate — expensive (relatively), detailed, classified, scored,
recommended. Every Folder Candidate becomes exactly one Discovered
Project (analysis doesn't itself reject candidates — even a
`Non-project`-classified folder was still a Candidate that got fully
analyzed); the distinction matters because a Candidate can be reasoned
about (and, if ever needed, rate-limited/paginated/deferred) *before*
paying the cost of full analysis.

### 2.3 Discovered Project vs. Managed Project

The single most important distinction in this whole model, restated
plainly: a **Discovered Project is evidence, recomputed fresh every scan,
owned entirely by Discovery, never edited by a human directly**. A
**Managed Project is a decision, persisted once and edited over time,
owned by Project Intelligence, containing exactly the fields a human (or
an Advisor/graph computation acting on human-entered data) put there**.
A Discovered Project has no `notes`/`decisions`/`priority` — those don't
exist until a human creates or links a Managed Project. A Managed Project
has no `move_risk`/`confidence_score` — those are Discovery-only
judgments about a filesystem, not something a human "sets." **Linking the
two (Identity Resolution, §9) never merges their schemas into one row —
it creates a reference between two records that keep their own separate
lifecycles.**

### 2.4 Project Container vs. Project

A Project Container is defined *by what it lacks* (its own strong
project markers) *and* what it wraps (one or more child Folder Candidates
with real signal). A Project (Discovered or Managed) is defined by what
it *has*. The two real examples already found make the distinction
concrete: `AGUA-AZUL-APP` (a Container wrapping exactly one same-named
child — almost certainly a redundant wrapper, hence the `Rename`
recommendation) versus `ROLE Commerce Factory` (a Container wrapping
several *distinct* children — a genuine multi-project family, not a
wrapper to flatten). The same structural pattern (nesting) means two
different things depending on what's inside; this document does not
attempt to resolve which of those two container shapes should ever
itself become a Managed Project entity (open question, §10).

### 2.5 Asset vs. Asset Collection

An Asset is one file. An Asset Collection is a *folder classification* —
a Discovered Project whose dominant content happens to be Assets. A
Software Project can contain Assets (a `logo.png` in `public/`) without
being an Asset Collection. An Asset Collection is not a container *of*
Asset entities in today's implementation (only aggregate counts exist) —
this is a real, acknowledged gap between the two concepts as currently
built versus as this document defines them; closing it means
implementing per-file Asset tracking (§5's proposed `discovered_assets`),
not something this document does.

### 2.6 Scan Run vs. Discovery Snapshot

A Scan Run is the *event* — "discovery executed against this root at this
time, took this long, hit these errors." A Discovery Snapshot is the
*result*, per Discovered Project, from that event — "here is what folder
X looked like as of that run." One Scan Run produces many Snapshots (one
per Discovered Project it found). Neither exists as a persisted concept
today; the distinction matters for the future persistence model (§5)
because a Scan Run's operational metadata (duration, errors, status) has
a completely different retention/query shape than a Snapshot's evidentiary
content (which needs to support "show me this folder's health score
history," not "show me how long scans have taken").

### 2.7 Recommendation vs. command or action

A Recommendation is a **claim**: "given the evidence, action X is
advisable, for reasons Y." It is never itself executed. Nothing in
Discovery today — or proposed anywhere in this document — moves a
folder, renames a folder, merges two Managed Projects, or archives
anything, in response to a Recommendation. The six actions
(`Leave where it is`, `Move into IA PROJECTS`, `Archive`,
`Merge with another project`, `Rename`, `Requires manual review`) read as
imperatives but function as *labels a human reads*, exactly like Advisor's
`suggested_action` field already does for Managed Projects — Discovery's
Recommendation is the same kind of thing, not a new precedent.

### 2.8 Identity Candidate vs. confirmed identity

An Identity Candidate is a **proposal with a confidence tier** — exact,
strong, weak, or conflicting evidence (§9.2) — that a Discovered Project
and a Managed Project (or two Discovered Projects, for Project Family
purposes) refer to the same real thing. It carries no authority on its
own, regardless of how high its confidence is. A confirmed identity only
exists after a Human Confirmation (§1.20) resolves that specific
candidate. **There is no threshold at which a candidate's score alone
promotes it to confirmed** — see the hard invariant in §3.

### 2.9 Project Relationship vs. Project Family

A Project Relationship is the general N:N link type (§1.21) — including
directional ones like `depends_on` that have nothing to do with "these
are one product." A Project Family is a specific, named, typically
symmetric grouping meant to answer "which folders/repos are actually one
thing" (§1.22). Every Project Family membership is a Project Relationship
(of type `same_family`), but not every Project Relationship implies a
Project Family (a `depends_on` link between two otherwise-unrelated
products is a Relationship, not a Family).

### 2.10 Discovery data vs. user-authored project data

Discovery data (classification, health score, move risk, tech stack,
recommendation) is **always recomputed from the filesystem** and
**never hand-edited** — there is no `PATCH /discovery/...` that lets a
human override a classification in place. User-authored project data
(notes, decisions, priority, tags on a Managed Project) is **never
recomputed** — it only changes when a human changes it. Where the two
need to coexist on one eventual "project detail" view, they are rendered
side by side, sourced from two different records, per the Source-of-Truth
Matrix (§6) — never merged into one mutable blob.

### 2.11 Discovered facts vs. derived judgments

A **discovered fact** is something a detector directly observed — "a
`README.md` file exists," "47 `.py` files," "the git remote is
`git@github.com:...`." A **derived judgment** is a conclusion computed
from facts — `classification`, `move_risk`, `health_score`,
`recommendation`. This distinction is why every judgment in this codebase
carries a `reasons`/`breakdown` alongside it: a judgment must always be
traceable back to the facts that produced it (already true today, and a
hard invariant going forward, §3).

### 2.12 Machine confidence vs. human confirmation

A confidence score (`confidence_score`, an Identity Candidate's evidence
tier, a Recommendation's rule priority) is **Discovery's estimate of its
own certainty** — it can be wrong, and nothing in this model treats a
high score as equivalent to human sign-off. A Human Confirmation is an
**actual person's decision**, recorded once, and is the only thing that
authorizes discovered data to affect a Managed Project. No confidence
threshold, however high, substitutes for one — restated as a hard
invariant in §3 because this is the single most safety-critical boundary
in the whole model.

### 2.13 Managed Project Health vs. Discovered Project Health

**Decided** (`DECISIONS.md`): these are two separate scores, computed by
two separate engines, over two separate kinds of evidence, and they stay
that way. **Managed Project Health** (`projects/health/
compute_health_score`, Epic 1) evaluates the curated operational/
project-management record — activity per the DB's `updated_at`, open
todos, unresolved decisions, missing deliverables, linked conversations,
and (if ever wired up) real commit dates. **Discovered Project Health**
(`discovery/health.compute_health`, Sprint 1/1.5) evaluates technical and
structural evidence Discovery itself found — documentation presence,
tests, recent filesystem/git activity, roadmap, structural signals,
automation, commercial readiness, deployment config. A Discovered Project
has no `notes`/`decisions`/`todos` to score; a Managed Project (until
linked) has no filesystem to inspect. **They may be presented together**
once a link exists — a project detail view showing both numbers, clearly
labeled, is exactly the intended future use — **but must never be
silently merged into one score**. Any future composite must be its own
explicitly-designed, explainable, versioned computation, not an implicit
average of the two or a quiet replacement of one by the other (see §1.17,
§6).

---

## 3. Domain Invariants

Non-negotiable, in priority order:

1. **Discovery is read-only with respect to scanned filesystems.**
   (Already true and tested — see `test_discovery.py`'s
   `test_audit_does_not_modify_scanned_tree`.) No future feature may
   change this for the scanned root itself; a Scan Run's own metadata
   store is a separate concern (invariant 2).
2. **A Scan Run never mutates the scanned root.** Any output it produces
   (reports, persisted Snapshots) is written to Discovery's own storage
   or a caller-supplied location outside the root — never inside it.
3. **A Recommendation is advisory and does not execute an action.** No
   code path may ever move, rename, delete, or merge anything in response
   to a Recommendation without an intervening Human Confirmation.
4. **A Folder Candidate may exist without becoming a Discovered
   Project.** (Not true today in practice — every Candidate is currently
   analyzed — but the *concept* must permit a future admission gate, e.g.
   a size/budget cutoff, without that being a modeling contradiction.)
5. **A Discovered Project may exist without being linked to a Managed
   Project.** The overwhelming majority of Discovered Projects, in either
   real corpus scanned so far, have no corresponding Managed Project at
   all — this must remain a valid, unremarkable, permanent state, not a
   transient one every folder is expected to leave.
6. **Identity resolution never silently merges user-authored Projects.**
   No confidence score, however high, may cause two Managed Projects (or
   a Managed Project and a Discovered Project) to merge without an
   explicit Human Confirmation of that specific merge.
7. **Human-authored fields must not be overwritten by discovered
   metadata.** Even after a confirmed link, a Managed Project's `notes`,
   `decisions`, `priority`, `tags`, and any other human-entered field are
   never overwritten by a rescan — discovered data may only ever *fill a
   gap* (e.g. populate `root_path` if it was previously null) or appear
   *alongside* human data, never replace it.
8. **Filesystem paths must be normalized but original path representation
   must remain recoverable where needed.** (Already partly true —
   `absolute_path_refs` stores the literal matched snippet, not just a
   normalized form.) Any future normalization (for identity matching,
   deduplication) must retain the original string somewhere, since
   Windows path casing/separators/junction targets are exactly the kind
   of detail a human resolving an Identity Candidate will need to see.
9. **Discovery provenance must be retained for every persisted finding.**
   Once anything in this model is persisted, it must be attributable to
   the specific Scan Run (and, transitively, Discovery Root) that
   produced it — never persisted as an anonymous fact.
10. **Derived scores must remain explainable through their underlying
    signals.** (Already true — `confidence_reasons`, `move_risk_reasons`,
    `maturity_reasons`, `commercial_reasons`, `health_breakdown`,
    `recommendation_reasons` all exist today.) Any new score introduced by
    a future sprint must carry the same kind of explanation, not just a
    number.
11. **Public API models must not directly expose mutable internal
    dataclasses.** `DiscoveredProject`/`ScanResult` (or their persisted
    successors) must never be returned as-is from an endpoint — a
    dedicated `api_models.py`-style boundary (matching Epic 3's Graph
    precedent) is required before any Discovery endpoint ships.
12. **Only server-approved roots may be scanned through a future API.**
    An HTTP-exposed scan trigger must validate the requested root against
    a server-side allow-list before touching the filesystem — never scan
    an arbitrary caller-supplied path. (Raised in the prior architecture
    review as a hard blocker; restated here as a permanent invariant, not
    a one-time fix.)
13. **A Discovery Root, once registered, is never silently rescanned into
    a different Discovery Root's history.** (New, implied by §2.6's
    Scan-Run/Snapshot distinction: if a root's path changes — a drive
    letter remap, a folder rename — that must be a deliberate re-
    registration decision, not an automatic assumption that "the same
    path today = the same root as last time," since Windows drive letters
    and Google Drive sync paths are exactly the kind of thing that can
    shift under a user without their folders having actually moved.)
14. **A Project Container's classification is never used to auto-flatten,
    auto-merge, or auto-delete its child folders.** The existing
    `Rename` recommendation for a redundant wrapper (§1.8) is advisory,
    per invariant 3 — no automation may act on it without a human
    performing the actual filesystem operation themselves, entirely
    outside Discovery's own read-only guarantee (invariant 1).
15. **`Merge with another project` may never be emitted by a rule without
    both strong identity evidence *and* relationship evidence together**
    (§9.2, §1.21) — name similarity or a single weak signal alone is
    never sufficient, and, per invariant 3, even a correctly-emitted
    `Merge with another project` recommendation still only executes
    after an explicit Human Confirmation.
16. **A Discovery Candidate Relationship (or candidate Project Family) is
    never treated as, displayed as, or silently promoted to, a confirmed
    Project Relationship.** Every candidate-tier label carries an explicit
    "possible" qualifier (§1.21) at every layer it appears in — data,
    API, and UI alike — until a Human Confirmation resolves it. Discovery
    never writes directly to the Projects domain's `related_projects`/
    `dependencies` tables, under any confidence score.
17. **Managed Project Health and Discovered Project Health are never
    silently merged into one score.** (§2.13, §1.17.) Any future
    composite score combining them must be introduced as its own
    explicitly-defined, explainable, and versioned computation — never an
    implicit average, and never a computation that replaces one score
    with the other without both remaining independently visible.

---

## 4. Lifecycles

### 4.1 Discovery Root

```
Unregistered -> Registered -> Active -> Retired
```
- **Unregistered**: A path exists on disk but Discovery has never been
  pointed at it (the state of every folder on the machine, today, before
  any scan).
- **Registered**: A human has scanned it at least once (today: simply
  running the CLI with `--root`; no persisted registration exists yet).
- **Active**: Registered and expected to be rescanned periodically
  (implied by future "Rescan" functionality, not implemented).
- **Retired**: The root no longer exists, or a human has explicitly
  stopped tracking it (e.g. the folder was deleted or superseded by a
  new location). Not implemented; would need explicit human action per
  invariant 13 — never inferred purely from "the path 404'd this scan"
  (which could just as easily be a temporarily-unmounted drive).

### 4.2 Scan Run

```
Requested -> Queued -> Running -> Completed
                              \-> Completed with warnings
                              \-> Failed
Requested -> Cancelled
Queued -> Cancelled
```
- **Requested**: A human or (future) scheduled trigger asks for a scan.
- **Queued**: Accepted but not yet executing (relevant once scanning is
  asynchronous, per the prior architecture review's recommendation that
  Discovery's API not be a synchronous compute-on-GET).
- **Running**: The scanner/detector/classifier/health/recommendation
  pipeline is actively executing. Today, this is the CLI's entire runtime
  — a single synchronous call, with no observable intermediate state.
- **Completed**: Finished, zero errors, zero skipped paths worth
  flagging.
- **Completed with warnings**: Finished, but `skipped_paths` and/or
  `errors` are non-empty (already a real, observed case — the real
  `Documents` scan skipped 3 permission-denied paths and still completed
  successfully).
- **Failed**: Could not run at all — e.g. the root doesn't exist
  (`FileNotFoundError`) or isn't a directory (`NotADirectoryError`), both
  already handled today by raising before any Scan Run "starts" in the
  persisted sense.
- **Cancelled**: A human or system aborts a Requested/Queued run before
  it starts executing (only meaningful once queuing exists).

*(States only — no implementation implied; today's CLI has exactly one
observable transition, Requested → Completed/Completed-with-warnings/
Failed, all synchronous.)*

### 4.3 Folder Candidate

```
Discovered by scanner -> Analyzed (becomes a Discovered Project)
                       -> Analysis failed (recorded in Scan Run errors, discarded)
```
No intermediate states — a Candidate's entire lifecycle happens within
one Scan Run and produces exactly one of the two outcomes above.

### 4.4 Discovered Project

```
NEW -> DETECTED -> CLASSIFIED -> SCORED -> RECOMMENDED
```
This is `PipelineStage` (Sprint 1.5, `app/discovery/pipeline.py`) — the
one lifecycle in this entire document that is **already implemented and
enforced today**, via `pipeline.require_stage` guards on
`health.compute_health` (requires `CLASSIFIED`) and
`recommendation.recommend` (requires `SCORED`). No sibling document
concept has code-enforced transitions yet; this one does, and future
persistence work should extend this enum (e.g. a future `LINKED` stage
once Identity Resolution exists) rather than inventing a parallel scheme.

### 4.5 Identity Candidate

```
Proposed -> Presented for review -> Confirmed
                                 -> Rejected
                                 -> Deferred (remains Presented indefinitely)
```
- **Proposed**: Identity Resolution generates it from evidence (not
  implemented).
- **Presented for review**: Visible to a human via a future confirm/
  reject UI/API (not implemented).
- **Confirmed**: A Human Confirmation resolves it positively — the link
  becomes real, subject to invariant 7 (never overwrites human fields).
- **Rejected**: A Human Confirmation resolves it negatively — the
  Discovered Project remains unlinked; Discovery should not re-propose
  the identical candidate on the very next scan without new evidence
  (avoiding "reject fatigue" from repeatedly re-surfacing the same
  rejected suggestion) — a UX concern to solve in whichever sprint builds
  this, not resolved here.
- **Deferred**: Left pending; a valid long-term state, not a defect.

### 4.6 Human Confirmation

```
Recorded (immutable)
```
A Human Confirmation has no further lifecycle once created — it is a
timestamped, append-only fact. A changed mind creates a *new* Human
Confirmation record superseding the old one's practical effect, rather
than editing history in place (§1.20).

### 4.7 Recommendation

```
Computed (per Scan Run) -> superseded by the next Scan Run's Recommendation
```
A Recommendation itself still has no independent lifecycle states of its
own — it is computed fresh at the `RECOMMENDED` pipeline stage and, per
Decision A (§1.18, `DECISIONS.md`), its *value* (`action`, `reasons`,
timestamp, rule/engine version) may be retained as part of a future
persisted Scan Run/Snapshot. That is recording a value, not giving the
Recommendation "dismissed"/"completed" states the way an Advisor
recommendation has — full recommendation lifecycle management remains
explicitly deferred (§1.18), and whether Discovery eventually adopts
Advisor's full persist-and-dismiss model on top of the recorded value
remains an open question (§10), not decided here.

### 4.8 Discovery Snapshot

```
Captured (at the end of a Scan Run) -> immutable, permanently retained
                                     -> superseded (not replaced) by the next Snapshot
```
"Superseded, not replaced" matters: a new Snapshot for the same
Discovered Project does not delete or overwrite the previous one — it
becomes the new *current* one while the old one remains queryable
history, per §5's retention notes.

---

## 5. Future Persistence Model (logical only — no SQL, no migrations)

Following this codebase's established convention (§08 proposal, and every
existing domain: Projects, Advisor, Imports, Extraction each own a
separate SQLite file) — **Discovery would own its own database**, kept
entirely separate from `role_os_projects.db`. Logical entities, not exact
columns:

| Entity | Durable? | Recomputable? | Notes |
|---|---|---|---|
| `discovery_roots` | Durable | No (user-declared) | One row per registered Discovery Root. |
| `discovery_runs` | Durable | No (historical event) | One row per Scan Run; append-only. |
| `discovered_candidates` | Ephemeral (per-run) | Yes | Could be transient/not persisted at all — a Folder Candidate's only lasting trace is the Discovered Project it produced. |
| `discovered_projects` | Durable (as the *current* state) | Yes, in full, from a rescan | The latest Snapshot's content, denormalized for fast querying — conceptually a view over `discovery_snapshots`, not independent truth. |
| `discovered_repositories` | Durable | Yes | Decoupled from `discovered_projects` specifically to support multiple repositories per project (§1.7's flagged gap) without a later breaking change. |
| `discovered_assets` | Durable | Yes | Matches proposal §9 essentially unchanged: path + type + size + mtime. |
| `discovery_findings` | Durable (if adopted) | Yes | Optional normalization of Technology/Structural/Risk/Health signals into queryable rows instead of JSON blobs on `discovered_projects` — a refinement, not required for Sprint 2. |
| `discovery_recommendations` | Durable (value only) | Yes (the value; not the decision) | Per Decision A: stores the winning `action`/`reasons`/generated timestamp/rule-or-engine-version as part of a Scan Run or Snapshot. **Does not imply** dismiss/accept/snooze columns or a recommendation-history UI — those are explicitly deferred past Sprint 2 (§1.18). Whether every losing candidate is *also* kept (Advisor-style) remains an open question (§10). |
| `identity_candidates` | Durable | No (a specific proposal, tied to specific evidence at a specific time) | Must retain the evidence that produced it, not just the conclusion. |
| `identity_confirmations` | Durable, historical | No | Append-only, per §4.6. **Never purged** — this is the audit trail for why a Managed Project has the `root_path` it has. |
| `discovery_snapshots` | Durable, historical | No (a Snapshot is retained even after the folder it describes changes or disappears) | The actual historical record; `discovered_projects` (above) is best understood as "latest snapshot per project," not a second copy of the same data. |
| `discovery_candidate_relationships` | Durable | Mixed (structural candidates are recomputable; evidence-based ones are tied to a specific run) | Per Decision C: Discovery-owned, **candidate tier only** (`possible duplicate of` / `possible archived copy of` / `possible fork of` / `possible child module of` / `possible member of project family` / `possible successor or predecessor of`). Never the authoritative store for a confirmed relationship — see the next row. |
| *(confirmed relationships/families)* | Durable | No (human-asserted or human-confirmed) | Per Decision C: **owned exclusively by the Projects domain** — Epic 1's existing `related_projects`/`dependencies` tables, extended (not duplicated) once a Discovery Candidate Relationship is confirmed. Discovery does not own, and never gains, a table for confirmed relationships. |

**Sensitive-data note**: `discovered_assets` and `discovery_findings`
(absolute-path evidence specifically) can incidentally capture personal
or credential-adjacent path fragments (usernames in Windows paths, `.env`
filenames — never their *contents*, per the original proposal's §17 risk
table, which already excludes reading `.env`/`*key*`/`*credential*`
*content*). Retention policy for these fields is an open question for
whoever designs the actual schema — flagged, not decided, here.

**Retention**: `discovery_runs`, `discovery_snapshots`, and
`identity_confirmations` are historical and must be retained
indefinitely (or per an explicit, human-configured retention policy) —
they are the only record of "why does this Managed Project look the way
it does." Everything else in the table above is either fully
recomputable from a rescan or, per the open question in §10, may not
need to be durable at all.

---

## 6. Source-of-Truth Matrix

| Field | Authority | Conflict rule |
|---|---|---|
| Project name | User input, if a Managed Project exists; otherwise filesystem discovery (folder name) | Once a Managed Project exists, its name is authoritative even if the folder is later renamed on disk — a rescan updates `root_path`'s target, never silently renames the Managed Project. |
| Description | User input (Managed Project) | Discovery never populates this field; a Discovered Project has no "description," only `classification`. |
| Priority | User input (Managed Project) | Never touched by Discovery. |
| Status | User input (Managed Project) | Never touched by Discovery. `maturity` (Discovered Project) is a *different*, Discovery-only field and must not be confused with or written into `status`. |
| Filesystem path | Filesystem discovery | Authoritative from Discovery; a Managed Project's `root_path` (once it exists, proposal §14) is filled from this, never hand-typed. |
| Git remote | Git (via `git_reader`) | Authoritative from Discovery/git; read-only, never user-editable. |
| Technology stack | Derived engine result (`detectors/markers.py`) | Recomputed every scan; a human cannot override it (there is no field for a manual override today — if one is ever added, it must be a clearly separate "user-declared stack" field per invariant 7, not a mutation of the discovered one). |
| Last activity | Git (commit date) if available, else filesystem discovery (mtime) | `health.score_recent_activity`'s existing precedence (git first, mtime fallback) is the model's answer here — already implemented. |
| Health score | Derived engine result | Two *different* health scores exist today and must not be confused: `projects/health/compute_health_score` (Managed Project, DB-driven) and `discovery/health/compute_health` (Discovered Project, filesystem-driven). Only after Identity Resolution links the two would there be any reason to reconcile them into one displayed number — and even then, both should likely remain visible, not merged into a single silently-blended value. |
| Commercial readiness | Derived engine result (Discovery only) | No Managed Project equivalent exists today; this is a Discovery-only field until/unless a future sprint decides to promote it. |
| Recommendation | Derived engine result (Discovery), separately, Advisor recommendations (Managed Project) | Two distinct recommendation systems, already coexisting in this codebase (Advisor's DB-persisted, dismissable recommendations vs. Discovery's recomputed-every-scan one) — never merge their storage or dismissal semantics; they answer different questions ("what should I do about this Managed Project" vs. "what should happen to this folder"). |
| Notes | User input (Managed Project) | Never touched by Discovery. |
| Decisions | User input (Managed Project) | Never touched by Discovery. |
| Relationships (confirmed) | User input / Human Confirmation (Epic 1's `related_projects`/`dependencies`) — **decided authority, see §1.21** | Discovery never writes here directly, at any confidence level. |
| Relationships (candidate) | Derived (Discovery's `possible ...`-labeled candidates, §1.21) | Always subordinate to the confirmed row above; a UI must display candidate relationships distinctly (e.g. visually separate, always qualified "possible") and never merge them into the confirmed list. |

**General conflict-resolution rule** (restated from invariant 7): wherever
a field could plausibly be set by both a human and Discovery, **the
human-set value always wins and is never silently overwritten** —
discovered data may only fill a null/empty field, or be displayed
alongside the human value as a separate, clearly-labeled fact (e.g. "you
set priority: high" next to "Discovery health score: 62").

---

## 7. API Boundary (concepts only — no schemas)

| Future surface | Concepts it would expose | Concepts it must **never** expose directly |
|---|---|---|
| `POST /discovery/scans` | Discovery Root (by reference), Scan Run (created, `Requested`/`Queued` state) | The raw `DiscoveredProject`/`ScanResult` dataclasses (invariant 11) — always via a dedicated response model. |
| `GET /discovery/scans/{id}` | Scan Run (status, timing, error/warning summary) | Full Folder Candidate internals (not a public concept at all, §1.4). |
| `GET /discovery/scans/{id}/candidates` | Discovered Project (classification, move risk, health score, recommendation — the "safe to show a human" subset) | Raw file paths beyond what's needed for identification/action (e.g. full `absolute_path_refs` snippets are sensitive-adjacent — a summary count plus reasons is likely the right exposure level, not the raw matched text, though this is a UI/product decision for whoever designs the actual endpoint, not settled here). |
| identity-confirmation endpoints | Identity Candidate (evidence tier, reasons), Human Confirmation (the confirm/reject action itself) | Silent auto-confirmation of anything — every such endpoint's effect must be traceable to one specific Human Confirmation record (invariant 6/9). |
| Mission Control | Discovered Project summaries (via confirmed links to Managed Projects only — per invariant 5, an *unlinked* Discovered Project should not appear in Mission Control at all, since Mission Control is about Managed Projects a human is tracking) | Any Discovery internals for projects that were never confirmed/linked. |
| Advisor | Real signals (commit recency, dirty worktree, TODO count) *feeding new Advisor rules* on already-linked Managed Projects (per the original proposal §12) | Advisor must not gain a dependency on Discovery's own persisted schema directly — it should consume the same kind of enriched `project` dict it already does today, just with real values where `None` used to be, per the original proposal's design. |
| Project Health | Real `commit_dates`/`last_modified` feeding the *existing* `projects/health/commits.py`/`activity.py` signals (again, only for linked/confirmed Managed Projects) | The two health engines (Discovery's and Projects') must remain visibly separate outputs even once one feeds signals into the other — never silently collapsed into one score with no way to tell which parts came from where. |
| Workspace Graph | Workspace Graph Nodes/Edges (§1.25/§1.26), computed on demand | A fourth, differently-shaped graph API that could be confused with `/graph` or `/conversation-graph` — naming and route namespace need explicit disambiguation before this ships (§8). |

**Standing rule for all of the above** (restates invariant 11/12):
every future Discovery endpoint needs (a) a dedicated response model
separate from the internal dataclass, and (b) for any endpoint that
triggers a filesystem scan, server-side root validation against an
allow-list — neither is optional, and neither is designed in this
document (both are Sprint 2+ implementation work).

---

## 8. Alignment Review

### 8.1 Against current `dashboard/app/discovery/` architecture

Strong alignment on the parts that are already built: Folder Candidate =
`scanner.Candidate`; Discovered Project = `DiscoveredProject`; Repository
(as a field, not entity) = `GitInfo`; Technology/Structural/Risk/Health
Signal = the detector registry's `Findings` dataclasses and
`health.compute_health`'s breakdown; Recommendation = `recommendation.
engine.recommend`'s output; the `DETECTED→CLASSIFIED→SCORED→RECOMMENDED`
lifecycle = `PipelineStage` (Sprint 1.5), already implemented exactly as
described.

The main gap: **today's `DiscoveredProject` is one flat ~50-field
dataclass**, while this document (§1.14-§1.17) describes Technology/
Structural/Risk/Health Signal as conceptually distinct entities. This is
not a contradiction — it's the same "God Object" observation from the
prior architecture review, restated as a modeling concern: Sprint 1/1.5
correctly kept these as fields for now (splitting them prematurely would
have been its own kind of scope creep, per Sprint 1.5's explicit
"structural hardening only" mandate), but any future persistence design
(§5's `discovery_findings` table) should treat that splitting as the
natural next step, not a redesign.

### 8.2 Against `08_IMPORT_ENGINE_PROPOSAL.md`

Strong alignment: this document's Discovery Root ≈ the proposal's
`PROJECT_ROOT`; Identity Candidate/Human Confirmation formalizes the
proposal's §6.3/§16.3 "fuzzy-match, human reviews before write" flow;
the persistence model (§5) is a direct, mostly-unchanged elaboration of
the proposal's §14 schema, split further only where a real gap was found
(Repository decoupled from Discovered Project, per §1.7). No
contradictions found. One clarification this document adds that the
proposal didn't have: the proposal used "Project" for both what this
document calls Discovered and Managed Project, which was fine for a
single-author architecture proposal but needs the split now that more
than one document/audience depends on the vocabulary (see §8.5's
terminology table).

### 8.3 Against `09_DISCOVERY_ENGINE_SPRINT1_REPORT.md`

Every real example cited in this document (§1.3, §1.7, §1.8, §1.11,
§1.13, §1.16, §1.18, §1.22) was pulled directly from that report's actual
scan output — no invented examples. The report's own "known limitations"
(§7: the `OTROS - no proyectos` false positive, the 8 "Unknown" numbered
folders, the `AGUA-AZUL-APP` duplicate) map directly onto this document's
Unknown Folder (§1.13), Asset Collection (§1.10), and Project Container
(§1.8) sections respectively — this document does not resolve any of
those known issues, only gives them a stable vocabulary to be discussed
and fixed in.

### 8.4 Against the Projects, Advisor, and Graph domains

- **Projects (Epic 1)**: "Managed Project" is new *documentation*
  vocabulary for the existing `projects` table — no rename proposed to
  the table, API, or code. The existing `related_projects` field and
  `dependencies` table are the **decided, exclusive** owner of confirmed
  Project Relationships (§1.21, Decision C) — Discovery's own candidate-
  tier relationships are additive, never a duplicate or a replacement of
  these.
- **Advisor (Epic 2)**: Discovery's Recommendation is deliberately
  *not* modeled after Advisor's persist-many-candidates-and-dismiss
  pattern — it's winner-take-all, recomputed fresh (§2.7, §4.7), though
  Decision A now allows the winning value (not the full Advisor-style
  lifecycle) to be persisted. Whether Discovery ever adopts Advisor's
  full dismiss/accept model on top of that recorded value remains an open
  question (§10), not a settled divergence — Advisor's model may turn out
  to be the better fit once Discovery recommendations need to be
  "dismissed" by a human the same way Advisor's are.
- **Graph (Epic 3) and Knowledge Graph (Sprint 5)**: Workspace Graph
  (§1.25/§1.26) is explicitly a *third* graph, not an extension of either
  existing one — see the terminology-conflict flag below.
- **Database ownership convention**: This document's persistence model
  (§5) follows the established "each domain owns its own SQLite file"
  convention exactly — no shared-database proposal anywhere in this
  document.

### 8.5 Terminology conflicts and proposed clarifications

No existing code, table, or endpoint name is proposed to be renamed. The
following are documentation-vocabulary clarifications only:

| Current term (in code/docs) | Proposed term (this document) | Reason | Compatibility impact |
|---|---|---|---|
| "Project" (ambiguous — used for both `projects` table rows and, informally, discovered folders in `08_IMPORT_ENGINE_PROPOSAL.md`) | "Managed Project" (existing `projects` table rows) vs. "Discovered Project" (`DiscoveredProject`) | Two different lifecycles, ownership models, and data shapes have been sharing one English word across documents. | None — no code, table, column, or endpoint renamed. Documentation-only going forward. |
| "Workspace" (risk of assuming it means "a scanned root," given Discovery's own vocabulary needs) | "Workspace" stays exactly as-is (Project Intelligence category); "Discovery Root" is the new, separate term for a scanned path | Prevents inventing a conflicting second meaning for an already-loaded term. | None — clarifies, does not rename. |
| "Graph" (already used twice: Epic 3's `/graph`, Sprint 5's `/conversation-graph`) | "Workspace Graph" for any future Discovery-sourced graph | A third graph needs a third, unambiguous name from day one — retrofitting one later would be a breaking rename. | None yet (Workspace Graph doesn't exist in code) — this is a naming reservation for future work, not a current rename. |
| `discovery_source` (proposal §14, coarse per-row flag) | "Discovery Source" (this document, §1.23) reserved as the more general per-field provenance concept | The proposal's column is a reasonable first cut at the coarse (whole-row) version of a more general idea; naming them the same avoids inventing yet another synonym later, while flagging that the fine-grained version isn't built. | None — the proposal's column, if implemented, can keep its name; this document just notes it's a specific case of a more general concept. |

No other renames are proposed. Where this document introduces a wholly
new term (Identity Candidate, Human Confirmation, Discovery Snapshot,
Project Family, Workspace Graph Node/Edge), there is no existing code
term to conflict with — these are additions to the vocabulary, not
replacements.

---

## 9. Identity Resolution — Conceptual Model Only

**No algorithm is specified here.** This section only names the signals,
sorts them by evidentiary strength, and works through the real/plausible
cases a future algorithm must handle — matching the proposal's own
explicit deferral of this exact problem (§6.3: "fuzzy-match... a design
spike before Sprint 2 writes a single row," per the prior architecture
review).

### 9.1 Candidate identity signals

- Normalized filesystem path (current or historical)
- Git remote URL
- Repository identity (a specific `.git` history, potentially distinct
  from its current remote if the remote was ever changed)
- Project name (folder name, or a name declared in `package.json`/
  `pyproject.toml`)
- Package metadata (`package.json`'s `name` field, `pyproject.toml`'s
  `[project].name`, etc.)
- README identity (a README's title/first heading, if parseable)
- Deployment metadata (a live URL mentioned in README/config — the same
  signal `classifier.classify_commercial_readiness` already scans for)
- Known aliases (a human-declared "this folder is also known as X")
- Historical scan continuity (the same Discovery Root, same relative
  path, across consecutive Scan Runs — the strongest *continuity* signal,
  distinct from identity-matching-across-locations)
- Human-confirmed links (a prior Human Confirmation for this exact
  Discovered Project — the only signal that isn't really "evidence" at
  all, since it's already a decided fact)

### 9.2 Evidence strength tiers

- **Exact evidence**: The same Discovery Root + same relative path +
  same git remote as a previously-confirmed link. Effectively "this is
  the same folder we already know about."
- **Strong evidence**: A git remote matches an existing Managed Project's
  known remote (if that field existed), even at a different path — or an
  identical package-metadata name plus a matching README identity.
- **Weak evidence**: Name similarity alone (e.g. `role-content-factory`
  folder name vs. a Managed Project named "Content Factory") — plausible,
  not reliable enough to act on without review.
- **Conflicting evidence**: Two candidate Managed Projects both show
  moderate similarity (e.g. two Managed Projects both loosely named
  "Factory"), or a git remote matches one candidate while the name
  matches a *different* one — must be surfaced to a human as an
  ambiguous case, never auto-resolved by picking the higher score.

**Regardless of tier: confidence scoring alone must never automatically
merge or overwrite a Managed Project** (invariant 6). Even "exact
evidence" produces an Identity Candidate requiring a Human Confirmation
in the initial implementation — a fast, one-click confirmation for the
obvious cases, but a confirmation nonetheless, per the proposal's own
§16.3 rollout ("nothing is auto-written... for this first run only, to
build trust in the classifier").

### 9.3 Illustrative cases

- **Same project moved to another folder**: Old path gone, new path has
  matching git remote/commit history → strong evidence, still a proposed
  Identity Candidate, not an auto-link.
- **Duplicate copy**: Two folders, same git remote, both currently
  present on disk (e.g. a stale backup) → strong evidence *for each other*
  as a candidate `possible duplicate of` relationship (§1.21), but
  ambiguous *which one* (if either) should become the canonical Managed
  Project — exactly the strong-identity-plus-relationship-evidence
  combination §9.2/invariant 15 require before a future rule may ever
  emit the reserved `Merge with another project` action (§1.18), and even
  then only with Human Confirmation before anything is consolidated.
- **Archived copy**: A duplicate that also classifies `maturity=stale` —
  likely candidate for the Archive *action* on the non-canonical copy,
  decided by a human, not inferred automatically from staleness alone.
- **Fork**: Same original codebase, divergent git history/remote —
  weak-to-conflicting evidence; name similarity may be high while git
  identity clearly differs. At most a candidate `possible fork of`
  relationship (§1.21); should not be treated as the same project or
  proposed for `Merge with another project`.
- **Parent container with one same-named child**: Already implemented,
  not merely conceptual — `apply_container_child_overrides` (§1.8). Not
  an identity-resolution case at all in today's implementation (it's
  structural, not cross-Scan-Run identity), but conceptually adjacent
  enough to note here: this is a case Discovery already resolves
  *without* needing Identity Resolution, because both folders are visible
  in the *same* Scan Run.
- **Unrelated projects with similar names**: The conflicting-evidence
  case (§9.2) — must never auto-merge on name alone.
- **One project containing multiple repositories**: The Repository/
  Discovered-Project 1:1 assumption gap already flagged in §1.7 — Identity
  Resolution for this case isn't "which Managed Project does this link
  to," it's "how many Repository entities does this one Discovered
  Project actually have," a prerequisite question this document does not
  resolve.
- **Multiple folders belonging to one product family**: The Project
  Family case (§1.22), illustrated by the real `ROLE Commerce Factory`
  example — identity resolution here proposes a candidate `possible
  member of project family` relationship at the *family* level, not
  folder-to-Managed-Project, and (per Decision C) only becomes an
  authoritative Project Family once a human confirms it.

---

## 10. Open Architectural Questions Requiring a Human Decision

Four of the original ten questions here were resolved by the
architectural review recorded in `DECISIONS.md` (Decisions A/B/C and the
health-ownership clarification) — kept below, marked **Resolved**, for
traceability rather than deleted, since the reasoning behind a decision
matters as much as the decision itself.

1. Should the "Discovered Project" record, once persisted, remain a
   denormalized flat row (mirroring today's dataclass) or be split into
   normalized `discovery_findings` rows per §8.1's observation? Affects
   query complexity vs. long-term extensibility. **Still open.**
2. ~~Should Discovery adopt Advisor's "persist every candidate, dedupe,
   allow dismiss/complete" model for Recommendations, or keep today's
   winner-take-all, recomputed-fresh model?~~ **Resolved (Decision A).**
   Sprint 2 may persist the winning Recommendation's *value* (`action`,
   `reasons`, timestamp, rule/engine version) as part of a Scan Run or
   Snapshot; full lifecycle management (dismiss/accept/snooze/history UI)
   is explicitly deferred, not decided against forever — **still open**:
   whether that fuller lifecycle is ever built, and whether losing
   candidates (not just the winner) are ever retained.
3. ~~Is `Merge with another project` ever going to have a rule that
   produces it, or should the six-action vocabulary be reduced to five?~~
   **Resolved (Decision B).** It stays in the vocabulary, reserved and
   inactive, until a rule can show both strong identity evidence *and*
   relationship evidence (invariant 15) — not deleted, not required to be
   implemented on any timeline.
4. ~~Should Project Relationship unify with Epic 1's existing
   `related_projects`/`dependencies`, or remain separate?~~ **Resolved
   (Decision C).** Confirmed relationships are owned exclusively by the
   Projects domain (extending, not duplicating, the existing fields);
   Discovery owns only the candidate tier (`possible ...`-labeled), which
   becomes confirmed solely through Human Confirmation.
5. ~~Should Project Family be a Discovery-owned concept or a
   Projects-domain one?~~ **Resolved (Decision C), same split as #4:**
   candidate Project Families are Discovery-owned; confirmed ones belong
   to the Projects domain.
6. How aggressively should Identity Resolution's "reject fatigue" be
   addressed (§4.5) — should a rejected Identity Candidate (or a rejected
   Discovery Candidate Relationship) ever be re-proposed automatically,
   and under what new-evidence threshold? **Still open.**
7. What is the actual retention policy for `discovery_snapshots` and
   `identity_confirmations` (§5) — unlimited, time-boxed, or
   count-boxed per Discovery Root? A product/ops decision informed by how
   large these tables would realistically get. **Still open.**
8. ~~Should the two independently-computed "health scores" ever be
   reconciled into one displayed number once a link is confirmed?~~
   **Resolved: no, not silently** (§2.13, §1.17, invariant 17). They
   remain two separate, separately-labeled numbers; **still open**:
   whether a *separately-designed, versioned* composite is ever built on
   top of them, and if so, exactly how it would be computed.
9. Should the future Workspace Graph (§1.25/§1.26) be its own API
   namespace, or could it instead be additive node/edge types merged into
   Epic 3's existing `/graph`? The naming-collision risk (§8.5) argues for
   separate; query/UX convenience might argue for merged — genuinely
   undecided here. **Still open.**
10. At what point (if ever) does a Discovery Root's registration (§4.1)
    need its own confirm/reject step, the same way an Identity Candidate
    does — i.e., should pointing Discovery at a new root be a lightweight
    action (today's model: just pass `--root`) or a reviewed one (given
    invariant 12's server-approved-roots requirement for a future API)?
    **Still open.**

---

## 11. Where to go next

- [[08_IMPORT_ENGINE_PROPOSAL]] — the original architecture proposal this
  document formalizes vocabulary for.
- [[09_DISCOVERY_ENGINE_SPRINT1_REPORT]] — the real scan results every
  example in this document is drawn from.
- `docs/product/DECISIONS.md` — "A formal Discovery Engine Domain Model
  was written before any persistence, identity resolution, or API work
  began" entry records why this document was written now, before
  persistence, plus the recommendation-persistence, reserved-`Merge`,
  relationship-ownership, and health-separation decisions layered on top
  of it after review.
- [[07_ROADMAP]] — Sprint 1/1.5 entries; Sprint 2+ is not planned here.
