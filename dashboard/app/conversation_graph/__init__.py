"""Sprint 5 — Knowledge Graph over imported conversations and extracted
knowledge objects.

A small, independent graph domain — separate from the Epic 3 Knowledge
Graph (`app/graph/`), which is built from an entirely different pipeline
(Project Intelligence, Advisor, and the Builder's `knowledge_cards`) and
has its own frozen, test-locked 12 node type / 12 relationship type
vocabulary. This domain has its own, much smaller vocabulary: 8 node
types (Conversation, Project, Person, Task, Decision, Idea, Document,
Asset) and exactly one relationship type ("contains"), computed on demand
from the imports and extraction databases -- no new persisted store, no
AI, no inferred relationships.
"""
