"""Sprint 4 — Knowledge Extraction.

Extracts structured objects (Project, Person, Task, Decision, Idea,
Document, Asset) from imported conversations using deterministic,
rule-based pattern matching only -- no external AI/LLM call, no
summarization, no free-form generation. Owns its own SQLite file (see
`Settings.extraction_db_path`), separate from every other domain's store.
"""
