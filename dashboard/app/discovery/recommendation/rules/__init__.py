"""The recommendation rule registry.

Precedence (documented, not hidden in code flow): each rule owns an
explicit `PRIORITY` integer, and `engine.recommend()` runs every rule,
keeps only the ones that fired (didn't return `None`), and picks the
**highest-priority** one -- never "first in this list wins" by accident.
List order below is for readability only; it has no effect on the result
(verified by `test_discovery_recommendation_rules.py`'s
`test_rule_order_in_list_does_not_affect_precedence`).

Precedence table, highest first, and *why* each rule outranks the next:

| Priority | Rule                    | Outranks lower rules because...                                   |
|----------|-------------------------|--------------------------------------------------------------------|
| 100      | `non_project`           | Nothing is recommended for consolidation if it isn't a project at all -- move risk, classification detail, everything else is moot. |
| 90       | `high_move_risk`        | Whether relocating is *safe* matters more than *what kind* of real folder this is -- a risky Brand/Asset or Documentation folder still needs manual review first. |
| 80       | `brand_asset_project`   | A creative-asset collection is never a candidate for "Move into IA PROJECTS" (that's for code/website projects) or Documentation-specific review. |
| 70       | `documentation_project` | Docs-only folders always need a human to confirm ownership -- more specific than the general real-project rule below. |
| 60       | `real_project`          | The general "is this a healthy, low-risk, real project?" rule for Software/Website/Mixed Project. |
| 0        | `fallback`              | Always fires; catches anything no other rule recognized (e.g. `Unknown`). Lowest priority so any real rule always wins if one applies. |

Exactly one rule fires per project in practice today, because
classification is mutually exclusive across Non-project/Brand-Asset/
Documentation/real-project-kinds/Unknown -- except `high_move_risk`, which
is classification-agnostic and can fire alongside a classification-specific
rule; its priority (90) is what makes it win over Brand/Asset (80),
Documentation (70), and real-project (60) when it does.
"""

from __future__ import annotations

from app.discovery.recommendation.rules import (
    brand_asset_project,
    documentation_project,
    fallback,
    high_move_risk,
    non_project,
    real_project,
)

RULES = [
    non_project,
    high_move_risk,
    brand_asset_project,
    documentation_project,
    real_project,
    fallback,
]
