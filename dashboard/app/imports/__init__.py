"""Sprint B1 — ChatGPT conversation importer.

Owns its own SQLite file (see `Settings.imports_db_path`), separate from the
Builder-generated knowledge database and every other domain's store. This
package only normalizes and persists raw conversation metadata/content — it
performs no AI knowledge extraction, project matching, capability matching,
advisor generation, or graph inference. Those remain the Builder's job.
"""
