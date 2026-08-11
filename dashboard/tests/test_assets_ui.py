"""Frontend wiring tests for Assets OS (Sprint C4). Same string-assertion
style as the other *_ui.py files -- no JS runtime/browser harness exists
in this repo; see dashboard/README.md for the manual verification
performed for actual rendering/interaction behavior.
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_assets_route_and_gallery_markup_present():
    body = client.get("/static/js/app.js").text
    assert "assets: renderAssetsPage" in body
    assert "assets-view-gallery-btn" in body
    assert "assets-view-list-btn" in body
    assert "asset-gallery-grid" in body


def test_assets_page_uses_canonical_api_only():
    body = client.get("/static/js/app.js").text
    start = body.index("async function loadAssetsResults")
    end = body.index("async function openAssetDetail")
    section = body[start:end]
    assert "/assets?" in section
    assert "/workspace/assets" not in section  # legacy endpoint no longer the gallery's source


def test_frontend_does_not_calculate_category_reusable_or_duplicates():
    """§14: frontend is presentation-only -- it must never compute
    category, reusable status, duplicate grouping, project identity, or
    MIME/type classification itself."""
    body = client.get("/static/js/app.js").text
    start = body.index("async function renderAssetsPage")
    end = body.index("async function openAssetDetail")
    section = body[start:end]
    for forbidden in (".duplicate_hash]", "byHash", "= category", "classify"):
        assert forbidden not in section, forbidden


def test_asset_card_shows_required_fields():
    body = client.get("/static/js/app.js").text
    start = body.index("function assetCardHtml")
    end = body.index("function assetListRowHtml")
    section = body[start:end]
    for field in (
        "a.filename",
        "a.project",
        "a.category",
        "a.reusable",
        "a.duplicate_group_id",
        "a.size_bytes",
        "a.modified_at",
    ):
        assert field in section, field


def test_asset_detail_actions_present():
    body = client.get("/static/js/app.js").text
    start = body.index("function assetDetailActionsHtml")
    end = body.index("function assetDetailPreviewHtml")
    section = body[start:end]
    assert "Open File" in section
    assert "Open Folder" in section
    assert "Copy Path" in section
    assert "Open Project" in section
    # No destructive action anywhere in the detail panel.
    assert "Delete" not in section


def test_asset_detail_no_destructive_actions_anywhere():
    body = client.get("/static/js/app.js").text
    start = body.index("function assetDetailHtml")
    end = body.index("async function openAssetDetail")
    section = body[start:end]
    for forbidden in ("data-asset-delete", "Delete Asset", "asset-detail-delete"):
        assert forbidden not in section, forbidden


def test_view_mode_preference_stored_locally():
    body = client.get("/static/js/app.js").text
    assert 'localStorage.getItem("roleos-assets-view")' in body
    assert 'localStorage.setItem("roleos-assets-view"' in body


def test_asset_filters_match_brief():
    body = client.get("/static/js/app.js").text
    start = body.index("const ASSET_FILTER_CHIPS")
    end = body.index("const ASSET_TYPE_ICONS")
    section = body[start:end]
    for label in (
        "All",
        "Reusable",
        "Favorites",
        "Logos",
        "Images",
        "Videos",
        "Documents",
        "Fonts",
        "Duplicates",
    ):
        assert f'"{label}"' in section, label


def test_explorer_asset_nav_opens_shared_asset_detail():
    body = client.get("/static/js/app.js").text
    start = body.index("function explorerHandleNav")
    end = body.index("const runExplorerUniversalSearch")
    section = body[start:end]
    assert 'nav === "asset"' in section
    assert "openAssetDetail(param)" in section


def test_project_hub_links_to_filtered_assets_view():
    body = client.get("/static/js/app.js").text
    start = body.index("async function renderProjectHubPage")
    end = body.index("ADVISOR PAGE")
    section = body[start:end]
    assert 'data-nav="assets"' in section
    assert "hub.assets_summary" in section
