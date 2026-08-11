# 08 — Import Engine: Architecture Proposal

Status: **Sprints 1-5 + C1 SHIPPED** — see `CHANGELOG.md` ("Discovery
Engine, Sprint 1", "Workspace Adoption, Sprint 2", "Project Boundary,
Sprint 3", "Project Intelligence Wiring, Sprint 4", "Project Unification,
Sprint 5", "Project Context, Sprint C1") and [[07_ROADMAP]].
`dashboard/app/discovery/` remains CLI-only and read-only per §18 Phase 1.
`dashboard/app/workspace/` (Sprint 2, §18 Phase 2-3) adds the first
writable layer on top of it: a cached scan + a per-folder overlay
(priority/business value/status/tags/notes/ignored/boundary override),
the `/workspace/*` API, and a Workspace page with Adopt/Ignore/Review/
Rescan — deliberately scoped down from §14/§15's "write into the
`projects` table" design to a separate, additive overlay table instead
(see this doc's §14 note below the original text). Sprint 3 adds
`dashboard/app/discovery/boundary/`: a project-boundary/hierarchy model
(top-level project / nested repository / component / documentation /
asset library / internal folder / excluded / non-project) so the
Workspace page groups real project structure instead of a flat list, plus
configurable exclusions — this was requested and scoped independently of
§6/§19's original wording, not a literal implementation of either. Sprint 4
wires that data into Projects/Home/Advisor/Assets (§12's original "Health/
Advisor Integration" and §13's "Mission Control Integration" sections,
reinterpreted at Sprint-4 scope — a Workspace Advisor sibling to Epic 2's,
not a Mission Control rewrite, which remains explicitly out of scope): a
Next Action extractor, an asset discovery index, a unified Recent Activity
feed, and Home portfolio aggregation. Sprint 5 removes the remaining
conceptual split between manually-created and discovered/adopted
projects via a canonical Project Identity bridge (`app/workspace/
identity.py`) and a Resume Work orchestration
(`app/workspace/resume.py`) — not part of this document's original
proposal, but the natural completion of Sprint 4's "known gap" (AI
Sessions couldn't be created for a purely-discovered project). See
`docs/architecture/09_DISCOVERY_ENGINE_SPRINT1_REPORT.md` /
`10_WORKSPACE_ADOPTION_SPRINT2_REPORT.md` /
`11_PROJECT_BOUNDARY_SPRINT3_REPORT.md` /
`12_PROJECT_INTELLIGENCE_WIRING_SPRINT4_REPORT.md` /
`13_PROJECT_UNIFICATION_SPRINT5_REPORT.md` /
`14_PROJECT_CONTEXT_SPRINT_C1_REPORT.md` for what actually shipped in
each sprint vs. what this document originally proposed. Sprint C1 (a
"Consolidation" sprint, not part of this document's original phases) adds
one composition layer, `app/project_context/`, over the identity bridge
Sprint 5 built — a single builder every page can request a project's full
context from, instead of each independently reassembling a subset of it.
Mission Control ranking (§13) is **SHIPPED as of Sprint C5** — see
`CHANGELOG.md` ("Mission Control, Sprint C5") and [[07_ROADMAP]] — but not
as a literal implementation of §13's proposal below. Sprint C5 built one
new endpoint, `GET /mission-control` (`app/mission_control/service.py`),
composing `ProjectContext`, Home's existing ranking, the Workspace
Advisor, Recent Activity, and the Daily Session domain into a "what should
I work on today" home page; §13's own "last worked on / ranked by business
value" framing is superseded by that real implementation rather than
built as separately described here. §13 is left below unedited as a
historical record of the original proposal.
Author framing: Chief Product Architect review, requested 2026-07-31.

---

## 1. Problem Statement

ROLE OS was designed around a "record a conversation, extract knowledge from it"
loop: ChatGPT export → Builder → knowledge DB → Project Intelligence records that
a human fills in by hand. That loop assumes the user's work *starts* inside ROLE
OS.

In reality the work already exists, in full, on disk, under

```
C:\Users\rolev\My Drive (rolevc@gmail.com)\1 - IA PROJECTS\
```

Every morning question the owner actually asks —

- What am I building?
- What should I do next?
- What's blocking me?
- Which project matters most commercially?
- Where did I leave off yesterday?

— is answerable from the filesystem and git history *today*, without ROLE OS.
ROLE OS instead asks the user to re-type all of it into empty forms. That is
backwards, and it is why Projects, Assets, and the graph are empty: nobody is
going to hand-enter six real projects' worth of README/roadmap/todo/asset data
that already lives in files. The system is idle not because the user hasn't
used it enough, but because its only intake path is manual data entry.

## 2. Current Architecture (verified against code, not assumed)

| Area | What it actually does | Evidence |
|---|---|---|
| Project schema | `id, workspace_id, name, description, status, health_score, priority, tags, owner, notes, decisions, todos, deliverables, assets, prompts, conversations, related_projects` — **no path field** | `dashboard/app/projects/models.py:53-75`, `db.py:37-57` |
| Project CRUD | `POST /pi/projects` takes only typed-in fields (name, workspace, description, status, priority, tags, owner) | `routers/pi/projects.py`, `models.py:33-40` |
| "Import" feature | Parses a ChatGPT `conversations.json` export into `ImportedConversation` rows. Never touches the filesystem beyond the uploaded bytes. Does **not** create or link Projects. | `imports/parser.py:9-13`, `imports/service.py:26`, `docs/product/CHANGELOG_PRODUCT.md:116-117` |
| Launcher | Builds a prompt string + a list of web URLs (claude.ai / chat.openai.com) for the browser to open. Explicitly documented as doing zero OS-level automation. | `routers/launcher.py:3-8, 34-60` |
| Health: commits | Docstring: *"ROLE OS has no git integration yet... callers pass `commit_dates=None`"* | `projects/health/commits.py:1-10` |
| Health: activity | Scores the DB row's `updated_at` (last time a human edited the record) — not filesystem mtimes | `projects/health/activity.py` |
| Health: decisions/deliverables/todos | Score manually-entered collection items | `projects/health/{decisions,deliverables,todos}.py` |
| Advisor rules | Read only DB fields: `priority`, `status`, `updated_at`, `deliverables`, `todos`, `tags`, cross-project DB relations. No file I/O anywhere. | `advisor/engine.py`, `advisor/rules/*.py` |
| Graph | Builds nodes/edges from the same manually-entered collections (`related_projects`, `assets`-as-JSON) | `graph/builders/project_graph.py:25-88` |
| Asset model | **No `Asset` class/table exists.** "Asset" is a label on a free-form JSON blob (`text`/`name`/`url`), same shape as a note. | grep across `dashboard/app`, `docs/architecture/04_DATA_MODEL.md:22` |
| Workspace-dir awareness | `ROLE_OS_WORKSPACE_DIR` is an **opt-in launcher switch pointing at one hardcoded path** — explicitly documented as *not* automatic detection, and it does not prefer a real workspace even when one exists on disk. | `docs/product/DECISIONS.md:396-403` |

Conclusion: every subsystem that could plausibly know about real projects —
schema, CRUD, health, advisor, graph — is wired exclusively to hand-entered
DB rows or to conversation text extracted from a single ChatGPT archive. There
is no code path today that reads a folder on disk and produces a Project
record. The claim in the brief is fully correct, not just directionally.

## 3. Why It Fails For This Workflow

The owner's mental model is project-first: open the folder, open the terminal,
open the code. ROLE OS's mental model is knowledge-first: import a
conversation, extract facts, manually curate a project around them. These are
different graphs with different roots. Knowledge-first works if the "product"
is a personal wiki. It fails the moment the real product of the day is six
folders of code, docs, and git history that ROLE OS has no way to look at.

The fix is not "add more import formats." It's recognizing that **the
filesystem is the source of truth**, and the DB (Projects, health, advisor,
graph) should be a *derived cache* over it — refreshable, not hand-maintained.

## 4. Desired User Experience

1. First run (or any run, via a "Rescan" button): ROLE OS walks the project
   root, finds every real project folder, and populates Projects — name,
   root path, git status, README/roadmap/todo excerpts, languages, last
   activity — with zero typing.
2. Mission Control opens to: *last touched project*, *ranked by business
   value / momentum*, *what's stale*, *what's blocked* — computed from real
   signals (last commit, mtimes, TODO/FIXME counts, README claims), not from
   fields nobody filled in.
3. Existing manual data (notes, decisions, priority override, commercial
   tags) is layered *on top of* the discovered record and never destroyed by
   a rescan.
4. `OTROS - no proyectos` is respected as an exclusion list, not scanned as
   projects.

## 5. Import Engine Architecture

Reuse, don't replace. The Import Engine is a **new sibling module**,
`dashboard/app/discovery/`, that sits next to the existing `imports/` module
(ChatGPT conversation import stays as-is — different job, same "ingest
external truth into the DB" shape). It writes into the *existing* Projects
table via one new nullable column and one new child table (§14), and calls
the *existing* health/advisor/graph code unchanged — those already consume
`project` dicts and don't care whether the dict was hand-typed or discovered.

```
discovery/
  scanner.py        # walks PROJECT_ROOT, yields candidate folders
  detectors.py       # git? package.json? pyproject? README/ROADMAP/etc. presence
  metadata.py        # per-project extraction (languages, framework, docs excerpts)
  git_reader.py      # last commit, commit count, branch, remote — via `git log`/pygit2
  classifier.py       # is this a real project? confidence score, project "kind"
  health_signals.py  # feeds real signals into existing projects/health/* scorers
  service.py          # orchestrates: scan -> extract -> classify -> upsert
  models.py           # DiscoveredProject, ScanResult dataclasses
```

Nothing in `projects/`, `advisor/`, `graph/`, or `routers/pi/` needs to be
rewritten. They gain new *inputs*, not a new shape.

## 6. Discovery Pipeline

1. **Root scan**: `os.scandir(PROJECT_ROOT)`, depth-limited (top-level +
   one level for monorepo-style `packages/*`). Skip `OTROS - no proyectos`,
   dotfolders, `node_modules`, `.venv`, `__pycache__`, anything in a
   configurable ignore list.
2. **Candidate filter**: a folder is a project candidate if it contains
   *any* of: `.git`, `package.json`, `pyproject.toml`, `requirements.txt`,
   `README*`, or more than N files. This prevents stray folders (a single
   PDF dropped at the root) from becoming "projects."
3. **Identity resolution**: match discovered folder → existing Project row
   by `root_path` if already imported; otherwise by fuzzy name match against
   existing hand-created Projects (so a project someone already typed in
   manually gets *linked*, not duplicated); otherwise create new.
4. **Incremental rescan**: store `last_scanned_at` and folder mtime; skip
   unchanged folders on subsequent scans for speed.

## 7. Metadata Extraction Pipeline

Per candidate folder, cheap and read-only:

- **Docs**: locate `README*`, `ROADMAP*`, `CHANGELOG*`, `TODO*`, `docs/`
  — read first N lines/headings for a summary, don't parse deeply at scan
  time (defer deep parsing to on-demand "open project" view).
- **Languages/framework**: file-extension histogram + marker files
  (`package.json`→Node, `pyproject.toml`/`requirements.txt`→Python,
  `Cargo.toml`→Rust, `*.csproj`→.NET, `next.config.*`→Next.js, etc.). No
  need for a full language-detection library initially — marker files plus
  extension counts cover this project root well.
- **Tests**: presence of `tests/`, `test_*.py`, `*.test.ts`, `pytest.ini`,
  `jest.config.*`.
- **Images/logos**: scan `assets/`, `public/`, `static/`, repo root for
  common image extensions; flag files matching `logo*`/`icon*`/`favicon*`
  as brand assets specifically.
- **Last modified**: max file mtime under the folder (excluding ignored
  dirs), cheap via `os.stat` walk with early skip of `.git`/`node_modules`.

## 8. Project Classification

A lightweight, explainable scoring function (not ML) that assigns:

- **Confidence** it's a real project (0–1) from signals in §6.2 — surfaced
  in the UI as "auto-discovered, please confirm" below a threshold, and
  silently accepted above it. This keeps a human in the loop for edge cases
  without requiring one for the common case.
- **Kind**: `code-app`, `content/knowledge`, `client-deliverable`, `internal
  tool`, `unknown` — inferred from marker files + folder-name heuristics,
  editable by the user afterward.
- **Commercial readiness** (§11) as a separate axis, not folded into kind.

## 9. Asset Discovery

Today "Asset" is a free-text JSON blob with no path. Proposed:
a real `discovered_assets` child table (one project → many rows), each
row a **path + type + size + mtime**, populated by the same scan pass that
already walks the folder for §7. Types: `image`, `logo`, `document`,
`dataset`, `design-file`, `other`. The existing manual "assets" JSON field
on Project stays for user-added links/notes about assets that aren't local
files (e.g. a Canva URL) — the two are additive, not a migration.

## 10. Repository Discovery

For any candidate folder with `.git`:

- Read `HEAD`, current branch, remote URL (origin), via `git` CLI subprocess
  (`git -C <path> log -1 --format=...`, `git remote get-url origin`) —
  no new dependency required, `git` is already used to develop ROLE OS
  itself, so it's a safe assumption on this machine. A `pygit2`/`GitPython`
  dependency is a later optimization only if subprocess overhead matters at
  the project counts involved (single digits to low tens).
- Extract: last commit hash/date/message, commit count, contributor count
  (informational only, single-user machine), dirty/clean working tree.
- This directly unblocks `projects/health/commits.py`, which today is a
  documented no-op (`commit_dates=None`) purely for lack of a data source —
  the scoring logic itself doesn't need to change.

## 11. Health Calculation

Extend, don't replace, `projects/health/`:

- `activity.py` gains a real signal: filesystem `last_modified` in addition
  to (or instead of, once discovery is live) the DB `updated_at` proxy it
  uses today.
- `commits.py` gets real `commit_dates` from §10 instead of `None`.
- `decisions.py` / `deliverables.py` / `todos.py` stay DB-driven for
  hand-entered items, but gain a discovered supplement: TODO/FIXME comment
  counts and unchecked `- [ ]` markdown checkboxes in ROADMAP/TODO files as
  an additional weak signal, clearly labeled as "auto-detected" vs. "you
  logged this."
- **Commercial readiness** is a new axis, not a health sub-score: derived
  from presence of a deployed URL / production config, a paying-client
  marker (contract/invoice references, if the user opts to tag them),
  README claims of "live"/"launched", and recency of commits. This stays
  a simple weighted heuristic, transparent and overridable — this is
  exactly the kind of judgment call that should default to a suggestion,
  not an assertion.

## 12. Advisor Integration

No change to `advisor/engine.py`'s contract: it already consumes a
`RuleContext` built from `project` dicts. Discovery just makes those dicts
richer (`root_path`, real `commit_dates`, `last_modified`, `discovered_assets`
count). Add 1-2 new rules that only make sense with real signals:

- `dirty_worktree_stale.py`: uncommitted changes sitting for N+ days —
  "you probably stopped mid-thought here."
- `no_recent_activity_but_was_hot.py`: high commit velocity in the last 90
  days, then silence — different from `stale_project.py`'s generic staleness,
  this flags a *drop-off*, which is a stronger "you meant to come back to
  this" signal.

## 13. Mission Control Integration

The morning-open view becomes: **Last worked on** (max across all projects'
`last_modified`/last commit) pinned at top, then a ranked list by a combined
score of (recency, commercial-readiness, advisor-flagged urgency). This is a
new read-only aggregation endpoint/view over existing Project + health data —
no new UI framework, it's a different sort/filter over what Mission Control
(if it exists as a view) or the Projects list already renders.

## 14. Database Changes

Minimal, additive, backward-compatible:

```sql
ALTER TABLE projects ADD COLUMN root_path TEXT;             -- nullable, unique when set
ALTER TABLE projects ADD COLUMN discovery_source TEXT;       -- 'manual' | 'discovered'
ALTER TABLE projects ADD COLUMN last_scanned_at TEXT;
ALTER TABLE projects ADD COLUMN last_commit_at TEXT;
ALTER TABLE projects ADD COLUMN last_modified_at TEXT;

CREATE TABLE discovered_assets (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(id),
  path TEXT NOT NULL,
  asset_type TEXT,          -- image | logo | document | dataset | design-file | other
  size_bytes INTEGER,
  modified_at TEXT
);

CREATE TABLE discovered_repos (
  project_id TEXT PRIMARY KEY REFERENCES projects(id),
  branch TEXT,
  remote_url TEXT,
  last_commit_hash TEXT,
  last_commit_at TEXT,
  last_commit_message TEXT,
  commit_count INTEGER,
  is_dirty INTEGER
);
```

No existing column is renamed or removed. Existing manually-created Projects
simply have `root_path IS NULL, discovery_source = 'manual'` and keep working
exactly as today.

## 15. API Changes

Additive only:

- `POST /discovery/scan` — trigger a scan of `PROJECT_ROOT` (or a given
  path), returns a `ScanResult` summary (found/updated/skipped counts).
- `GET /discovery/candidates` — preview candidates below the confidence
  threshold, awaiting confirmation, before they're written as Projects.
- `POST /discovery/candidates/{id}/confirm` / `/reject`.
- `GET /pi/projects/{id}` response gains optional fields (`root_path`,
  `repo`, `discovered_assets`) — additive to the existing schema, no
  breaking change for current consumers.
- Existing `POST /pi/projects` (manual create) is untouched — manual entry
  remains supported for projects that aren't on this disk (e.g. ideas).

## 16. Migration Strategy

1. Ship schema migration (§14) — additive, zero downtime, no data loss.
2. Ship `discovery/` module behind a settings flag, default **off**.
3. Run first scan manually via the new endpoint against
   `1 - IA PROJECTS`, review candidates in the preview endpoint before
   confirming — nothing is auto-written to a live Project until confirmed,
   for this first run only, to build trust in the classifier.
4. Once confidence in the classifier is established (a handful of scans
   with no bad matches), flip default confidence threshold so high-confidence
   candidates auto-confirm and only ambiguous ones need review.
5. Existing hand-entered Projects (if any point at a real folder by name)
   get `root_path` backfilled via the fuzzy-match step in §6.3, reviewed
   once, not silently overwritten.

## 17. Risk Analysis

| Risk | Mitigation |
|---|---|
| Google Drive sync folder = slow/locked file access, false "modified" signals from sync churn | Use mtime with a debounce window (ignore changes < 5 min old); read-only access, never write into project folders |
| Misclassifying a non-project folder as a project | Confidence threshold + manual confirm step (§16.3) |
| Scanning secrets-containing folders (`.env`, credentials) and surfacing paths/snippets in UI | Discovery reads file *names*/*metadata* only for non-doc files; only README/ROADMAP/CHANGELOG/TODO content is read as text, and those are conventionally non-secret. Never index `.env*`, `*key*`, `*credential*` file contents. |
| Duplicate Projects if fuzzy-match misses an existing manual entry | Manual review step before write; `root_path` uniqueness constraint prevents re-import duplication on rescan |
| Large git histories slow to read | `git log -1` only for the summary signal; deeper history only on-demand when a project is opened |
| Scope creep into a full IDE/file-indexer | Explicitly bounded to the metadata in §7 — no code search, no full-text indexing, in this phase |

## 18. Incremental Rollout Plan

- **Phase 0** (this doc): architecture sign-off, no code.
- **Phase 1**: schema migration + `discovery/scanner.py` + `detectors.py`,
  CLI-only (`python -m discovery.service scan`), prints results to console.
  No DB writes yet — validates the candidate list against the real 5-6
  project folders before anything touches the UI.
- **Phase 2**: `metadata.py` + `git_reader.py`, write to `discovered_assets`
  / `discovered_repos`, still preview-only via CLI or a simple JSON endpoint.
- **Phase 3**: `classifier.py` + `/discovery/scan` and `/discovery/candidates`
  API, confirm/reject flow wired into the existing Projects UI.
- **Phase 4**: wire real signals into `health/commits.py` and
  `health/activity.py`; add the two new advisor rules (§12).
- **Phase 5**: Mission Control "last worked on / ranked" view (§13); flip
  auto-confirm default per §16.4.

Each phase is independently shippable and reversible (feature-flagged), and
none of them touch `advisor/engine.py`'s rule contract or `graph/builders/`
signatures — they only enrich the data those already consume.

## 19. Recommended Sprint Breakdown

- **Sprint 1**: Phase 1 + Phase 2 (scanner, detectors, metadata, git reader,
  schema migration). Deliverable: a CLI report showing real data for all
  projects under `1 - IA PROJECTS` (excluding `OTROS - no proyectos`).
- **Sprint 2**: Phase 3 (classifier + API + confirm/reject UI). Deliverable:
  Projects list populated from real folders, reviewable and confirmable.
- **Sprint 3**: Phase 4 (health + advisor wiring). Deliverable: health
  scores and advisor nudges reflect real commit/activity/todo signals.
- **Sprint 4**: Phase 5 (Mission Control ranking view, auto-confirm
  threshold flip). Deliverable: opening ROLE OS answers the five morning
  questions from §1 without any manual data entry.

## 20. Definition of Done

- Every real project folder under `1 - IA PROJECTS` (excluding `OTROS - no
  proyectos`) has a corresponding Project row with `root_path` set,
  populated without the user typing anything, on first scan.
- Each such Project shows: languages, framework, git branch, last commit
  date/message, last modified date, discovered asset count, and README/
  ROADMAP/TODO excerpts — all sourced from disk.
- `projects/health/commits.py` receives real `commit_dates` (no longer
  `None`) for every git-backed project.
- Advisor produces at least one real, non-generic recommendation per active
  project, sourced from a signal that didn't exist before this work (commit
  recency, dirty worktree, TODO count).
- Opening Mission Control shows "last worked on" and a value-ranked list
  without the user having created a single manual Project record.
- A rescan is idempotent: re-running it against unchanged folders produces
  no duplicate rows and no data loss on previously-entered manual fields
  (notes, decisions, priority overrides).
- Manual Project creation (`POST /pi/projects`) still works unmodified, for
  projects that intentionally don't live on this disk.
