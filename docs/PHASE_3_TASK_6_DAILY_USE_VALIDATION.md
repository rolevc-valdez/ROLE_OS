# Role OS 2.0 — P3.6 Daily Use Validation & Real Work Onboarding

**Status: IN PROGRESS — WAITING FOR REAL KONTOOR ITEMS** (the two KONTOOR real-data examples must come from Role; nothing was invented). P3.6B polish applied — see the end of this document.

*Validation record. The original P3.6 pass changed no production code (P3.6B, at the end, did). Real onboarding was done only through the existing application API/UI.*

**Baseline:** `576be26` (P3.5 complete), `main == origin/main`, tree clean. The Role OS server was not running at start; it was started with the repo's `scripts/Start-RoleOS.ps1` and left running.

## Real Items Onboarded

| Item | Action | Result |
|---|---|---|
| **bolsa-de-trabajo** (`C:\Users\rolev\bolsa-de-trabajo`) | Adopted as authorized via the existing `POST /workspace/discovered/d560e18f1f2b3339/adopt` with `domain ROLE PERSONAL, kind project, status active` | Same stable id `d560e18f1f2b3339`; registration kept (`registered_projects` row unchanged, `registration_source explicit`, `source local`); canonical Role OS project created (`7e62998e…`). Priority/business value are the system defaults (`medium`) — nothing chosen or invented; no deadline, no next action, not completed. |
| **yt-dlp** | Added through **Add External Work** (Review dry run → Save) after local verification | `kind tool`, `domain ROLE PERSONAL`, `status active`, **`source other`**, URL `https://github.com/yt-dlp/yt-dlp` (upstream docs), reference "Installed CLI via winget (package yt-dlp.yt-dlp), run from PowerShell; downloads go to %USERPROFILE%\Downloads\Role Media. Usage guide: PROJECT_REGISTRY.md > YT-DLP.", purpose note from the registry entry. No next action (none known). |

**yt-dlp verification (machine evidence, not documentation alone):** `yt-dlp --version` → `2026.08.19`; binary at `%LOCALAPPDATA%\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe\yt-dlp.exe`; matches `PROJECT_REGISTRY.md` (winget package, same version). **Why `other`, not `local`:** in the P3.5 model `local` means a real project folder Role OS can analyze (Discovery/registration); yt-dlp is an installed third-party CLI with no project folder of Role's, and inventing one would be dishonest. No credentials or secrets stored (the `%USERPROFILE%` variable is kept unexpanded).

**bolsa-de-trabajo checks after adoption:** appears under ROLE PERSONAL and in Active Projects (rank 4 of 6); Mission Control reasons about it normally (ranked, Needs Attention "Commit or stash uncommitted changes" — true: its pre-existing `tsconfig.tsbuildinfo` modification; next action inferred from its latest commit); `ROLE_OS_DISCOVERY_ROOTS` still unset, scan root unchanged; repository untouched — `git status --porcelain` + `HEAD` identical and all 53 files (excluding `.git`, `node_modules`, `.next`) identical in path/size/mtime before vs. after.

## Waiting for Role Input

Not created — no placeholders:

**A. One real KONTOOR project that lives in Claude Web** — Workspace → **Add External Work**:
Name · Kind `project` · Domain `KONTOOR` · Source `Claude Web` · URL (the Claude project/conversation link, if any) · Status · Priority · Purpose/notes (what it is, why it exists) · Next action (the next concrete step). Then **Review** → **Save**.

**B. One real KONTOOR reusable script / bookmarklet / tool** — same form:
Name · Kind `tool` · Domain `KONTOOR` · Source matching reality (`Chrome bookmark` / `Claude Web` / `Web` / `Other`) · URL if it has a normal http(s) link, otherwise Reference (where it lives, e.g. "Chrome bookmarks bar › Kontoor › …") · Status · Priority · Purpose/notes. **Do not paste the bookmarklet code or any credentials** (the form rejects `javascript:`).

After both are saved, the KONTOOR domain, the Tools section and the external **Open ↗** links can be validated with real data and P3.6 can close.

## Daily Command Center — Real Data (as seen in the browser)

Chips: **All 7 · KONTOOR 0 · UNGER 0 · ROLE PERSONAL 7 · CLIENTES 0**.

