"""Unit tests for the deterministic Knowledge Extraction rules (Sprint 4):
pattern-based extractors for the seven supported object types."""

from __future__ import annotations

from app.extraction import rules


def content(*texts: str) -> list[dict]:
    return [{"role": "user", "text": t, "created_at": None} for t in texts]


def test_extract_projects_matches_keyword_lines():
    lines = rules.lines_from_content(content("Necesitamos definir el proyecto de expansion antes del viernes."))
    found = rules.extract_projects(lines)
    assert len(found) == 1
    title, confidence = found[0]
    assert "proyecto" in title.lower()
    assert 0 < confidence <= 1


def test_extract_decisions_matches_keyword_lines():
    lines = rules.lines_from_content(content("Decidimos usar Claude para el pipeline. Aprobado por todos."))
    found = rules.extract_decisions(lines)
    assert len(found) == 1
    assert "decidimos" in found[0][0].lower()


def test_extract_tasks_matches_keyword_lines():
    lines = rules.lines_from_content(content("Todavia esta pendiente revisar el presupuesto."))
    found = rules.extract_tasks(lines)
    assert len(found) == 1


def test_extract_ideas_matches_keyword_lines():
    lines = rules.lines_from_content(content("Se me ocurre una idea: podriamos automatizar el reporte semanal."))
    found = rules.extract_ideas(lines)
    assert len(found) == 1


def test_extract_people_finds_capitalized_names():
    found = rules.extract_people("Maria Gonzalez va a liderar el equipo junto con John Smith.")
    names = [name for name, _ in found]
    assert "Maria Gonzalez" in names
    assert "John Smith" in names


def test_extract_people_excludes_blocked_phrases():
    found = rules.extract_people("Usamos ROLE OS y Business Central para el proyecto.")
    names = [name for name, _ in found]
    assert "ROLE OS" not in names
    assert "Business Central" not in names


def test_extract_people_confidence_rises_with_mentions():
    multi_mention = rules.extract_people("Ana Torres dijo hola. Ana Torres volvio a escribir. Ana Torres confirmo.")
    single_mention = rules.extract_people("Ana Torres dijo hola.")
    assert multi_mention[0][0] == single_mention[0][0] == "Ana Torres"
    assert multi_mention[0][1] > single_mention[0][1]


def test_extract_documents_matches_document_extensions_only():
    found = rules.extract_documents("Adjunto el reporte final: budget_report.pdf y logo_final.png")
    titles = [t for t, _ in found]
    assert "budget_report.pdf" in titles
    assert "logo_final.png" not in titles


def test_extract_assets_matches_asset_extensions_only():
    found = rules.extract_assets("Adjunto el reporte final: budget_report.pdf y logo_final.png")
    titles = [t for t, _ in found]
    assert "logo_final.png" in titles
    assert "budget_report.pdf" not in titles


def test_extract_all_returns_all_seven_types():
    result = rules.extract_all(content("hola"))
    assert set(result.keys()) == {"Project", "Person", "Task", "Decision", "Idea", "Document", "Asset"}


def test_extract_all_finds_nothing_in_empty_content():
    result = rules.extract_all([])
    assert all(found == [] for found in result.values())


def test_pick_deduplicates_within_a_single_call():
    lines = ["Decidimos usar Claude.", "Decidimos usar Claude.", "Otra linea sin match."]
    found = rules.extract_decisions(lines)
    assert len(found) == 1
