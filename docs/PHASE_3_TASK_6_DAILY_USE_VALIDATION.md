# Role OS 2.0 — P3.6 Daily Use Validation & Real Work Onboarding

**Status: IN PROGRESS — WAITING FOR ROLE INPUT** (the two KONTOOR real-data examples must come from Role; nothing was invented).

*Validation record. No production code was changed. Real onboarding was done only through the existing application API/UI.*

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