- **What should I do now?** Recommended **ROLE Commerce Factory** (STALE, NEEDS ATTENTION), next action *inferred* "milestone: Phase 3 local provider pipeline validated (2026-08-21T12:30:17-07:00)", why: "Suggested: Consider shipping/launching · Has a next action (inferred from latest git commit) · No activity in 34 days", **Continue Working →**; then ROLE_OS and role-ecosystem.
- **Needs Attention:** Commerce Factory (critical), bolsa-de-trabajo / role-ecosystem / ROLE_OS (commit or stash), "Rescan Workspace", **"Role Test Project"**, ROLE MASTER, ROLE_KNOWLEDGE_OS.
- **Pending Work / Next Actions:** 5 cards; 3 of them are past git commit messages, role-ecosystem has an ai_session next action + pending work, ROLE MASTER one from TODO.md.
- **Active Projects:** 6 (5 original + bolsa-de-trabajo), all ROLE PERSONAL, all NEEDS ATTENTION, 4 STALE, health mostly "critical".
- **Completed:** "No completed projects yet." (honest — nothing marked completed).
- **Tools:** yt-dlp · ROLE PERSONAL · tool · Other · **Open ↗** (new tab, `noopener noreferrer`).
- **Role Dashboard:** card + **Open Role Dashboard →**.
- **Where I Left Off:** role-ecosystem, next action "n8n orchestration design", latest snapshot + AI session.
- Page length ≈ 4,000 px: only the recommendation is in the first viewport.

## 30-Second Test

| # | Question | Result | Note |
|---|---|---|---|
| 1 | What should I work on first? | **PASS** | Recommended card is the first thing below the chips. |
| 2 | Why? | **PARTIAL** | Why bullets exist, but they lean on an *inferred* past commit and on STALE/NEEDS ATTENTION that every project carries (344 h old scan) — the reason doesn't distinguish the pick. |
| 3 | What else is pending? | **PARTIAL** | Pending Work exists but 3 of 5 "next actions" are past commit messages with raw timestamps; reads as history, not a to-do. |
| 4 | Which projects are active? | **PASS** | Six clear cards (below the fold). |
| 5 | Which tools are available? | **PASS** | yt-dlp visible with domain, source and Open. |
| 6 | Which domain owns each item? | **PASS** | Chips with counts + a domain tag on every card. |
| 7 | Where did I leave off? | **PARTIAL** | Last section on the page (≈ 4,000 px down); its snapshot text is truncated at the start ("l estado…") and describes ROLE Commerce Factory while attached to role-ecosystem. |
| 8 | How do I continue? | **PASS** | Large **Continue Working →** on the recommendation (not clicked — it would create a real AI session record). |
| 9 | How do I open Role Dashboard? | **PASS** | Visible button; opens `#/dashboard` (see friction on scroll/return). |

## Domain Validation

ROLE PERSONAL = 5 original projects + bolsa-de-trabajo + yt-dlp (7) ✔. KONTOOR empty (waiting for Role) ✔. UNGER, CLIENTES empty — acceptable, nothing created to fill them. Each chip filters Recommended / Pending / Active / Completed / Tools with honest empty states ("No projects in this domain.", "No tools in this domain.", "No completed projects in this domain.").

## Project vs Tool

Projects (6) are ranked by the Executive Decision (Commerce Factory 1 … ROLE_KNOWLEDGE_OS 6, bolsa 4). yt-dlp is **not** ranked, not in Executive Decision / Primary Focus / Today's Focus, and appears only under **Tools**. Domain filtering applies to both. **Open ↗** is a plain new-tab link to the stored URL; clicking the tool card opens its detail page (Location, reference, Open) — no Resume Work is triggered by either.

## Completed

Zero real completed projects → "No completed projects yet." Nothing was marked completed; completion behavior remains covered by automated fixtures (P3.3/P3.5 tests).

## Role Dashboard

**Open Role Dashboard →** navigates to `#/dashboard`; Dashboard v2 loads (Dashboard, Portfolio Status, Continue Work, Needs Attention, Recent Activity, Recent Assets, Recent Knowledge; no errors) and already shows the two adoptions in Recent Activity. Returning: sidebar **Mission Control** → `#/home` works. Friction recorded below (scroll position, naming, no back link). No new dashboard was created.

## Friction Log

**BLOCKER** — none.

