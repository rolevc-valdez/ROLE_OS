"""ROLE OS Knowledge Extraction Engine (Milestone 3).

A modular enrichment pipeline that turns a single parsed conversation into a
structured `KnowledgeCard`, and a corpus-level pass that links related
conversations once every card has been built.

Extractors (one responsibility each):
    summary.py        -> summary
    decisions.py       -> decisions, deliverables
    todos.py             -> open todos
    prompts.py             -> prompts
    entities.py               -> people, applications, vendors, urls, files,
                                  project/category classification, tags
    relationships.py             -> related_conversations (corpus-level)

Usage:
    from extractors import build_knowledge_card, attach_related_conversations

    cards = [build_knowledge_card(conv, msgs).to_dict() for conv, msgs in ...]
    attach_related_conversations(cards)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ._util import sentences, to_iso
from .decisions import extract_decisions, extract_deliverables
from .entities import (
    classify_project,
    extract_applications,
    extract_files,
    extract_people,
    extract_tags,
    extract_urls,
    extract_vendors,
)
from .prompts import extract_prompts
from .relationships import attach_related_conversations, compute_related
from .summary import extract_summary
from .todos import extract_todos

__all__ = [
    "KnowledgeCard",
    "build_knowledge_card",
    "attach_related_conversations",
    "compute_related",
]


def _status(text: str) -> str:
    low = text.lower()
    if any(x in low for x in ["completado", "terminado", "listo", "aprobado", "resolved", "fixed"]):
        return "Completed"
    if any(x in low for x in ["en progreso", "trabajando", "in progress", "pendiente", "falta", "todo"]):
        return "In Progress"
    return "Unknown"


@dataclass
class KnowledgeCard:
    """The enriched, per-conversation knowledge record produced by the pipeline."""

    conversation_id: str
    date: str
    updated: str
    title: str
    project: str
    secondary_projects: list[str] = field(default_factory=list)
    category: str = "GENERAL"
    summary: str = ""
    status: str = "Unknown"
    decisions: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    applications: list[str] = field(default_factory=list)
    vendors: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    related_conversations: list[str] = field(default_factory=list)
    # Deprecated alias for `files`, kept for backward compatibility with
    # Milestone 1/2 consumers (e.g. the dashboard) that read `assets`.
    assets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def build_knowledge_card(conversation: dict, messages: list[tuple[str, str]]) -> KnowledgeCard:
    """Run every per-conversation extractor and merge the results into one KnowledgeCard.

    `related_conversations` is left empty here — it is a corpus-level field
    filled in afterwards by `attach_related_conversations()` once every
    conversation in the export has been turned into a card.
    """
    title = conversation.get("title") or "Untitled"
    body = "\n".join(text for _, text in messages)
    lines = sentences(body)

    primary, secondary, category, base_tags = classify_project(title, body)
    prompts = extract_prompts(messages)
    applications = extract_applications(title, body)
    vendors = extract_vendors(title, body)
    files = extract_files(body)

    return KnowledgeCard(
        conversation_id=str(conversation.get("id") or conversation.get("conversation_id") or ""),
        date=to_iso(conversation.get("create_time")),
        updated=to_iso(conversation.get("update_time")),
        title=title,
        project=primary,
        secondary_projects=secondary,
        category=category,
        summary=extract_summary(title, prompts),
        status=_status(body),
        decisions=extract_decisions(lines),
        deliverables=extract_deliverables(lines),
        todos=extract_todos(lines),
        people=extract_people(body),
        applications=applications,
        vendors=vendors,
        urls=extract_urls(body),
        files=files,
        prompts=prompts,
        tags=extract_tags(base_tags, applications),
        related_conversations=[],
        assets=files,
    )
