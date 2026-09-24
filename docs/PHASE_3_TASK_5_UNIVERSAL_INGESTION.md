# Role OS 2.0 — P3.5 Universal Project & Tool Ingestion

*Implementation record. P3.5 evolved from "ROLE_PROJECT.md only" into a way to represent Role's useful work wherever it lives. No new database, no new entity, no sync platform, no Claude/ChatGPT/Chrome integration.*

**Baseline:** `2057ca5` (P3.4 complete), `main == origin/main`, tree clean — verified against `CURRENT_STATE.md` / `NEXT_ACTIONS.md` / the P3.1–P3.4 docs. The scope doc's original *proposed* task table used older numbering; `CURRENT_STATE.md` already tracked the real sequence, so this was not a material discrepancy. The scope doc now carries an authoritative *Executed Task Sequence*.

## Product Problem

Role's real work is not all Git repositories. Some of it lives only in Claude Web or ChatGPT, some is a Chrome bookmarklet, a reusable Kontoor/Unger script, a prompt/skill, or a web tool (yt-dlp, Cobalt). Until P3.5 Role OS could only manage work it found as a **local folder** (Discovery, or P3.4 registration), so that work was invisible to the Daily Command Center.

## Three Separate Concepts

| Concept | Field | Values | Owner |
|---|---|---|---|
| WHAT it is | `kind` (P3.2) | `project` (goal/lifecycle work) · `tool` (reusable capability) | Role |
| WHOSE work | `domain` / `client_name` (P3.2) | `KONTOOR` · `UNGER` · `ROLE PERSONAL` · `CLIENTES` (+ client) · unclassified | Role |
| WHERE it lives | `source` (**new**) | `local` · `claude_web` · `chatgpt` · `chrome_bookmark` · `github` · `web` · `other` | Role (or `local` for folders) |
| HOW to open it | `external_url` / `external_reference` (**new**) | an http(s) link and/or a free-text "where to find it" | Role |

**Domain ≠ source.** Claude, ChatGPT and Chrome are *sources*, never domains; `normalize_domain("CHATGPT")` is rejected (tested). The domain list is unchanged.

## Model (inspected first, then extended — no new persistence)

Inspected: `adopted_projects`, `registered_projects`, `PROJECT_REGISTRY.md`, Workspace service, Project Memory, Project Context, AI sessions, Assets, Mission Control, Dashboard v2. Finding: `adopted_projects` already carries everything managed work needs (adopted flag, domain/client/kind, status, priority, business value, notes, canonical project link), and every screen reads work through one function (`workspace.service._cached_projects()`), as P3.4 showed. So external work is simply **an adopted overlay row with no folder**.

Additive columns on `adopted_projects` (idempotent `ADD COLUMN`, NULL for every existing row):

