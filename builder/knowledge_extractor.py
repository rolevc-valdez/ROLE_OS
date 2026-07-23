"""Backward-compatible entry point for the knowledge extraction engine.

As of Milestone 3, the actual extraction logic lives in the modular
`extractors/` package (summary, decisions, todos, prompts, entities,
relationships) and is orchestrated by `extractors.build_knowledge_card`.

This module is kept so existing code — including `builder.py` — can keep
doing `from knowledge_extractor import build_card, KnowledgeCard` without
any changes. `build_card` is a thin alias for
`extractors.build_knowledge_card`.
"""

from __future__ import annotations

from extractors import KnowledgeCard, attach_related_conversations, build_knowledge_card

__all__ = ["KnowledgeCard", "build_card", "attach_related_conversations"]


def build_card(conversation: dict, messages: list[tuple[str, str]]) -> KnowledgeCard:
    """Build a single conversation's KnowledgeCard. See extractors.build_knowledge_card."""
    return build_knowledge_card(conversation, messages)
