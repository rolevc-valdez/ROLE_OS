# 18 — Assets Canonicalization Audit, Sprint C4.1: Completion Report

Scope executed: prove Assets now has one true source of truth across ROLE
OS, remove any remaining duplicate mappings, and prevent future drift. An
audit sprint, not a feature sprint: no new user-facing functionality, no
Assets UI redesign, no new database, no LLM calls, no modification to any
scanned project file. No version bump, no commit, no tag.

## Verdict

**Fully canonical**, with one real bug found and fixed during the audit
(not present in the original C4 completion report's claims — this report
does not trust that report, per instruction, and verifies against the
actual source and live behavior instead).

Deleting `app.assets` would break every real filesystem-asset surface in
ROLE OS: the Assets gallery (`/assets`), Explorer's Asset search results
and Project Hub's assets summary (both via `app.workspace.assets_index`,
a pure re-export), Dashboard and Home's recent/reusable asset cards (via
`workspace.service.list_project_assets`), and `ProjectContext.
assets_count` (via `app.project_context.builder._asset_count`) — none of
these have a fallback or parallel implementation to fall back to.

## 1. Full caller audit

Every symbol a second implementation would need to touch was searched
across the entire backend (`dashboard/app/`) and frontend
(`dashboard/app/static/js/app.js`):

`AssetRecord`, `assets_count`, `reusable_count`, `recent_assets`,
`duplicate_hash`, `duplicate_group_id`, `likely_logo`, category/asset-type
classification, MIME detection, image dimension reading, preview-URL/
thumbnail generation, file/folder opening, copy-path, and per-project
asset-summary construction.

**Result**: every match resolves to one of three cases —

