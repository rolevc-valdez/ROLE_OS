"""The one, shared definition of a discovered folder's stable identity.

A discovered folder has no database row until a user adopts it, so every
consumer -- the boundary/hierarchy pass in this package, and
`app.workspace.service`'s API ids -- needs the exact same deterministic id
derived from its `root_path`. Defined once here so the two can never drift
apart.
"""

from __future__ import annotations

import hashlib


def compute_item_id(root_path: str) -> str:
    return hashlib.sha1(root_path.encode("utf-8")).hexdigest()[:16]