**HIGH VALUE**
1. **Stale-signal saturation.** Workspace scan is 344 h old; 6/6 projects NEEDS ATTENTION, 4/6 STALE, most "critical" — badges stop differentiating. A rescan (Workspace → Rescan) is the immediate remedy; before autostart, decide whether startup should refresh the scan.
2. **Past commits presented as "Next action".** For 3 of 6 projects the next action is the latest commit message (with an ISO timestamp); labelled *inferred* but still reads as history. Recording real next actions (NEXT_ACTION.md / snapshots / the P3.5 manual next action) or de-emphasising commit-derived ones would sharpen questions 2–3.
3. **"Where I Left Off" is buried** at the bottom of a ≈ 4,000 px page — one of the three core questions.
4. **Where-I-Left-Off data quality.** The only saved snapshot (role-ecosystem, 2026-08-21) begins mid-word and describes ROLE Commerce Factory work — data, not code; needs Role's decision (re-snapshot or correct), not auto-editing.
5. **Test data in production views.** "Role Test Project" (a manual PI project from 2026-07-31) appears in Needs Attention. Cleanup is deferred/unauthorized — Role's decision.
6. **Role Dashboard opens mid-page** (keeps the previous page's scroll, landed 2,014 px down at Recent Activity) — looks like the wrong page at first glance.

**MINOR**
7. A tool's detail page is project-shaped: primary **Resume Work** button, Git "Not a git repository", Documentation "Missing", Confidence 0%.
8. Tool card with a URL hides the reference text (how/where to run yt-dlp) — only visible on the detail page; **Open ↗** goes to upstream docs, which may not be what "open a tool" suggests.
9. No explicit way back from Role Dashboard; sidebar says "Mission Control" while the page is titled "Daily Command Center"; no sidebar item is highlighted on `#/dashboard`.
10. No UI to edit an external item after saving (status/next action/URL) — API `PATCH` only; will matter once KONTOOR items need their next action updated.

**COSMETIC**
11. Raw ISO timestamps inside next-action text.
12. Sidebar highlights "Projects" while viewing a tool's detail page.

None of these block P3.6 validation, so none were fixed here (per the task rules).

## Tests

No production code changed → targeted regression only: `test_universal_ingestion`, `test_explicit_project_registration`, `test_daily_command_center`, `test_work_classification`, `test_mission_control_api`, `test_workspace_api`, `test_workspace_resume`, `test_dashboard_v2` → **159 passed, 0 failed**. All 15 runtime DB checksums identical before/after the test run.

## Runtime / User Data Modified (not Git content)

- `var/role_os_dashboard/role_os_workspace.db`: bolsa-de-trabajo overlay row (adopted, ROLE PERSONAL / project / active, canonical link) and one external row for yt-dlp (`6c3d71e658f3a4c1`, source `other`, 1 note). The 5 original rows unchanged; `integrity_check` ok.
- External `ROLE_KNOWLEDGE_OS\00_SYSTEM\role_os_projects.db`: two canonical Role OS projects created by adoption/save (bolsa-de-trabajo, yt-dlp) — 10 → 12 projects; `integrity_check` ok.
- Nothing else. Not created: KONTOOR items, Cobalt, FERREVOLT, Unger, CLIENTES work, bulk items. No rescan, no Resume Work click, no Discovery-root change.

## Recommendation

- **Do not close Phase 3 or start Windows autostart yet.** First: Role adds the two KONTOOR items (above) and re-runs the 30-second test with real KONTOOR data.
- Before autostart, consider a small follow-up addressing HIGH VALUE items 1–3 and 6 (startup scan freshness, commit-derived next actions, Where I Left Off placement, dashboard scroll reset) — each requires Role's approval; items 4–5 are Role data decisions.

---

# P3.6B — Daily Command Center Polish

*Approved corrective follow-up to the P3.6 friction log. Baseline `b8224a2`. **P3.6 remains IN PROGRESS — WAITING FOR REAL KONTOOR ITEMS.***

## Test / demo data removed (proof first, established delete APIs, backups taken)

Backups of the two affected DBs were taken before any change (session scratchpad `backup_p36b/`: `role_os_projects.db` sha256 `a521f1dc…`, `role_os_workspace.db` `3ad9a316…`).

| Record | Evidence | Action |
|---|---|---|
| **Role Test Project** (`9e9a671f…`, PI workspace *Ideas*) | Created by hand in the UI on 2026-07-31 (the day after the DB): description "just a tst on ideas", no notes/todos/decisions/deliverables, never updated, no discovery link, no adoption/registration; one session "Engineering" created 2 minutes later, never used, **no snapshots**. Self-declared test with zero information. | Session + project removed via `DELETE /pi/projects/{id}/ai-sessions/{sid}` and `DELETE /pi/projects/{id}`. Its orphaned Advisor recommendation ("Revisit Role Test Project — it's gone quiet", which then appeared in Needs Attention labelled "Ideas") was dismissed via `POST /advisor/recommendations/{id}/dismiss`. |
| **Active Project / Paused Project / Quiet Project** (`ef2f0b8f…`, `35ec05fe…`, `4371621c…`, PI workspace *Discovered*) | **Automated test pollution:** exact fixture names from `tests/test_executive_decision.py`; created 2026-08-05/06 (two of them 41 ms apart); linked to temp-folder discovery ids that never existed in the canonical overlay; no content, sessions, dependencies, capabilities or overlay rows. They stayed hidden until Role Test Project's recommendation was dismissed; then "Active Project" surfaced in Needs Attention labelled "Discovered". | Removed via `DELETE /pi/projects/{id}`; their three "gone quiet" Advisor recommendations dismissed. |

No filesystem directory was touched. **Root cause + regression protection:** `tests/conftest.py` only `setdefault`s the isolated DB paths, so a pytest run from a shell that inherited the launcher's real `ROLE_OS_*_DB_PATH` values would write into canonical data. `conftest.py` now refuses to run (`pytest.exit`, code 4) if any writable runtime path resolves inside `var/` or `ROLE_OS_WORKSPACE_DIR` — verified live (refused before touching anything) and unit-tested.

Left untouched (not proven pollution — Role's decision): a second, unlinked **"ROLE Commerce Factory"** PI project (`0c5e26e2…`, created 2026-08-02, the same day as the linked one) that appears as a second Commerce Factory entry in Needs Attention.

## Where I Left Off — misattributed snapshot

- **Provenance:** snapshot `f275dfd7…` was saved on 2026-08-21 at **12:26:56 PDT** into role-ecosystem's then-current session. Its accomplishments ("ROLE Commerce Factory — Phase 3 Local Provider Pipeline … Product Factory tests 246/246 …") and summary describe ROLE Commerce Factory's milestone, committed **3 minutes later** (`3080e35`, 12:30:17 PDT). role-ecosystem had no commits that day, and the summary is truncated at its first character ("l estado…"). Its `next_prompt` ("n8n orchestration design") could plausibly be role-ecosystem's, so the correct owner of the *whole* snapshot is not provable → **option B**.
- **Resolution:** a new additive, non-destructive invalidation: `ai_session_snapshots.invalidated_at` / `invalidated_reason` + `POST /pi/projects/{pid}/ai-sessions/{sid}/snapshots/{snap}/invalidate` (reason required). `get_latest_snapshot` — the single source of *current* continuity for Where I Left Off, Project Memory and Resume Work — skips invalidated snapshots. History (snapshot list, timeline, marked `[invalidated: …]`) keeps it verbatim. Content not edited, nothing re-associated, no replacement summary.
- **Current state:** Where I Left Off shows **ROLE_OS** (most recent real session "ROLE_OS — Continue this project"), "No next action recorded.", "**No current snapshot.**"

## Workspace rescan (approved)

`POST /workspace/rescan {}` on the existing single default root (`…\1 - IA PROJECTS`); `ROLE_OS_DISCOVERY_ROOTS` unset, nothing broader scanned. Freshness went from **353.8 h (stale) to 0.0 h (fresh)**, and the stale banner is gone. Folders found went from 23 to **25**: new folders **FERREVOLT** and **KONTOOR** — discovered only, **not adopted**. The adopted set is identical (7, same ids); bolsa-de-trabajo is still registered + adopted; yt-dlp is still an external tool; nothing was auto-adopted. STALE now marks only the 3 projects with 30+ days of real inactivity instead of all of them.

## Fixes (code)

- **Next action quality:** in the Daily Command Center, a latest-commit (or CHANGELOG-unreleased) "next action" is now treated as history: `next_action = null`, `last_activity_note = {text, source}`. The UI shows "No next action recorded." with a small "Last activity: … (from latest git commit)". Forward sources are unchanged: manual entry → AI-session snapshot → NEXT_ACTION.md → TODO → ROADMAP → README next steps. Pending Work lists only genuine next actions / pending work. The Where I Left Off card applies the same rule. (The Projects page and Project Memory keep their existing provenance-labelled behavior.)
- **Why:** each active item's candidate reasons (recorded next action, pending work, blocked, high value, a specific suggestion **with its evidence**, staleness) are filtered so that a reason *every* active project shares is dropped. "Most recently active project" is added only when it is unique. If the first-ranked item has nothing distinguishing, it says so ("No single signal clearly sets it apart — it is first in the existing Executive Decision ranking."). No ranking change.
- **Layout:** the order is now filters → What should I do now? → **Where I Left Off** → Pending Work → Needs Attention → Active | Completed → Tools | Role Dashboard → Daily Session. The same element was moved, not duplicated. Live, Where I Left Off starts at 968 px (the first viewport is 959 px), versus the bottom of a ~4,000 px page before.
- **Role Dashboard:** every route change now starts at the top (`window.scrollTo(0, 0)` in the router). Live: 2,599 px before the click → 0 on `#/dashboard`. The Dashboard header gets a **← Daily Command Center** link, and the sidebar highlights Daily Command Center while the Dashboard is open.
- **Tools / external detail:** for `kind = tool` the primary action is **Open ↗** (when a URL exists); Resume Work appears only as a secondary link when a real AI session exists. External items (no folder) no longer show Git / Documentation / Repositories / Assets / Tests or "Full boundary review". The reference text now shows even when a URL exists (Command Center cards).
- **Terminology:** the sidebar label is now **Daily Command Center** (was "Mission Control"). The route `#/home`, `GET /mission-control` and the internal Mission Control service name are unchanged.

## Tests

New `dashboard/tests/test_daily_command_center_polish.py` (17 tests): canonical-path guard; snapshot invalidation (API, reason required, 404 for the wrong session, history kept, timeline label, never reaches Mission Control continuity); commit → last activity, not next action; forward NEXT_ACTION.md kept; manual next action kept; honest empty-state strings; why differentiation (shared reasons dropped, unique most-recent only, honest fallback, a single item keeps its reasons); Where I Left Off order (moved, not duplicated); scroll reset + back link; sidebar label; tool primary action / Resume only with a session; reference visible with a URL; external tool payload. Updated (intended changes only): the P3.3 layout-order and empty-state wording tests, and the navigation highlight-map literal. Focused + neighboring suites: 267 passed. **Full suite: 1,500 passed, 0 failed** (1,483 + 17). All 15 runtime DB checksums identical before/after the full run.

## 30-second test (after P3.6B, live)

| # | Question | Before | After |
|---|---|---|---|
| 1 | What first? | PASS | **PASS** — ROLE Commerce Factory |
| 2 | Why? | PARTIAL | **PASS** — "Suggested: Consider shipping/launching — Health score 82 with commercial readiness 'client-ready'", "No activity in 34 days" (both distinguishing) |
| 3 | What else is pending? | PARTIAL | **PASS** — only genuine next actions (role-ecosystem from ROADMAP.md, ROLE MASTER from TODO.md); the others honestly say "No next action recorded." |
| 4 | Active projects? | PASS | **PASS** — 6 |
| 5 | Tools? | PASS | **PASS** — yt-dlp with Open ↗ **and** how to run it |
| 6 | Domains? | PASS | **PASS** — All 7 · KONTOOR 0 · UNGER 0 · ROLE PERSONAL 7 · CLIENTES 0 |
| 7 | Where did I leave off? | PARTIAL | **PASS** — right below the recommendation; ROLE_OS, honest "No current snapshot." |
| 8 | Continue? | PASS | **PASS** |
| 9 | Open Role Dashboard? | PASS | **PASS** — opens at the top, clear way back |

## Remaining friction (not fixed — out of scope or Role's decision)

- **HIGH VALUE (data decision):** the duplicate unlinked "ROLE Commerce Factory" PI project in Needs Attention.
- **MINOR:** Operational Intelligence still describes ROLE_OS as "with an open next action" based on a commit-derived next action (Advisor/OI wording was not redesigned here). ROLE_KNOWLEDGE_OS looks freshly active because Role OS writes its own DBs inside `ROLE_KNOWLEDGE_OS\00_SYSTEM`, while OI says "inactive 50 days". Dashboard v2 counts yt-dlp as a project ("Adopted Projects 8"). Deleting a PI project leaves its Advisor recommendations live (mitigated here by dismissing them). There is no UI to edit external items.
- **COSMETIC:** the tool Overview still lists Confidence / Move risk; raw timestamps in "Last activity"; the sidebar highlights "Projects" on a tool detail page.

## Runtime / user data modified in P3.6B (not Git content)

- `ROLE_KNOWLEDGE_OS\00_SYSTEM\role_os_projects.db`: removed 4 test/demo projects (Role Test Project, Active/Paused/Quiet Project) + 1 empty session; snapshot `f275dfd7…` invalidated (kept); additive snapshot columns. Projects 12 → 8, sessions 6 → 5; `integrity_check` ok.
- `ROLE_KNOWLEDGE_OS\00_SYSTEM\role_os_advisor.db`: 4 orphaned recommendations dismissed (plus the Advisor's normal health refresh); ok.
- `var/role_os_dashboard/role_os_workspace.db`: rescan cache (25 folders, 2026-09-25 08:46 UTC); adopted/registration rows unchanged; ok.
- Nothing else: no folders touched, Discovery roots unchanged, Resume Work not clicked.
