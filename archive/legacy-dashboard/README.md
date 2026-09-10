# Legacy Project Dashboard (archived)

## What it was

`project-dashboard.html` was a small, self-contained, single-file HTML page ("Mapa de proyectos" / "Project Map"), built independently of the FastAPI `dashboard/app` and sharing no code, data, or route with it. It stored a hand-curated catalog of Role's projects/tools/scripts (name, category, kind, status, description, usage instructions, local path, and an optional URL) in the browser's own `localStorage`, under the key `role-project-map-v1`, with a small hardcoded `starter` list as its default seed data. It also carried a special "ROLE MASTER" card with dedicated buttons to copy a starter prompt and open ChatGPT, and to copy a `claude` CLI command for that folder.

## Why it was retired

Role OS 2.0 Phase 1 established Mission Control (`/`) as the one canonical landing/orientation experience, backed by real, automated Discovery + Workspace adoption instead of a manually-curated, browser-local catalog. Keeping both meant two competing, divergent ideas of "the map of Role's projects" — exactly the duplication `audits/ROLE_OS_1X_AUDIT.md` (Phase 0) flagged. This file was never wired into `dashboard/app` (no router, no shared code, no shared data) and had no other repository reference pointing users at it.

## When it was archived

2026-09-10, Role OS 2.0 Phase 1 Task 6.

## What replaced it

Mission Control (`GET /`, `GET /mission-control`) — the FastAPI dashboard's real, automated Discovery + Workspace + Project Memory + Executive Decision composition. See `docs/PHASE_1_TASK_4.md` and `docs/PHASE_1_TASK_6.md` for the full record, including which of this file's five matching real projects (ROLE OS, ROLE_KNOWLEDGE_OS, ROLE Commerce Factory, ROLE MASTER, role-ecosystem) already had their description/usage text migrated into the canonical `adopted_projects` overlay as a note.

## localStorage limitation

This is a **static HTML file preserved from the repository's working tree** — it cannot prove, and this task did not assume, what (if anything) a real browser's `localStorage` under the key `role-project-map-v1` currently holds beyond this file's own hardcoded `starter` array. If Role edited cards through this page's own UI at some point, those edits exist only in whichever browser profile was used, are not present anywhere in this repository, and were not migrated here. No export/backup JSON file (the page's own "Exportar" feature produces `role-projects-backup.json`) was found anywhere in this repository as of the archive date. If such browser-local edits matter, they must be recovered from that browser (via its DevTools → Application → Local Storage, or the page's own "Exportar" button while it's still openable) before that browser profile is lost.

## Where Role Master assets remain

`assets/role-master/RM-000.png` and `assets/role-master/rolevaldez_official.png` remain at their **original path** (`assets/role-master/`, repo root — not moved into this archive folder), since nothing else in the repository referenced or depended on relocating them, and no other current Role OS system consumes them. This archived HTML file's own image references (`assets/role-master/RM-000.png`, relative to the file's original location at the repository root) will **not resolve correctly** if this archived copy is opened directly from `archive/legacy-dashboard/` — this is an accepted, documented trade-off of preserving the file byte-for-byte rather than editing its paths. To view the images, open them directly from `assets/role-master/`.
