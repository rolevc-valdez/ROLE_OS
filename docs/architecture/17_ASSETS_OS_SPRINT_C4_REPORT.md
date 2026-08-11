# 17 — Assets OS, Sprint C4: Completion Report

Scope executed: replace the Assets page's flat technical file listing
(Knowledge Graph `Asset` nodes) with a real visual Asset Library over
files discovered inside adopted projects — canonical `AssetRecord` model,
safe thumbnail/preview service, deterministic classification, reusable
overrides, duplicate detection, gallery/list views, Asset Detail panel,
Project Hub and Explorer integration, one canonical `/assets` API. No
version bump, no commit, no tag.

## 1. The problem

The Assets page listed `Asset` nodes from the Epic 3 Knowledge Graph — a
technical, LLM-independent representation with no thumbnails, no
classification, no reuse signal, no way to tell a screenshot from a
reusable logo. It had no relationship to the real files sitting inside
adopted project folders, and no path from "I need the RoleValdez logo"
to an actual usable file.

## 2. Architecture

```
GET /assets?q=&category=&project_id=&reusable=&favorite=&duplicates_only=&page=
        │
        ▼
app.assets.service.search_assets()
        │
        ├─ app.assets.service.list_all_assets()
        │       └─ app.project_context.builder.all_project_contexts()   (same fn every screen uses)
        │               └─ app.assets.service.index_project_assets()    (per adopted project root)
        │                       ├─ app.assets.classification            (category/reusable/likely_logo)
        │                       ├─ app.assets.image_meta                (Pillow dimensions, decompression-bomb guard)
        │                       └─ app.assets.db                        (asset_cache, asset_overrides)
        └─ app.assets.db.list_overrides()                               (user reusable/category/favorite)

GET /assets/{id}/preview
        │
        ▼
app.assets.service.resolve_safe_path(asset_id)   (asset_id → real path, only if it's in the live index
        │                                          AND resolves inside a currently-adopted root)
        ▼
app.assets.preview.get_or_create_thumbnail()     (Pillow resize, cached under var/.../asset_thumbnails/)
```

