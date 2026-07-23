"""Knowledge Graph domain (Epic 3).

Turns Projects, Knowledge Cards, Capabilities, Dependencies, and Advisor
Recommendations into one unified relationship graph. The graph itself owns
no persisted storage -- it is assembled on demand from the three existing
databases (Builder knowledge DB, Project Intelligence DB, Advisor DB) and
recomputed every time `engine.build_graph()` is called, the same
recompute-on-read pattern used by the Advisor in Epic 2.
"""
