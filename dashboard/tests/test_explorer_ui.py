"""Frontend wiring tests for Explorer 2.0 (Sprint C3). Same string-
assertion style as the other *_ui.py files -- no JS runtime/browser
harness exists in this repo; see dashboard/README.md for the manual
verification performed for actual rendering/interaction behavior.
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_explorer_route_and_universal_search_present():
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200
    body = resp.text
    assert "explorer: renderExplorerPage" in body
    assert "phub: renderProjectHubPage" in body
    assert "explorer-universal-search-input" in body
    assert "/explorer/search" in body


def test_header_search_opens_explorer_on_enter():
    body = client.get("/static/js/app.js").text
    section = body[
        body.index('searchInput.addEventListener("input"') : body.index("document.addEventListener")
    ]
    assert 'e.key !== "Enter"' in section
    assert 'navigate("explorer", q)' in section


def test_frontend_performs_no_ranking_or_dedup_logic():
    """§ Frontend requirements: presentation only -- no ranking logic, no
    deduplication, no ProjectContext recomputation. The universal-search
    rendering functions must consume `groups`/`counts` exactly as
    returned, never sort, filter-by-uniqueness, or recompute health/next
    action themselves."""
    body = client.get("/static/js/app.js").text
    start = body.index("function renderExplorerUniversalResults")
    end = body.index("function explorerHandleNav")
    section = body[start:end]
    assert ".sort(" not in section
    assert "healthTier(" not in section
    assert "new Set(" not in section  # no client-side de-duplication


def test_project_hub_composes_single_endpoint():
    body = client.get("/static/js/app.js").text
    start = body.index("async function renderProjectHubPage")
    end = body.index("// =======", start + 10)
    section = body[start:end]
    # Exactly one fetch -- the frontend must not aggregate multiple APIs.
    assert section.count("fetchJSON(") == 1
    assert "/explorer/project/" in section


def test_explorer_filters_match_brief():
    body = client.get("/static/js/app.js").text
    start = body.index("const EXPLORER_FILTER_TYPES")
    end = body.index("const EXPLORER_TYPE_ICONS")
    section = body[start:end]
    for label in (
        "All",
        "Projects",
        "Sessions",
        "Snapshots",
        "Knowledge",
        "Assets",
        "Commits",
        "Activity",
        "Recommendations",
        "Markdown",
    ):
        assert f'"{label}"' in section, label


def test_result_card_shows_required_fields():
    body = client.get("/static/js/app.js").text
    start = body.index("function explorerResultCardHtml")
    end = body.index("function explorerGroupHtml")
    section = body[start:end]
    for field in (
        "item.title",
        "item.project",
        "item.summary",
        "item.date",
        "item.origin",
        "item.actions",
    ):
        assert field in section, field


# ---------------------------------------------------------------------------
# Sprint C3.1: legacy "Imported Conversations" dependencies removed from
# Explorer entirely -- not merely hidden underneath the universal search.
# ---------------------------------------------------------------------------


def test_legacy_imported_conversations_dashboard_removed_from_explorer():
    body = client.get("/static/js/app.js").text
    start = body.index("async function renderExplorerPage")
    # Bound the search window to renderExplorerPage's own function body,
    # not the whole file (openConversationDetail below it still legitimately
    # calls /import/conversations/{id} for the shared detail overlay).
    end = body.index("function exportConversation", start)
    section = body[start:end]
    assert "/import/metrics" not in section
    assert "/import/facets" not in section
    assert "/import/conversations?" not in section
    assert "explorer-metrics" not in section
    assert "explorer-source-select" not in section
    assert "explorer-list-wrap" not in section
    assert "Imported Conversations" not in section


def test_legacy_explorer_functions_no_longer_exist():
    body = client.get("/static/js/app.js").text
    for legacy_fn in (
        "function loadExplorerMetrics",
        "function loadExplorerFacets",
        "function wireExplorerControls",
        "function loadExplorerList",
        "function explorerTableHtml",
        "function explorerPaginationHtml",
        "function defaultExplorerState",
        "function importedAfterForPreset",
    ):
        assert legacy_fn not in body, legacy_fn


def test_explorer_runs_universal_search_immediately_on_load():
    """The universal search must be the page's default content, not
    something that only appears once the user starts typing -- an empty
    query is a real, meaningful request (a bounded browse), not a no-op."""
    body = client.get("/static/js/app.js").text
    start = body.index("async function renderExplorerPage")
    end = body.index("function exportConversation", start)
    section = body[start:end]
    assert "runExplorerUniversalSearch(initialQuery.trim())" in section


def test_conversation_detail_overlay_still_reachable_but_not_a_dashboard():
    """The shared conversation detail overlay (used by Explorer search
    results' "Open Conversation" action and by the Knowledge Graph page)
    is intentionally kept -- only the standalone browsing/metrics
    dashboard was removed."""
    body = client.get("/static/js/app.js").text
    assert "async function openConversationDetail" in body
    assert "explorer-conversation-section" not in body
