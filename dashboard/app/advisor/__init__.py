"""AI Advisor domain (Epic 2).

A deterministic, rule-based recommendation engine that analyzes Projects,
Knowledge Cards, Capabilities, Dependencies, Health Scores, TODOs,
Deliverables, and Decisions to recommend what to do next — fully
explainable, and requiring no external AI API by default.

See `engine.py` for the orchestrator, `rules/` for the eight independent
signal-detection rules, `scoring.py` for the shared scoring toolkit,
`narrative.py` for the (swappable) explanation-text provider, and `db.py`
for persistence in its own SQLite database file.
"""