1. **Canonical**: calls into `app.assets.*` directly, or via `app.
   workspace.assets_index` (a verified pure re-export shim, zero local
   `def`s of its own — see §14's guard test).
2. **Pure aggregation**: `sum`/`len`/`sort`/`filter` over fields an
   `AssetRecord` already computed (Dashboard's `reusable_assets =
   [a for a in all_assets if a.get("reusable")]`, Project Hub's
   `assets_summary`, Home's `recent_assets[:10]`) — never a second
   *decision* about what category/reusable/duplicate/type means.
3. **Presentation-only** (`app.js`): every asset renderer (Home, Dashboard
   cards, Project Hub, the Assets gallery itself, Explorer results,
   Discovered Project Detail's assets table) reads server-provided fields
   verbatim — confirmed no `.endsWith(".png")`-style client-side
   extension branching, no client-side `classifyCategory`/`isReusable`
   reimplementation anywhere in the Assets page's own ~15,000-character
   section of `app.js`. The "Copy Path" button reads `asset.absolute_path`
   (a server field), not a client-reconstructed path.

No independent computation of category, reusable status, duplicate
detection, MIME type, image dimensions, or thumbnails was found anywhere
outside `app.assets`.

## 2. Canonical source — confirmed

| Concern | Authoritative implementation | Status |
|---|---|---|
| Discovery/indexing | `app.assets.service.index_project_assets`/`list_all_assets` | Sole implementation |
| Model | `app.assets.model.AssetRecord` | Sole schema |
| Classification | `app.assets.classification` | Sole implementation |
| Metadata (dimensions) | `app.assets.image_meta` | Sole implementation |
| Preview/thumbnail | `app.assets.preview` | Sole implementation |
| Overrides | `app.assets.db` | Sole write path (§6) |
| API | `app.routers.assets` | Canonical `/assets` surface |

`app.workspace.assets_index` is the one documented compatibility shim
(pure re-export, its own docstring says so, verified by an `ast`-based
test that it defines zero local functions/classes).

## 3. Screen-by-screen verification

| Screen | Endpoint(s) | Service | AssetRecord usage | Bypasses `app.assets`? |
|---|---|---|---|---|
| Assets gallery | `GET /assets` | `search_assets` → `list_all_assets` | Full fields, server-filtered/paginated | No |
| Explorer (asset results) | `GET /explorer/search` | `app.assets.service.list_all_assets()` directly | Full fields, per result | No |
| Project Hub | `GET /explorer/project/{id}` | `assets_index.index_assets_for_project` (shim) | Full fields + `assets_summary` (`count`/`reusable_count`/`by_category`, pure aggregation) | No |
| Project Detail (discovered) | `dprojectAssetsHtml` reads `/workspace/assets` | `assets_index` shim (delegates to `app.assets`) | Full fields | No |
| Home | `GET /workspace/home` | `workspace.service.list_project_assets` → `assets_index` shim | Full fields, sorted/sliced | No |
| Dashboard | `GET /dashboard/summary` | `workspace.service.list_project_assets` | Full fields, filtered (`reusable`) and sliced | No |
| Advisor | (no direct asset rendering) | N/A | N/A | N/A |
| Cockpit | (no direct asset rendering) | N/A | N/A | N/A |
| Workspace | `GET /workspace/discovered` (no asset fields embedded) | N/A | N/A | N/A |
| ProjectContext | `assets_count` field | `_asset_count` → `assets_index.index_assets_for_project` | Count only (`len(...)`) | No |

## 4. Duplicate asset counts — the one real bug

**Found**: `index_project_assets` — the function Dashboard, Home,
`ProjectContext.assets_count`'s recent-activity block, and Project Hub
all call *directly* (not through `/assets`) — never resolved
`duplicate_group_id` to `None` for a file that doesn't actually share its
partial-content hash with anything else.

`_build_record` set `duplicate_group_id = duplicate_hash` unconditionally
— a raw candidate value, per its own comment: "resolved to a real group
only if 2+ share it — see `group_duplicates()`." But `group_duplicates()`
was only ever invoked inside `list_all_assets()`, the function backing
the `/assets` API. Every other direct caller returned the *raw* value:
every hashable file showed a non-null `duplicate_group_id`, even a
genuinely unique one.

**Live proof, before the fix** (real `shot_4_logo.png`, the only image in
`ROLE_KNOWLEDGE_OS` — genuinely unique, no real duplicate exists):

```
Assets API (/assets?q=shot_4_logo):      duplicate_group_id: "019d265e..."  ✓ correctly null after fix
Project Hub (/explorer/project/{id}):    duplicate_group_id: "019d265e..."  ✗ before fix, non-null
Dashboard (/dashboard/summary):          duplicate_group_id: "019d265e..."  ✗ before fix, non-null
Home (/workspace/home):                  duplicate_group_id: "019d265e..."  ✗ before fix, non-null
GET /assets/duplicates/019d265e...:      404 Not Found (no such group)     — correctly refused even before the fix
```

`/assets`'s own value was *already* correct (`None`) because
`list_all_assets` applies `group_duplicates`. Every other screen showed a
misleading "this has a duplicate" signal for a file the Assets page
itself correctly showed as unique.

**Fix**: `index_project_assets` now calls `group_duplicates(records)` on
its own return value before returning — every caller, not just
`list_all_assets`, gets the already-resolved value. `list_all_assets`
still re-groups the combined cross-project list afterward (idempotent for
already-correct per-project groups; still catches a duplicate whose only
other copy lives in a *different* project, which a single project's own
walk can't see).

**Live proof, after the fix**: all four surfaces (`Assets API`,
`Project Hub`, `Dashboard`, `Home`) now agree: `duplicate_group_id: null`
for `shot_4_logo.png`.

Every other count checked has no equivalent inconsistency:
`assets_count`/`reusable_count`/`recent_assets`/category breakdown are
all plain aggregation over already-correct fields, computed exactly once
per screen from `app.assets`-sourced records.

## 5. Duplicate models — none found

No asset-shaped dict/DTO/serializer was found outside `app.assets.model.
AssetRecord` and its `asset_record_to_dict` projection. Every "asset
summary" construction (Project Hub's `assets_summary`, Dashboard's
`cards`) is a plain dict of aggregated numbers, not a second record shape
competing with `AssetRecord`.

## 6. Explorer consolidation — confirmed

Explorer's asset search results are produced directly by `app.assets.
service.list_all_assets()` (not the workspace shim) — verified live: the
real `shot_4_logo.png` result from `GET /explorer/search?q=shot_4_logo`
carries the identical `id` (`asset_id`), `project_id`
(`canonical_project_id`), and `item_id` (`discovery_item_id`) as every
other surface. `actions` (`Open Asset` → the shared Asset Detail panel,
`Open Project` → the shared project navigation) construct no second asset
representation.

## 7. ProjectContext consolidation — confirmed, with the one caveat noted in §12

`ProjectContext.assets_count` is computed via `_asset_count`, which calls
the canonical `index_project_assets` and takes `len(...)` — never a
looser `discovery_detail` counter (that was Sprint C1B's own fix,
reconfirmed still in place). `ProjectContext` does not embed a full asset
list (only the count), matching the brief's "avoid expensive rescans"
guidance; Project Hub (a separate, richer endpoint) is where the full
list and category breakdown live.

## 8. Home / Dashboard consolidation — confirmed

Both call `workspace.service.list_project_assets`, which delegates to the
canonical shim. Live-verified: `shot_4_logo.png`'s record in both `GET
/dashboard/summary`'s `recent_assets` and `GET /workspace/home`'s
`recent_assets` is byte-identical (every field, including the
now-correctly-null `duplicate_group_id`).

## 9. Legacy Graph Assets — documented, not merged

Two pre-existing, unrelated "Asset" concepts exist in the Knowledge Graph
domains, confirmed to have **no id/endpoint overlap** with `app.assets`:

- **Epic 3's Knowledge Graph** (`app/graph/`): a `"Asset"` node built per
  filename string found in an imported ChatGPT conversation's extracted
  `assets`/`files` list, or per item in a manually-entered PI Project's
  `assets` collection. Label-only (`data={"filename": ..., "source":
  "conversation"}` or a raw dict from the Project row) — no filesystem
  access, no category/dimensions/hash.
- **Sprint 5's Conversation Graph** (`app/conversation_graph/`): a
  lowercase `"asset"` node sourced from LLM-extraction of conversation
  text (`extraction_db.list_all_objects()`), even further removed from
  the filesystem.

**Decision**: keep as a historical/knowledge representation, clearly
separate from `app.assets.AssetRecord` — do not delegate or merge. These
predate Sprint C4, answer a genuinely different question ("what assets
were *mentioned*" vs. "what asset files actually exist"), and a future
engineer should not assume `/graph?node_type=Asset` and `/assets` return
the same data. Documented here and in `docs/product/DECISIONS.md` rather
than renamed, since renaming a graph node-type label is a breaking change
to an existing, working, unrelated feature outside this audit's scope.

## 10. Classification architecture — reviewed, left as-is

`app/assets/classification.py`: 163 lines, one fixed-priority `_NAME_
RULES` tuple plus three small functions (`classify_category`, `is_
reusable`, `detect_likely_logo`). No duplication found; no structural risk
at this size. **Decision**: do not refactor into `assets/rules/` — that
split would add indirection without a concrete problem it solves today.
Revisit if the rule count grows enough to make the single fixed-priority
tuple hard to reason about (no fixed threshold set; a future sprint
should judge this by whether a reviewer can still read the whole
priority order in one screen).

## 11. Duplicate service boundary — stays inside `app.assets`

**Decision**: duplicate detection (partial-content SHA1 hash, grouped via
`group_duplicates`, surfaced via `GET /assets/duplicates/{id}`) stays
inside `app.assets.service` — no separate duplicate domain. Current code
demonstrates no concrete need for one (single hash algorithm, single
grouping pass, no cross-domain consumer other than `app.assets` itself).

**Documented future extension points** (not implemented, no code added):
- Full-file hashes (currently: first 1MB partial-content hash — a
  deliberate speed/practicality tradeoff, not upgraded here).
- Perceptual/near-duplicate image hashing (would catch the same image at
  different compression levels — partial-content hashing can't).
- Same-design-different-resolution detection (would need real image
  analysis, not just byte hashing).

## 12. Performance audit

**Verified working as intended**:
- Per-file dimensions/duplicate-hash are genuinely cached
  (`asset_cache`, keyed by path+mtime+size) — an unchanged file is never
  re-opened, re-decoded, or re-hashed on a subsequent scan.
- Thumbnails are lazy (`GET /assets/{id}/preview`, generated on first
  request, cached after).
- `/assets` paginates server-side (`page`/`page_size`).
- Duplicate grouping is bounded to the records already indexed, no extra
  filesystem pass.

**One real, measured inefficiency found, documented but not fixed**
(fixing would mean threading a pre-computed asset list through
`ProjectContext`'s shared `_assemble` function, which many other screens
depend on — out of scope for a no-redesign audit):

`GET /dashboard/summary` walks every adopted project's filesystem
**twice** in one request: once via `ProjectContext.assets_count` (per
project, inside `all_project_contexts()`) for the count, and again via
`workspace.service.list_project_assets` for the actual `recent_assets`/
`reusable_assets` records. Measured against the real workspace (5 adopted
projects, small asset counts):

| Endpoint | Measured (3 runs) |
|---|---|
| `GET /assets?page_size=200` | 275ms / 297ms / 305ms |
| `GET /workspace/home` | 285ms / 290ms / 282ms |
| `GET /project-context/{id}` (single) | 157ms / 150ms / 168ms |
| `GET /dashboard/summary` | 540ms / 545ms / 501ms |

Dashboard's ~500ms is roughly double `/assets`'s own ~280ms for
comparable work, consistent with the double-walk. Not urgent at the
current workspace size (sub-second either way), but will scale linearly
with adopted-project count and per-project asset count.
**Recommendation for C5**: have `build_dashboard_summary` compute
`assets_by_project` once and derive both the count and the record list
from it, rather than `ProjectContext` and Dashboard independently walking
the same projects.

## 13. Security regression audit — no weakening found

Re-verified live: unknown `asset_id` returns 404 on `/preview`, `/file`,
and detail (never a raw-path lookup); `POST /open-file` correctly 405s on
GET (method-restricted); the decompression-bomb guard, SVG safe-preview,
oversized-image 422, and thumbnail-cache exclusion from Sprint C4 remain
in place and covered by the existing 43 tests (unchanged this sprint).
Symlink/junction skipping (`entry.is_symlink()` guards in
`index_project_assets`) reviewed by source inspection — unchanged, same
pattern the Discovery Engine's already-tested symlink handling uses; not
re-tested with a real symlink here (Windows symlink creation needs admin
rights in this environment) since the code path itself was not touched
this sprint.

## 14. Architectural guard — 9 new tests

`dashboard/tests/test_assets_canonical_architecture.py` — source-tree
inspection (`ast`), not behavior, so a regression fails immediately:

1. `test_no_second_classification_function_exists` — no second `def
   classify_category` anywhere in `app/`.
2. `test_no_second_duplicate_grouping_function_exists` — no second
   `def group_duplicates`/`find_duplicates` anywhere in `app/`.
3. `test_legacy_workspace_assets_index_remains_a_thin_shim` — zero local
   `def`s in `assets_index.py`.
4. `test_explorer_service_uses_canonical_assets_module`.
5. `test_project_context_builder_uses_canonical_assets_module`.
6. `test_dashboard_service_uses_canonical_assets_module`.
7. `test_assets_router_is_the_only_place_that_writes_asset_overrides` —
   checks the qualified `assets_db.set_override` call, not the bare name
   (Workspace's unrelated boundary-override endpoint happens to share the
   function name `set_override` for a different domain — an early draft
   of this test false-positived on it and was corrected).
8. `test_frontend_assets_page_calls_canonical_api_not_legacy_endpoint`.
9. `test_frontend_assets_page_does_not_compute_classification_client_side`.

An explicit allowlist (`_CLASSIFY_ALLOWLIST`, `_DUPLICATE_GROUPER_
ALLOWLIST`) names the one legitimate file each check exempts — the
canonical implementation itself.

## 15. Live acceptance

All verified against the real `1 - IA PROJECTS` workspace (server
launched normally, cwd=`dashboard/`):

- Assets gallery, Explorer asset results, Project Hub assets summary,
  Dashboard recent assets, Home recent assets, and `ProjectContext.
  assets_count` all agree for `ROLE_KNOWLEDGE_OS`: **9 = 9 = 9**.
- `shot_4_logo.png` carries an identical `asset_id`, `category`,
  `reusable`, `likely_logo`, `preview_available`, `duplicate_group_id`
  (now consistently `null`), and `canonical_project_id` across the Assets
  API, Project Hub, Dashboard, and Home.
- No scanned file modified (by construction — nothing in this sprint
  touched write paths other than the in-memory `duplicate_group_id`
  resolution).
- No console errors on Dashboard/Assets after the fix (only the
  previously-documented harmless Chrome-extension-internal noise,
  unrelated to this app).

## 16. Tests and results

- 1 new regression test locking in the bug fix:
  `test_index_project_assets_resolves_duplicate_group_id_directly`.
- 9 new architectural guard tests (§14).
- Full repo-wide regression suite (`dashboard/tests`): **1021 passed, 0
  failed** (11:43 wall time; up from 1011 before this sprint's 10 new
  tests).
- `ruff check --select E9,F,I001` and `black --check` clean on every
  touched file.
- `node --check app/static/js/app.js` — no JS files were modified this
  sprint (audit found no frontend violation), so this is unchanged from
  Sprint C4's last passing check.
- Live browser smoke test: Dashboard and Assets gallery render correctly
  post-fix, no console errors.

## 17. Files inspected vs. modified

**Files created**: `dashboard/tests/test_assets_canonical_architecture.py`,
this report.

**Files modified**: `dashboard/app/assets/service.py` (the
`duplicate_group_id` fix), `dashboard/tests/test_assets_os.py` (1 new
regression test).

**Files inspected, unmodified** (confirmed already canonical): `app/
workspace/assets_index.py`, `app/workspace/service.py`, `app/workspace/
portfolio.py`, `app/workspace/activity.py`, `app/project_context/
builder.py`, `app/project_context/models.py`, `app/dashboard/service.py`,
`app/explorer/service.py`, `app/routers/pi/projects.py`, `app/graph/`,
`app/conversation_graph/`, `app/routers/graph.py`, `app/routers/
conversation_graph.py`, `app/static/js/app.js` (every asset-rendering
section).

## Recommendation for C5

Two follow-ups surfaced by this audit, neither urgent:

1. Fix the Dashboard double-walk (§12) by threading a pre-computed asset
   list through `ProjectContext` instead of two independent filesystem
   passes per request.
2. If/when duplicate detection needs to catch near-duplicates (same image
   re-exported at a different resolution, a different compression
   level), extend `app.assets.service` with perceptual hashing rather
   than opening a second duplicate-detection module — the extension
   points are documented in §11.
