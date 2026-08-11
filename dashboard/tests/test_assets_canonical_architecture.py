"""Architectural guard tests (Sprint C4.1: Assets Canonicalization Audit).

These tests don't exercise behavior -- they inspect the source tree itself
so that a future change reintroducing a second asset implementation (a
second classifier, a second duplicate grouper, a legacy shim growing real
logic again, a screen bypassing `app.assets`) fails CI immediately instead
of silently drifting until the next manual audit.

Each test documents *why* the rule exists, not just what it checks, so a
legitimate exception can be added deliberately (via the allowlist below)
rather than by weakening the check.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

# Files legitimately allowed to define their own `def classify_category`/
# `def group_duplicates`/`def find_duplicates` -- i.e. the one canonical
# implementation itself. Anything else defining one of these names is a
# second implementation and the audit's whole point is to prevent that.
_CLASSIFY_ALLOWLIST = {APP_DIR / "assets" / "classification.py"}
_DUPLICATE_GROUPER_ALLOWLIST = {APP_DIR / "assets" / "service.py"}


def _iter_py_files():
    for path in APP_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _defines_function(tree: ast.Module, name: str) -> bool:
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        for node in ast.walk(tree)
    )


def test_no_second_classification_function_exists():
    """Classification (category/reusable/likely_logo) must have exactly
    one implementation, `app.assets.classification.classify_category`. A
    second `def classify_category` anywhere else in `app/` would mean a
    screen or service is deciding "what kind of file is this" on its own
    terms instead of asking the canonical classifier -- the exact
    duplication this audit sprint exists to catch."""
    offenders = []
    for path in _iter_py_files():
        if path in _CLASSIFY_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _defines_function(tree, "classify_category"):
            offenders.append(str(path))
    assert offenders == [], f"second classify_category() definition(s) found: {offenders}"


def test_no_second_duplicate_grouping_function_exists():
    """Duplicate detection (`group_duplicates`/`find_duplicates`) must
    have exactly one implementation, in `app.assets.service`. A second
    grouper elsewhere would silently disagree with `/assets/duplicates/
    {id}` about what counts as a duplicate -- exactly the
    `duplicate_group_id` inconsistency this audit sprint found and fixed
    once already (see `app.assets.service.index_project_assets`'s
    docstring)."""
    offenders = []
    for path in _iter_py_files():
        if path in _DUPLICATE_GROUPER_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _defines_function(tree, "group_duplicates") or _defines_function(
            tree, "find_duplicates"
        ):
            offenders.append(str(path))
    assert offenders == [], f"second duplicate-grouping function(s) found: {offenders}"


def test_legacy_workspace_assets_index_remains_a_thin_shim():
    """`app.workspace.assets_index` (Sprint 4's original module) must stay
    a pure re-export over `app.assets.*` -- no local `def` of its own. If
    it ever grows a real function body again, every one of its callers
    (`workspace.service`, `project_context.builder`, `dashboard.service`,
    `explorer.service`) silently starts reading from a second
    implementation instead of the canonical one."""
    path = APP_DIR / "workspace" / "assets_index.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    local_defs = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    assert local_defs == [], f"assets_index.py must have no local defs, found: {local_defs}"

    source = path.read_text(encoding="utf-8")
    assert "from app.assets" in source, "assets_index.py must import from app.assets"


def test_explorer_service_uses_canonical_assets_module():
    """Explorer's asset search results and Project Hub assets summary must
    be built from `app.assets`/`app.workspace.assets_index` (which itself
    delegates to `app.assets`), never a second per-Explorer asset
    mapper."""
    source = (APP_DIR / "explorer" / "service.py").read_text(encoding="utf-8")
    assert re.search(r"from app\.assets(\.\w+)? import|import app\.assets", source) or re.search(
        r"from app\.workspace import.*assets_index|from app\.workspace\.assets_index import",
        source,
    ), "explorer/service.py must import from app.assets (directly or via the workspace shim)"


def test_project_context_builder_uses_canonical_assets_module():
    """`ProjectContext.assets_count` and its recent-activity asset list
    must be computed via `app.assets`/`app.workspace.assets_index`, never
    a second per-project asset walk. This is the exact bug Sprint C1B
    fixed once (see `_asset_count`'s docstring: "not the cheap
    discovery_detail counter... which could disagree with what the Assets
    page actually lists")."""
    source = (APP_DIR / "project_context" / "builder.py").read_text(encoding="utf-8")
    assert "assets_index" in source, "project_context/builder.py must use the assets_index module"
    assert "index_assets_for_project" in source


def test_dashboard_service_uses_canonical_assets_module():
    """Dashboard's recent/reusable asset cards must come from the same
    canonical index every other screen uses, via `workspace.service.
    list_project_assets` (which itself delegates to `app.assets`), never
    an independent asset walk or count."""
    source = (APP_DIR / "dashboard" / "service.py").read_text(encoding="utf-8")
    assert "list_project_assets" in source


def test_assets_router_is_the_only_place_that_writes_asset_overrides():
    """`PATCH /assets/{id}` (routers/assets.py) must be the only HTTP
    surface that calls `app.assets.db`'s `set_override` -- a second write
    path would let a screen set reusable/category/favorite without going
    through the same validation (asset must exist in the live index).

    Checks the qualified `assets_db.set_override`/`app.assets.db.
    set_override` call, not the bare name `set_override` -- Workspace's
    unrelated boundary-override endpoint (`app.workspace.service.
    set_override`, Sprint 3: "treat as top-level project") happens to
    share the same function name for a completely different domain, and
    a bare-string check would false-positive on it."""
    offenders = []
    for path in _iter_py_files():
        if path.parts[-2:] == ("routers", "assets.py"):
            continue
        if "routers" not in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        if re.search(r"assets_db\.set_override|app\.assets\.db\.set_override", source):
            offenders.append(str(path))
    assert offenders == [], f"a second router writes asset overrides: {offenders}"


def test_frontend_assets_page_calls_canonical_api_not_legacy_endpoint():
    """The Assets gallery must call `/assets`, never the legacy
    `/workspace/assets` endpoint Sprint 4 originally exposed (still kept
    alive only as a backward-compatible delegate for any external
    caller)."""
    js_path = APP_DIR / "static" / "js" / "app.js"
    source = js_path.read_text(encoding="utf-8")
    assets_page_start = source.index("ASSETS PAGE")
    assets_page_section = source[assets_page_start : assets_page_start + 15000]
    assert "/workspace/assets" not in assets_page_section
    assert "/assets" in assets_page_section


def test_frontend_assets_page_does_not_compute_classification_client_side():
    """The Assets gallery must render server-provided `category`/
    `reusable`/`duplicate_group_id`/`mime_type` fields verbatim, never
    recompute them from a filename/extension in JavaScript -- the whole
    point of one canonical, deterministic, server-side classifier is that
    a file's category means the same thing everywhere it's shown."""
    js_path = APP_DIR / "static" / "js" / "app.js"
    source = js_path.read_text(encoding="utf-8")
    assets_page_start = source.index("ASSETS PAGE")
    assets_page_section = source[assets_page_start : assets_page_start + 15000]
    # A client-side classifier would need to branch on extension/filename
    # to decide a category -- these patterns would only show up in a
    # reimplementation, not in code that just renders `a.category`.
    for banned in ('.endsWith(".png")', ".endsWith('.png')", "classifyCategory", "isReusable("):
        assert banned not in assets_page_section, f"found client-side classification: {banned}"
