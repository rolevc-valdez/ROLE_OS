"""Workspace Adoption (Discovery Engine Sprint 2).

Lets the user adopt folders the read-only Discovery Engine
(`app.discovery`) already found on disk into a lightweight "workspace"
overlay, without ever copying discovery metadata into the database. The
filesystem stays the source of truth: this package's own SQLite file
(`Settings.workspace_db_path`) stores only two things --

1. a cache of the last scan (`workspace_scan_cache`), so the Workspace page
   doesn't re-scan the filesystem on every request; and
2. a small per-folder overlay (`adopted_projects`): priority, business
   value, status, tags, notes, and an ignore flag.

Everything else shown for a discovered project (name, git status, health
score, confidence, move risk, classification, ...) is re-read from the
cached scan at request time, never duplicated into a row.

This is intentionally separate from `app.projects` (the existing,
manually-created Project Intelligence records) -- that domain is untouched
by this package; both are surfaced together only in the UI layer.
"""
