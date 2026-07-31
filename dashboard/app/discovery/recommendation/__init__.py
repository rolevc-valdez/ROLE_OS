"""Move/keep recommendation for a discovered folder (Sprint 1.5: rule-based
engine architecture -- see `docs/product/DECISIONS.md`).

One of exactly six actions, chosen by an ordered set of independent,
individually testable rules (`rules/`) over signals `classifier.py` and
`health.py` already computed -- no filesystem access, no ML, always paired
with the specific reasons behind the call so a human can override it. This
package only *recommends*; nothing here moves, renames, merges, or deletes
anything.

`recommend()` and `apply_container_child_overrides()` are re-exported here
unchanged from Sprint 1's flat `recommendation.py` module for every
existing caller (`classifier.py`, `service.py`, tests).
"""

from __future__ import annotations

from app.discovery.recommendation.container_override import apply_container_child_overrides
from app.discovery.recommendation.engine import VALID_ACTIONS, recommend

__all__ = ["recommend", "apply_container_child_overrides", "VALID_ACTIONS"]