| column | use |
|---|---|
| `source` | where it lives. NULL = legacy local folder, **resolved to `local` at read time, never back-filled** |
| `display_name` | name of external work (a folder's name still comes from disk) |
| `external_url` | optional http(s) pointer |
| `external_reference` | optional "where/how to find it" text |
| `next_action` | Role's own recorded next step (see *Notes / next action*) |

**Identity.** `adopted_projects.root_path` is the table's UNIQUE NOT NULL identity column. Rather than a destructive table rebuild, an external row stores an opaque, Role-OS-generated key there — `external:<uuid4>` — and its item id is the same `compute_item_id(key)` hash every item uses, so ids are stable. That key is **not a path**: it is never shown, never user-entered, and never used for filesystem access. Every Workspace consumer receives `root_path = None` (the key travels separately as `workspace_key`), which the existing "no local root" branches already handle: Resume Work picks a web assistant instead of Claude Code, Project Memory / session intent / summary skip file reads, the asset walk and Ecosystem detectors skip the item. A web-only project never needs a fake Windows path.

Guards added where `None` was not already safe: next-action extraction never runs with an empty root (it would otherwise resolve `Path("")` to the server's CWD — tested), `list_project_assets` skips folder-less items, and *Launch Claude Code* is refused for external work with a clear message.

## Add External Work (UI)

Workspace page → **Add External Work** (next to *Register Project*):

- Form: **Name**, **Kind** (project / tool, with one-line meanings), **Domain** (default *Unclassified* — never guessed), **Client** (only shown for CLIENTES), **Source** (must be chosen; no default), **URL** (optional), **Reference** (optional), **Status** (active / paused / blocked / completed / archived), **Priority** (low / medium / high / critical), **Purpose / notes** (optional), **Next action** (optional). A line warns not to paste passwords, tokens or bookmarklet code and states the URL is only a link Role OS does not read.
- **Review** → `POST /workspace/external-work?dry_run=true` validates and returns the normalized record; **nothing is saved**. The review card shows every field plus where the item will appear (Tools vs. Daily Command Center). Editing any field clears the review; **Save** saves exactly what was reviewed.
- After saving, the item is an ordinary adopted Workspace item: its **Location** column shows the source badge and **Open ↗** (or the reference text); status/priority/domain/next action/URL can be edited through the existing `PATCH /workspace/discovered/{id}`; it can be hidden with the existing **Ignore**.

Local folders keep using Discovery or **Register Project** (source `local` is refused on this form).

## External References

- URL: optional; must be absolute `http`/`https` with a host; no spaces; ≤ 2,048 chars. **Rejected:** `javascript:` (bookmarklet code), `file:`, `data:`, scheme-less links, and URLs with embedded `user:password@`. Purely syntactic — **no network access** to save.
- Reference: optional free text ≤ 500 chars; may not start with `javascript:`.
- **Open ↗** opens the stored URL in a new tab (`target="_blank" rel="noopener noreferrer"`), shown in the Daily Command Center (Recommended / Then / Pending / Active / Completed / Tools), the Workspace list, review panel and project detail. It is a navigation pointer, **not** proof Role OS can read the content, and **not** Resume Work.

## Claude Web / ChatGPT

Source `claude_web` / `chatgpt` with an optional project/conversation URL, plus domain, kind, status, priority, purpose and next action. Role OS never reads the conversation. Resume Work still behaves as before: it builds a prompt from Project Memory (name, notes, recorded next action) and — because there is no local root — targets a web assistant; it creates an AI-session record exactly as it does for any project. Opening the stored URL is a separate, explicit **Open** click.

## Chrome Bookmarklets / Scripts

Registered by hand as `kind = tool`, `source = chrome_bookmark`, with a reference such as "Chrome bookmarks bar › Kontoor › FS Quick Actions" (a URL is optional). Role OS does **not** read Chrome bookmarks, modify Chrome, store bookmarklet code, execute anything, or store credentials. It only *knows the tool exists and where to find it*. Storing source code would need a separate, secure code-storage design — not built.

## Project vs Tool (unchanged P3.2 semantics)

External tools flow through the same `kind = tool` predicate (`classification.is_rank_excluded`) as local tools: they appear under **Tools** and never in *What should I do now?*, the Executive Decision ranking, Primary Focus, Today's Focus or Needs Attention (ranking, Executive Decision and Primary Focus tested for an external tool; the others use the same shared predicate, covered by the P3.3 tests). External projects appear in **Active Projects** and **Pending Work** once saved (they are adopted on save — Role reviewed every field), compete in the ranking like any adopted project, and move to **Completed** (excluded from recommendations) when their status is `completed`. Domain filters apply identically (tested for UNGER and CLIENTES + client).

## Notes / Purpose / Next Action

- **Purpose / notes** reuse the existing overlay `notes` list (the purpose becomes the first note) — no new text field.
- **Next action:** the existing sources are all file-based (`NEXT_ACTION.md`, TODO, ROADMAP, README, CHANGELOG, git) or AI-session snapshots — none exist for work without a folder. One overlay column, `next_action`, holds Role's own recorded step. When set it is returned with source **"manual entry"** and confidence 1.0 (an explicit statement by Role outranks inferred signals); when empty, behavior for local projects is exactly as before. Existing local projects have it NULL, so nothing changes for them.
- "Where did I leave off?" continues to come from AI-session snapshots once Resume Work has been used.

## ROLE_PROJECT.md — Decision

**Designed, parser/import DEFERRED.** Reasons: (1) universal external registration covers the urgent need (work with no folder) without any file; (2) importing a manifest needs precedence rules between a file in a repo and values Role edits in the UI (which wins, when, and how a change is detected) — a real design task, not a small parser; (3) Role OS already detects a second, unused manifest (`.role-os/project-status.json`, `detectors/operational_manifest.py`) — two manifest formats should be reconciled once, not twice. P3.4 already *reports* when a `ROLE_PROJECT.md` exists.

Scope: **optional, local folders only.** Never required for Claude Web / ChatGPT work, bookmarklets or simple tools.

Minimal schema (Markdown with a small key/value header; human-owned values only):

```markdown
# ROLE_PROJECT
name: Bolsa de Trabajo
domain: ROLE PERSONAL        # KONTOOR | UNGER | ROLE PERSONAL | CLIENTES
client:                      # only when domain is CLIENTES
kind: project                # project | tool
status: active
priority: medium

## Purpose
One or two sentences: what this is and why it exists.

## Next Action
The single next concrete step.
```

| | Fields |
|---|---|
| **REQUIRED** | none beyond the file itself — every field is optional; `name` recommended |
| **OPTIONAL** (human-owned) | `name`, `domain`, `client`, `kind`, `status`, `priority`, `## Purpose`, `## Next Action` |
| **AUTO-DISCOVERED — DO NOT STORE** | path, git remote/branch/commits/dirty state, languages/tech stack, file counts, README/CHANGELOG/tests presence, health score, last activity, `source` (a folder is always `local`) |

Values would be validated with the same P3.2/P3.5 normalizers (bad values rejected, never guessed), proposed on the review card, and only applied on Role's explicit adopt — never auto-imported.

## Security / Privacy

No passwords, cookies, session tokens, API keys or browser data are stored or read; URLs with embedded credentials are rejected; no Claude, ChatGPT, Chrome, browser-history or bookmark scraping; no network access to save a reference; stored URLs are opened only by Role's explicit click in a new tab with `noopener noreferrer`; bookmarklet `javascript:` code is refused in both URL and reference.

## API

| method | path | behavior |
|---|---|---|
| POST | `/workspace/external-work?dry_run=true` | review: validate + normalize, persist nothing |
| POST | `/workspace/external-work` | save: one adopted overlay row + its canonical Role OS project; returns the Workspace item |
| PATCH | `/workspace/discovered/{id}` | existing endpoint, now also accepts `next_action`, and (external only) `display_name`, `external_url`, `external_reference`; 422 on invalid values |

Workspace items, Project Contexts and Daily Command Center items gain `source`, `is_external`, `external_url`, `external_reference`; Workspace summary gains `projects_external`. All existing keys unchanged; `WorkspaceItem.root_path` is now `str | None`.

## Migration / Backward Compatibility

Additive columns only; no row rewritten; no id changed. The five adopted projects keep `ROLE PERSONAL / project / active` and resolve to `source = local` at read time with `source` still NULL in the DB (tested with a fresh adopted local item). P3.4 registration is unchanged — registered folders resolve to `local`. Discovery roots untouched.

## Tests

`dashboard/tests/test_universal_ingestion.py` — **30 tests**: source vocabulary and validation (case/hyphen tolerant, unknown and `local` rejected for external); domains unchanged and providers rejected as domains; unsafe URLs (`javascript:`, `file:`, `data:`, scheme-less, credentials, spaces); bookmarklet code refused as reference; API 422 for invalid source / `local` / blank name with nothing persisted; domain + CLIENTES/client rules; dry-run persists nothing; Claude Web project without local path (root None, notes from purpose, canonical project created); ChatGPT reference; Chrome-bookmark tool without URL; web + GitHub references; URL serialization through the API and Project Context; stable unique ids for same-named items; no filesystem reads (a `NEXT_ACTION.md` in the CWD is not picked up; no asset walk); recorded next action + PATCH (and 422 on bad URL); Claude Code launch refused; local backward compatibility (same id, `source` resolved not stored); P3.4 registration still local/unadopted and no Discovery-root change; Resume Work for an external project (not Claude Code); external project in Active with source/URL/domain/next action; external tool in Tools only; tool excluded from ranking / Executive Decision / Primary Focus; completed external project under Completed and unranked; domain/client data for filtering; ignored external work leaves Mission Control; UI strings (form labels, sources, dry-run review, `noopener noreferrer`).

Results: focused 30/30 (plus the P3.3 and P3.4 suites re-run together: 79/79); **full suite 1,483 passed, 0 failed** (`tests/`, `builder/tests/`, `dashboard/tests/`; 1,453 before + 30). No existing test was modified. Every new test uses its own workspace DB and clears the lru-cached `get_settings()` (the P3.4 lesson).

## Live Validation

**Runtime DB isolation:** SHA256 of all 15 runtime DB files (10 under `var/`, 5 in `ROLE_KNOWLEDGE_OS\00_SYSTEM\`) identical before and after the full test run.

**Live UI (canonical runtime, server restarted with the repo's Stop/Start scripts):**

- Workspace page shows **Add External Work** next to *Register Project* and *Rescan Workspace*.
- The form offered exactly: Name · Kind · Domain · Client (CLIENTES only) · Source · URL · Reference · Status · Priority · Purpose / notes · Next action.
- A sample (tool · KONTOOR · Chrome bookmark · reference "Chrome bookmarks bar > Kontoor > FS Quick Actions") was entered and **Review** produced the correct review card ("Tools appear under Tools and never compete…"). **Save was not clicked.**
- A `javascript:` URL was rejected live with the bookmarklet message.
- Afterwards: `projects_external 0`; Daily Command Center Tools "No tools registered yet.", Completed "No completed projects yet.", Active still the five local projects (`source local`); no error boxes on the page.

**Runtime/user data modified:** `var/role_os_dashboard/role_os_workspace.db` only — the five additive columns were created by the app's own schema migration on first connection (all NULL; `integrity_check` ok). No rows added or changed: `adopted_projects` still 5 × `ROLE PERSONAL / project / active`, 0 external rows; `registered_projects` still only bolsa-de-trabajo (`d560e18f1f2b3339`), still not adopted. All other 14 DB checksums identical. No real external work (yt-dlp, Cobalt, Kontoor/Unger scripts, Claude Web/ChatGPT projects) was created. Discovery roots unchanged (`ROLE_OS_DISCOVERY_ROOTS` unset).

## Limitations

- No edit form yet for an external item's fields (API `PATCH` only; UI supports add, review, open, ignore).
- Ignore hides external work; there is no hard delete (by design, reversible).
- `status` remains free text in the API; the form offers the five known statuses.
- A recorded `next_action` must be updated by Role — nothing infers it for external work.
- No import from Claude/ChatGPT exports, Chrome bookmark files or `ROLE_PROJECT.md` yet.

## Future Import Possibilities (not built)

`ROLE_PROJECT.md` / `.role-os/project-status.json` reconciliation and import; opt-in import of a single exported Claude/ChatGPT conversation into the existing Import pipeline; a user-selected Chrome bookmarks HTML export parsed locally into *proposed* tools (never auto-saved); a code-snippet store for scripts with explicit secret scanning.