One canonical asset index (`app.assets.service`), one canonical model
(`AssetRecord`), reused unmodified by the Assets gallery, Explorer's
Asset search results, and Project Hub's assets summary. `app.workspace.
assets_index` (Sprint 4) is now a thin backward-compatible shim
delegating to `app.assets.service` — not a second implementation.

## 3. Canonical `AssetRecord`

`dashboard/app/assets/model.py`:

```
asset_id, canonical_project_id, discovery_item_id, filename,
absolute_path, relative_path, extension, asset_type, category,
mime_type, size_bytes, width, height, duration_seconds, modified_at,
reusable, likely_logo, duplicate_hash, duplicate_group_id,
preview_available, preview_url, source, favorite, project
```

`asset_id = sha1(absolute_path)[:16]` — deterministic, matches this
codebase's existing `compute_item_id` convention. `duration_seconds` is
honestly `None` (video/audio duration extraction is out of scope this
sprint) rather than a fabricated value.

## 4. Classification (deterministic, no LLM)

`dashboard/app/assets/classification.py` — 16 categories (Logo, Brand,
Character, Photo, Illustration, Screenshot, Icon, Social Media,
Thumbnail, Template, Video, Audio, Document, Font, Prompt Resource,
Other), matched in a fixed priority order against:

1. filename + **root-relative** folder path (regex, `_`/`-` normalized to
   spaces so `\bword\b` boundaries work correctly against real
   underscore/hyphen-delimited filenames)
2. image dimensions (icon-sized, common raw screen-capture resolutions)
3. file extension

Folder-path matching is deliberately scoped to the path *relative to the
scanned project root*, not the full absolute filesystem path — an
absolute path also carries every ancestor directory outside the project
itself (a Windows username, "My Drive", a parent workspace folder), any
of which could coincidentally contain a classification keyword and
misclassify every file nested under it. Root-relative keeps the signal
to folder names the project itself actually created.

**Reusable-by-default**: `True` only for Logo/Brand/Character/Template/
Font/Icon; ordinary screenshots/photos/thumbnails default to `False`,
per the explicit "do not mark ordinary screenshots and temporary exports
reusable by default" requirement. A user can override any asset's
reusable flag, category, or favorite status — stored exclusively in
`role_os_assets.db`'s `asset_overrides` table, never written back into
the scanned source file.

## 5. Preview / thumbnail security model

- Every preview/file/open-file/open-folder request resolves exclusively
  through `resolve_safe_path(asset_id)`, which re-derives the real
  filesystem path from a validated `asset_id` already present in the
  **live index** and checks it resolves inside a **currently-adopted**
  project root. A client can never submit a raw filesystem path — there
  is no endpoint that accepts one.
- Raster images (`png`/`jpg`/`jpeg`/`webp`/`gif`) are opened with Pillow,
  resized to a 480px max dimension, and cached under `Settings.
  asset_thumbnail_cache_dir` (default `var/role_os_dashboard/
  asset_thumbnails/`) — never inside a scanned project folder. Cache key
  is `{asset_id}-{int(source_mtime)}.png`, so an edited source is never
  served a stale thumbnail.
- `Image.MAX_IMAGE_PIXELS` is capped at 64,000,000 (~8000×8000) as a
  decompression-bomb guard; `PIL.Image.DecompressionBombError` is caught
  and converted to an honest HTTP 422, not a crash.
- SVG is served as its own file with an `image/svg+xml` content type
  rather than rasterized — a browser loading it via `<img src=...>`
  treats it as a non-executing image resource (no embedded `<script>`
  runs), the standard safe-embed mechanism, without a sanitizer
  dependency.
- Unsupported formats report `preview_available: false`; the frontend
  shows a type-specific placeholder instead of a broken-image icon, both
  for a genuinely unsupported format and for a preview request that
  fails at request time (`onerror` graceful degradation).
- The generated thumbnail cache directory itself is excluded from every
  scan (read from `Settings.asset_thumbnail_cache_dir`'s own resolved
  parent, not a separately-assumed path — see §8, bug 3) so it can never
  be walked back in as a "discovered asset."

## 6. Duplicate detection

The existing partial-content SHA1 hash (first N bytes) is resolved into
a real `duplicate_group_id` only for files that actually share it with
2+ others. `GET /assets/duplicates/{group_id}` lists every member with
its project and path. Duplicates are surfaced, never auto-deleted or
auto-consolidated — the user decides.

## 7. API

`dashboard/app/routers/assets.py`, namespaced under `/assets`:

| Method | Path | Description |
|---|---|---|
| GET | `/assets` | List/search/filter/paginate |
| GET | `/assets/freshness` | Last scan time / staleness |
| GET | `/assets/duplicates/{group_id}` | Duplicate group members |
| GET | `/assets/{id}` | Full detail |
| GET | `/assets/{id}/preview` | Cached resized preview (422 if unsupported/unsafe) |
| GET | `/assets/{id}/file` | Raw file stream |
| PATCH | `/assets/{id}` | Set reusable/category/favorite override |
| POST | `/assets/{id}/open-file`, `/assets/{id}/open-folder` | OS-integration (this machine, Windows only) |

Route registration order matters: `/freshness` and `/duplicates/{id}` are
registered before the `/{asset_id}` wildcard. `GET /workspace/assets`
(Sprint 4) is unchanged as a contract and now delegates to this same
canonical service.

## 8. Bugs found and fixed during live verification

None of these were caught by the unit test suite — each was found by
running the real server against the real `1 - IA PROJECTS` workspace, and
each now has a regression test.

1. **Word-boundary regex defeated by underscores.** `\blogo\b`-style
   rules never matched `shot_4_logo.png` because Python's `re` treats
   `_`/`-` as word characters — no boundary exists between `_` and `l`.
   Fixed by normalizing `[_\-]+` to spaces in the match haystack before
   applying every rule.
2. **Uncaught decompression-bomb exception (HTTP 500).** A real
   ~208-megapixel image (`shot_4_logo.png`, PNG) crashed `GET /assets/
   {id}/preview` with `PIL.Image.DecompressionBombError`, because
   `preview.py` never imported `image_meta`'s `Image.MAX_IMAGE_PIXELS`
   guard as a side effect, and the exception wasn't caught. Fixed by
   importing `image_meta` explicitly for its side effect and adding a
   dedicated `except Image.DecompressionBombError` handler converting it
   to `PreviewError` → HTTP 422. Frontend gained `onerror` graceful
   degradation so a failed `<img>` load shows a placeholder, not a
   browser broken-image icon.
3. **Classification matched the entire absolute path.** `folder_path`
   was `str(entry_path.parent)` — the full absolute path, including every
   ancestor directory outside the scanned project. A test whose pytest
   `tmp_path` happened to contain the word "logo" (because the test
   function itself was named `test_logo_detected_as_category`) proved
   this: unrelated ancestor directories could misclassify every file
   nested under them. Fixed to match only the path relative to the
   scanned project root.
4. **Generated thumbnail cache leaking back into its own index.**
   Indexing ROLE_OS's own checkout (a real adopted project, since it
   contains the running dashboard) walked its own freshly-generated
   thumbnail cache back in as "discovered assets," which then got
   re-thumbnailed on the next scan. The first fix attempt excluded a
   hardcoded `Settings.repo_root / "var"`, which worked once but not
   after a server restart from a different launch cwd: every `var/`-
   relative default in `config.py` is a *relative* path, resolved via
   `Path(...).resolve()` against the process's current working directory
   at `Settings()` construction time — not against `repo_root`, which is
   derived from `__file__`. Launching with cwd=`dashboard/` (the normal
   `uvicorn app.main:app` workflow) therefore actually wrote to
   `dashboard/var/role_os_dashboard/asset_thumbnails/`, not `var/...` at
   the repo root. Fixed by reading the real, already-resolved `Settings.
   asset_thumbnail_cache_dir`'s parent directly, instead of reconstructing
   an assumed path.
5. **A second process's runtime dir, invisible to the first process's
   exclusion.** Even after fix 4, a *second*, unrelated process — a
   `pytest` run launched from the repo root while a dev server was
   already running from `dashboard/` — independently resolved the same
   relative default to a *third* physical directory
   (`ROLE_OS/var/role_os_dashboard/asset_thumbnails/`), which leaked into
   the live server's asset list the same way, since the live server's
   exclusion only knew about its own resolved runtime dir. Fixed with a
   second, structural exclusion layer: `role_os_dashboard` — the one
   literal path segment every `var/`-relative default in `config.py`
   shares, regardless of which `var/` parent it resolves under — is
   excluded by directory *name*, the same way `.git`/`node_modules` are
   in `IGNORE_DIR_NAMES`, catching every physical copy structurally
   instead of chasing one resolved path at a time. See
   `docs/product/DECISIONS.md` for the general principle this
   established.

## 9. Files created

- `dashboard/app/assets/__init__.py`, `model.py`, `classification.py`,
  `image_meta.py`, `db.py`, `service.py`, `preview.py`
- `dashboard/app/routers/assets.py`
- `dashboard/tests/test_assets_os.py` (33 tests), `test_assets_ui.py` (10
  tests)

## 10. Files modified

- `dashboard/app/config.py` — `assets_db_path`, `asset_thumbnail_cache_dir`
- `dashboard/app/workspace/assets_index.py` — rewritten as a thin
  backward-compatible shim over `app.assets`
- `dashboard/app/workspace/service.py` — passes canonical/discovery ids
  through to `index_assets_for_project`
- `dashboard/app/project_context/builder.py` — same, plus a new public
  `all_project_contexts()` shared with Dashboard/Explorer
- `dashboard/app/explorer/service.py` — `_search_assets` now calls
  `app.assets.service.list_all_assets()` directly; `project_hub()` gains
  an `assets_summary`
- `dashboard/app/main.py` — registers the `assets` router
- `dashboard/app/static/js/app.js` — Assets OS gallery/list frontend,
  Asset Detail panel, Project Hub assets summary, Explorer asset
  navigation, graceful thumbnail-error degradation
- `dashboard/app/static/css/components.css` — Assets OS styles
- `dashboard/requirements.txt` — `Pillow>=10.0,<12.0`
- `dashboard/tests/test_workspace_assets_index.py`,
  `test_workspace_sprint4_ui.py` — updated for intentionally new
  category values and the canonical `/assets` endpoint

## 11. Tests and results

43 new/rewritten tests across `test_assets_os.py` and `test_assets_ui.py`
covering: canonical record shape, PNG/SVG dimension parsing, SVG safe
preview, unsupported-format no-preview, oversized-image preview failing
honestly (422, not 500), logo/screenshot reusable defaults, category +
reusable + favorite overrides never touching the source file, duplicate
grouping and the `/assets/duplicates/{id}` endpoint, project filtering,
search by filename/category/extension/relative_path, pagination, path
traversal rejection, asset ids for files outside any adopted root
rejected, resolved-path-outside-adopted-roots rejected, missing/deleted
files, cache invalidation, `ProjectContext.assets_count` parity, Explorer
integration, manual projects (no assets, no error), real paths with
spaces/parentheses, excluded folders never leaking in, ROLE OS's own
runtime directory never leaking into the index, classification unit
tests. 4 pre-existing tests updated for intentionally new behavior
(Title Case categories, `.psd` no longer reusable by default, the
canonical `/assets` endpoint replacing `/workspace/assets` in UI
assertions).

Full repo-wide regression suite (`dashboard/tests`, 1011 tests) run after
every fix: **1011 passed, 0 failed** (12:20 wall time).

## 12. Real-workspace verification

Verified live against the real `1 - IA PROJECTS` folder (server launched
the same way the normal workflow does, cwd=`dashboard/`):

- 9 real assets discovered, all inside `ROLE_KNOWLEDGE_OS/ROLE_OS_BUILDER`
  (`home.png`, `shot_1_crwd.jpg` … `shot_8_ChatGPT Image ....png`).
- `shot_4_logo.png` correctly classified `category: "Logo"`,
  `reusable: true`, `likely_logo: true` — the only reusable asset in the
  real dataset — and correctly shows an honest 422 ("image too large to
  preview safely") rather than a crash, since it's a genuinely oversized
  (~208-megapixel) file.
- The other 8 assets render real thumbnails in the gallery.
- **No RoleValdez logo was fabricated.** ROLE MASTER (checked per the
  brief's explicit instruction) currently has zero image/design assets —
  only markdown and JSON files — so it correctly contributes nothing to
  the Asset Library. This is reported honestly, not worked around.
- No duplicate assets currently exist in the real dataset, so
  `duplicate_group_id` grouping is exercised by unit tests only, not by
  live data — noted as a known limitation below, not a bug.
- Filtering by project, by reusable, `/assets/freshness`, and a full
  `POST /workspace/rescan` → re-list cycle all verified stable, including
  after fixing bug 4 above (confirmed clean across a server restart from
  the real launch cwd).
- Explorer integration verified: `GET /explorer/search?q=logo` returns an
  Asset result whose primary action opens the real Asset Detail panel.
- Browser check: gallery renders correctly, 8/9 real thumbnails load,
  the oversized logo shows the honest placeholder, no `app.js` console
  errors (only the known harmless Chrome-extension-internal "listener
  indicated an asynchronous response" noise, unrelated to this app).

## 13. Known limitations

- Video/audio duration extraction is not implemented; `duration_seconds`
  is always honestly `None`.
- No HTTP Range/seek support for video/audio streaming — full-file
  playback only.
- Open File / Open Folder are implemented for Windows only, the platform
  this dashboard is built to run on.
- Duplicate-group grouping was verified only via unit tests against the
  real dataset, since no real duplicate files currently exist in
  `1 - IA PROJECTS`.

## 14. Recommendation for a hypothetical Sprint C5

The Assets OS foundation (canonical model, safe preview pipeline,
deterministic classification) is now reusable infrastructure. A natural
next step would extend it to video/audio (real duration extraction,
Range-request streaming, a video thumbnail via a decoded first frame)
rather than opening a new asset subsystem — the same `AssetRecord`,
`resolve_safe_path`, and cache-under-`var/` patterns already generalize.
