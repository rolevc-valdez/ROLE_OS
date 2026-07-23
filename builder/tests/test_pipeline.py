"""Tests for the extraction pipeline orchestrator (extractors.build_knowledge_card)
and its backward-compatible alias in knowledge_extractor.build_card.
"""

from __future__ import annotations

from extractors import KnowledgeCard, build_knowledge_card
from knowledge_extractor import build_card


CONVERSATION = {
    "id": "conv-x",
    "create_time": 1700000000,
    "update_time": 1700003600,
    "title": "ROLE Master Factory planning",
}

MESSAGES = [
    ("user", "Quiero definir el plan para ROLE Master Factory. Adjunto plan.pdf."),
    ("assistant", "Decidimos usar Claude para el pipeline. Aprobado. Ver https://github.com/rolevc/role-master"),
]


def test_build_knowledge_card_returns_knowledge_card_instance():
    card = build_knowledge_card(CONVERSATION, MESSAGES)
    assert isinstance(card, KnowledgeCard)


def test_build_knowledge_card_populates_all_required_fields():
    card = build_knowledge_card(CONVERSATION, MESSAGES).to_dict()

    assert card["conversation_id"] == "conv-x"
    assert card["summary"]
    assert card["decisions"]
    assert card["todos"] == []
    assert card["deliverables"] == []
    assert card["prompts"] == [MESSAGES[0][1]]
    assert card["people"] == ["Master Factory"]
    assert card["applications"] == ["Claude", "GitHub"]
    assert card["vendors"] == []
    assert card["urls"] == ["https://github.com/rolevc/role-master"]
    assert card["files"] == ["plan.pdf"]
    assert "role-master-factory" in card["tags"]
    assert card["related_conversations"] == []


def test_build_knowledge_card_keeps_assets_alias_in_sync_with_files():
    card = build_knowledge_card(CONVERSATION, MESSAGES).to_dict()
    assert card["assets"] == card["files"]


def test_knowledge_extractor_build_card_matches_pipeline_output():
    """Milestone 1/2 compatibility: knowledge_extractor.build_card must behave
    exactly like extractors.build_knowledge_card."""
    legacy = build_card(CONVERSATION, MESSAGES).to_dict()
    pipeline = build_knowledge_card(CONVERSATION, MESSAGES).to_dict()
    assert legacy == pipeline
