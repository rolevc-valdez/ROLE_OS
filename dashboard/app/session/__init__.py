"""Daily Session domain (ROLE OS Dashboard MVP).

Owns its own SQLite database (see `Settings.session_db_path`), separate
from every other domain's store. Lets the user start and close a daily
work session (date, project, operation mode, objective, expected result),
generates a copyable Claude session-initialization prompt and an
Obsidian-compatible Markdown daily record, and keeps a small local
registry of ecosystem projects. No AI/LLM call is made anywhere in this
domain -- prompt and Markdown generation are pure string templating over
data the user already entered.
"""
