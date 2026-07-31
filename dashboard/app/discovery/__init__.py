"""Discovery Engine — Sprint 1 (read-only filesystem audit).

Implements the "Discovery Pipeline" and "Metadata Extraction Pipeline" from
docs/architecture/08_IMPORT_ENGINE_PROPOSAL.md, sections 5-11, scoped to
Sprint 1 only: scan a folder tree, detect signals, classify, score, and
report. It never writes to the Projects database and never modifies any
file it scans — see `scanner.py` and `service.py` docstrings for the
read-only guarantee.

Project import (writing discovered data into the `projects` table) is out
of scope here and belongs to a later sprint per the rollout plan (§18).
"""
