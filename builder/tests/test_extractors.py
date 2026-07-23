"""Unit tests for the individual extractors under builder/extractors/."""

from __future__ import annotations

from extractors.decisions import extract_decisions, extract_deliverables
from extractors.entities import (
    classify_project,
    extract_applications,
    extract_files,
    extract_people,
    extract_tags,
    extract_urls,
    extract_vendors,
)
from extractors.prompts import extract_prompts
from extractors.relationships import attach_related_conversations, compute_related
from extractors.summary import extract_summary
from extractors.todos import extract_todos


def test_extract_summary_prefers_first_substantial_prompt():
    prompts = ["hi", "Quiero definir el plan completo para el proyecto ROLE Master Factory"]
    assert extract_summary("Untitled", prompts) == prompts[1]


def test_extract_summary_falls_back_to_title():
    assert extract_summary("My Title", ["hi", "ok"]) == "My Title"


def test_extract_decisions_matches_keywords():
    lines = ["Decidimos usar Claude.", "Nada relevante aqui."]
    assert extract_decisions(lines) == ["Decidimos usar Claude."]


def test_extract_deliverables_matches_keywords():
    lines = ["El entregable final quedo listo.", "Otra linea."]
    assert extract_deliverables(lines) == ["El entregable final quedo listo."]


def test_extract_todos_matches_keywords():
    lines = ["Falta aprobar presupuesto.", "Ya terminado."]
    assert extract_todos(lines) == ["Falta aprobar presupuesto."]


def test_extract_prompts_filters_to_user_role_and_limit():
    messages = [("user", "one"), ("assistant", "two"), ("user", "three")]
    assert extract_prompts(messages) == ["one", "three"]
    assert extract_prompts(messages, limit=1) == ["one"]


def test_classify_project_matches_known_rules():
    project, secondary, category, tags = classify_project(
        "ROLE Master Factory planning", "Vamos a usar ROLE Master Factory"
    )
    assert project == "ROLE_MASTER_FACTORY"
    assert category == "PROJECT"
    assert "role-master-factory" in tags


def test_classify_project_falls_back_to_category():
    project, secondary, category, tags = classify_project(
        "Random chat", "Tuve un error al instalar el software"
    )
    assert project == "IT_SUPPORT"
    assert category == "IT_SUPPORT"


def test_classify_project_falls_back_to_general():
    project, secondary, category, tags = classify_project("Untitled", "")
    assert project == "GENERAL"


def test_extract_applications_matches_known_apps():
    assert extract_applications("", "We used Claude and GitHub today") == ["Claude", "GitHub"]


def test_extract_vendors_matches_known_vendors():
    assert extract_vendors("", "Talked to Microsoft support") == ["Microsoft"]


def test_extract_vendors_empty_when_no_match():
    assert extract_vendors("", "Nothing relevant here") == []


def test_extract_urls_dedupes_and_limits():
    body = "See https://example.com and again https://example.com and https://other.com"
    assert extract_urls(body) == ["https://example.com", "https://other.com"]


def test_extract_files_matches_common_extensions():
    body = "Adjunto plan.pdf y notas.docx, tambien logo.PNG"
    files = extract_files(body)
    assert "plan.pdf" in files
    assert "notas.docx" in files
    assert "logo.PNG" in files


def test_extract_people_filters_blocked_terms():
    body = "Reunion con Juan Perez y con Google Drive."
    people = extract_people(body)
    assert "Juan Perez" in people
    assert "Google Drive" not in people


def test_extract_tags_merges_base_and_application_tags():
    tags = extract_tags(["role-master-factory"], ["Claude", "GitHub"])
    assert tags == ["role-master-factory", "claude", "github"]


def test_compute_related_scores_shared_project_highest():
    cards = [
        {"conversation_id": "a", "project": "P1", "tags": [], "people": [], "applications": []},
        {"conversation_id": "b", "project": "P1", "tags": [], "people": [], "applications": []},
        {"conversation_id": "c", "project": "P2", "tags": [], "people": [], "applications": []},
    ]
    related = compute_related(cards)
    assert related["a"] == ["b"]
    assert related["c"] == []


def test_attach_related_conversations_mutates_cards_in_place():
    cards = [
        {"conversation_id": "a", "project": "P1", "tags": [], "people": [], "applications": []},
        {"conversation_id": "b", "project": "P1", "tags": [], "people": [], "applications": []},
    ]
    attach_related_conversations(cards)
    assert cards[0]["related_conversations"] == ["b"]
    assert cards[1]["related_conversations"] == ["a"]
