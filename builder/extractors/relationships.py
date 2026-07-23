"""Related-conversations extractor.

Unlike the other extractors, this one operates on the *whole* set of
already-built knowledge cards rather than a single conversation — a
conversation's related conversations can only be known once every
conversation has been classified and tagged.

Relatedness is a simple weighted overlap score across project, tags,
people, and applications. This is intentionally cheap (no embeddings/AI):
it is a rule-based relationship signal that can be swapped for a smarter
model later without changing the KnowledgeCard shape.
"""

from __future__ import annotations

from typing import Any

WEIGHT_PROJECT = 3
WEIGHT_TAG = 1
WEIGHT_PERSON = 2
WEIGHT_APPLICATION = 1


def _score(card_a: dict[str, Any], card_b: dict[str, Any]) -> int:
    score = 0
    if card_a.get("project") and card_a["project"] == card_b.get("project"):
        score += WEIGHT_PROJECT
    score += WEIGHT_TAG * len(set(card_a.get("tags", [])) & set(card_b.get("tags", [])))
    score += WEIGHT_PERSON * len(set(card_a.get("people", [])) & set(card_b.get("people", [])))
    score += WEIGHT_APPLICATION * len(
        set(card_a.get("applications", [])) & set(card_b.get("applications", []))
    )
    return score


def compute_related(cards: list[dict[str, Any]], max_related: int = 5) -> dict[str, list[str]]:
    """Compute related conversation IDs for every card in `cards`.

    Returns a mapping of conversation_id -> ordered list of related
    conversation_ids (most related first), capped at `max_related`.
    """
    related: dict[str, list[str]] = {}
    for card in cards:
        card_id = card.get("conversation_id")
        if not card_id:
            continue
        scored = []
        for other in cards:
            other_id = other.get("conversation_id")
            if not other_id or other_id == card_id:
                continue
            score = _score(card, other)
            if score > 0:
                scored.append((score, other_id))
        scored.sort(key=lambda x: (-x[0], x[1]))
        related[card_id] = [other_id for _, other_id in scored[:max_related]]
    return related


def attach_related_conversations(cards: list[dict[str, Any]], max_related: int = 5) -> list[dict[str, Any]]:
    """Mutate `cards` in place, setting each card's `related_conversations` field."""
    related_map = compute_related(cards, max_related=max_related)
    for card in cards:
        card["related_conversations"] = related_map.get(card.get("conversation_id"), [])
    return cards
