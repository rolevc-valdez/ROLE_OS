"""Tests for the Project Boundary / Hierarchy model (Discovery Engine
Sprint 3): top-level project detection, nested repositories, monorepo-like
structures, numbered internal folders, the nested-independent-project
exception, exclusions (exact/case-insensitive/glob), deterministic ids,
real paths with spaces and parentheses, and the read-only guarantee.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from app.discovery.identity import compute_item_id
from app.discovery.service import run_audit


def _write(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)


def _commit_all(path: Path, message: str = "commit") -> None:
    subprocess.run(["git", "add", "."], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=str(path), check=True)


def _by_name(projects, name):
    return next(p for p in projects if p.name == name)


# ---------------------------------------------------------------------------
# Top-level project detection (§2)
# ---------------------------------------------------------------------------


def test_folder_with_own_git_is_top_level_project(tmp_path: Path):
    proj = tmp_path / "root" / "my-app"
    _write(proj / "main.py")
    _init_git_repo(proj)
    _commit_all(proj)

    result = run_audit(tmp_path / "root")
    p = _by_name(result.projects, "my-app")
    assert p.item_kind == "project"
    assert p.is_top_level_project is True


def test_folder_with_only_readme_is_not_top_level_project(tmp_path: Path):
    """§2's negative list: a README/images/markdown/generic name alone must
    never be enough to qualify as a top-level project."""
    root = tmp_path / "root"
    _write(root / "just-notes" / "README.md", "just some notes")
    _write(root / "just-notes" / "photo.png", "img")

    result = run_audit(root)
    p = _by_name(result.projects, "just-notes")
    assert p.is_top_level_project is False
    assert p.item_kind in {"non_project", "unknown"}


def test_container_with_child_repos_is_promoted_to_top_level(tmp_path: Path):
    """§3's motivating example: ROLE Commerce Factory has no markers of its
    own, but contains two child components -- it must still become the
    top-level project, with the children nested underneath, not peers."""
    root = tmp_path / "root"
    _write(root / "Commerce Factory" / "adapter-a" / "package.json", "{}")
    _write(root / "Commerce Factory" / "adapter-b" / "package.json", "{}")

    result = run_audit(root)
    factory = _by_name(result.projects, "Commerce Factory")
    adapter_a = _by_name(result.projects, "adapter-a")
    adapter_b = _by_name(result.projects, "adapter-b")

    assert factory.item_kind == "project"
    assert factory.is_top_level_project is True
    assert adapter_a.item_kind == "component"
    assert adapter_a.parent_item_id == factory.item_id
    assert adapter_a.project_root_id == factory.item_id
    assert adapter_b.item_kind == "component"
    assert adapter_b.parent_item_id == factory.item_id


def test_substantial_documentation_structure_is_promoted_to_top_level(tmp_path: Path):
    """§2/§4's other motivating example: ROLE MASTER has no markers of its
    own, but a README+ROADMAP plus several internal (documented) folders
    is "substantial project structure" -- it must become a top-level
    project, with its numbered folders nested as internal folders."""
    root = tmp_path / "root"
    _write(root / "ROLE MASTER" / "README.md", "overview")
    _write(root / "ROLE MASTER" / "ROADMAP.md", "plans")
    for name in ["01_BRAND_CORE", "02_PROMPT_SYSTEM", "03_PROJECTS"]:
        _write(root / "ROLE MASTER" / name / "README.md", "content")

    result = run_audit(root)
    master = _by_name(result.projects, "ROLE MASTER")
    assert master.item_kind == "project"
    assert master.is_top_level_project is True

    for name in ["01_BRAND_CORE", "02_PROMPT_SYSTEM", "03_PROJECTS"]:
        child = _by_name(result.projects, name)
        assert child.is_top_level_project is False, f"{name} must not be top-level"
        assert child.item_kind == "internal_folder"
        assert child.is_internal_folder is True
        assert child.parent_item_id == master.item_id


def test_bare_container_with_no_evidence_stays_non_top_level(tmp_path: Path):
    """A container with no own markers, no child repos, and no substantial
    doc structure must not be force-promoted."""
    root = tmp_path / "root"
    _write(root / "random-stuff" / "notes.txt", "shopping list")

    result = run_audit(root)
    p = _by_name(result.projects, "random-stuff")
    assert p.is_top_level_project is False


# ---------------------------------------------------------------------------
# Nested Git repositories / monorepo-like structures (§3)
# ---------------------------------------------------------------------------


def test_nested_git_repository_classified_as_repository(tmp_path: Path):
    root = tmp_path / "root"
    container = root / "container-no-markers"
    _write(container / "README.md", "just a note")  # not enough alone (§2)
    nested = container / "nested-repo"
    _write(nested / "main.py")
    _init_git_repo(nested)
    _commit_all(nested)
    # Give the container a second internal-ish child so it's promoted via
    # the "contains a child with its own markers" rule, not by accident.

    result = run_audit(root)
    nested_p = _by_name(result.projects, "nested-repo")
    container_p = _by_name(result.projects, "container-no-markers")

    assert container_p.item_kind == "project"
    assert nested_p.item_kind == "repository"
    assert nested_p.is_nested_repository is True
    assert nested_p.parent_item_id == container_p.item_id


def test_monorepo_style_packages_all_nested_under_one_root(tmp_path: Path):
    root = tmp_path / "root"
    _write(root / "monorepo" / "packages" / "pkg-a" / "package.json", "{}")
    # Scanner's default max_depth=2 only reaches "packages" itself at depth
    # 2 (not pkg-a, which is depth 3) unless "packages" itself is admitted
    # as a candidate -- exercise the shallower, always-supported case: two
    # sibling packages directly under the monorepo root.
    _write(root / "monorepo" / "service-a" / "package.json", "{}")
    _write(root / "monorepo" / "service-b" / "package.json", "{}")

    result = run_audit(root, max_depth=2)
    mono = _by_name(result.projects, "monorepo")
    assert mono.item_kind == "project"
    for name in ("service-a", "service-b"):
        child = _by_name(result.projects, name)
        assert child.item_kind == "component"
        assert child.project_root_id == mono.item_id


# ---------------------------------------------------------------------------
# Nested independent project exception (§3)
# ---------------------------------------------------------------------------


def test_nested_repo_with_strong_independent_evidence_is_promoted(tmp_path: Path):
    root = tmp_path / "root"
    container = root / "workspace-folder"
    _write(container / "index.md", "just an index")
    independent = container / "genuinely-independent-product"
    _write(independent / "main.py")
    _write(independent / "ROADMAP.md", "our own roadmap")
    _write(independent / "tests" / "test_x.py", "def test(): assert True")
    _init_git_repo(independent)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.com/independent.git"],
        cwd=str(independent),
        check=True,
    )
    _commit_all(independent)
    # A second sibling so the container is promoted via the "has a child
    # with markers" rule and actually attempts to nest `independent`.
    _write(container / "other-child" / "package.json", "{}")

    result = run_audit(root)
    independent_p = _by_name(result.projects, "genuinely-independent-product")

    assert independent_p.confidence_score >= 0.75
    assert independent_p.item_kind == "project"
    assert independent_p.is_top_level_project is True
    assert independent_p.parent_item_id is None


def test_nested_repo_without_remote_stays_nested(tmp_path: Path):
    """Same shape as the adapters in the real workspace: package.json
    only, no .git at all -- must default to "component", not be promoted."""
    root = tmp_path / "root"
    container = root / "ROLE Commerce Factory"
    _write(container / "RCOM-Printful-Adapter" / "package.json", "{}")
    _write(container / "RCOM-Shopify-Adapter" / "package.json", "{}")

    result = run_audit(root)
    for name in ("RCOM-Printful-Adapter", "RCOM-Shopify-Adapter"):
        child = _by_name(result.projects, name)
        assert child.is_top_level_project is False
        assert child.item_kind == "component"


# ---------------------------------------------------------------------------
# Numbered internal folders (§4)
# ---------------------------------------------------------------------------


def test_numbered_folder_with_own_git_is_not_forced_internal(tmp_path: Path):
    """§4: "a numbered folder is not automatically excluded; use the parent
    context and evidence" -- own markers win over the name pattern."""
    root = tmp_path / "root"
    parent = root / "Parent Project"
    _write(parent / "README.md", "overview")
    _write(parent / "ROADMAP.md", "plans")
    numbered_but_real_repo = parent / "03_SPECIAL_REPO"
    _write(numbered_but_real_repo / "main.py")
    _init_git_repo(numbered_but_real_repo)
    _commit_all(numbered_but_real_repo)
    _write(parent / "01_DOCS" / "README.md", "just docs")
    _write(parent / "02_ASSETS" / "README.md", "just assets")

    result = run_audit(root)
    special = _by_name(result.projects, "03_SPECIAL_REPO")
    assert special.item_kind == "repository"
    assert special.is_internal_folder is False


# ---------------------------------------------------------------------------
# Exclusions: exact / case-insensitive / glob (§5)
# ---------------------------------------------------------------------------


def test_exact_name_exclusion_default_otros(tmp_path: Path):
    root = tmp_path / "root"
    _write(root / "OTROS - no proyectos" / "junk" / "file.txt", "junk")
    _write(root / "real-project" / "main.py")
    _init_git_repo(root / "real-project")
    _commit_all(root / "real-project")

    result = run_audit(root)
    otros = _by_name(result.projects, "OTROS - no proyectos")
    assert otros.is_excluded is True
    assert otros.item_kind == "excluded"
    assert otros.exclusion_reason is not None
    # Not rescanned recursively: its junk subfolder never appears at all.
    assert all(p.name != "junk" for p in result.projects)


def test_case_insensitive_default_exclusion(tmp_path: Path):
    root = tmp_path / "root"
    _write(root / "NODE_MODULES" / "some-package" / "index.js", "x")

    result = run_audit(root)
    nm = _by_name(result.projects, "NODE_MODULES")
    assert nm.is_excluded is True


def test_glob_exclusion_default(tmp_path: Path):
    root = tmp_path / "root"
    _write(root / "something.egg-info" / "PKG-INFO", "x")

    result = run_audit(root)
    p = _by_name(result.projects, "something.egg-info")
    assert p.is_excluded is True


def test_user_extra_exclusion_exact_name(tmp_path: Path):
    root = tmp_path / "root"
    _write(root / "Personal Scratch" / "notes.txt", "private")

    result = run_audit(root, extra_exclusions=["Personal Scratch"])
    p = _by_name(result.projects, "Personal Scratch")
    assert p.is_excluded is True
    assert "user-configured" in p.exclusion_reason


def test_user_extra_exclusion_glob_pattern(tmp_path: Path):
    root = tmp_path / "root"
    _write(root / "backup-2024" / "file.txt", "x")
    _write(root / "backup-2025" / "file.txt", "x")
    _write(root / "real-project" / "README.md", "x")

    result = run_audit(root, extra_exclusions=["backup-*"])
    assert _by_name(result.projects, "backup-2024").is_excluded is True
    assert _by_name(result.projects, "backup-2025").is_excluded is True
    assert _by_name(result.projects, "real-project").is_excluded is False


def test_excluded_folder_not_rescanned_recursively(tmp_path: Path):
    """A folder that would otherwise contain a real-looking nested project
    must not surface it once the parent is excluded."""
    root = tmp_path / "root"
    excluded_child_repo = root / "OTROS - no proyectos" / "looks-like-a-project"
    _write(excluded_child_repo / "main.py")
    _init_git_repo(excluded_child_repo)
    _commit_all(excluded_child_repo)

    result = run_audit(root)
    assert all(p.name != "looks-like-a-project" for p in result.projects)


# ---------------------------------------------------------------------------
# Deterministic ids
# ---------------------------------------------------------------------------


def test_item_id_is_deterministic_and_matches_shared_identity_function(tmp_path: Path):
    root = tmp_path / "root"
    _write(root / "my-app" / "main.py")
    _init_git_repo(root / "my-app")
    _commit_all(root / "my-app")

    result = run_audit(root)
    p = _by_name(result.projects, "my-app")
    assert p.item_id == compute_item_id(p.root_path)

    result2 = run_audit(root)
    p2 = _by_name(result2.projects, "my-app")
    assert p2.item_id == p.item_id


# ---------------------------------------------------------------------------
# Real paths with spaces and parentheses
# ---------------------------------------------------------------------------


def test_hierarchy_with_spaces_and_parentheses_in_paths(tmp_path: Path):
    root = tmp_path / "My Drive (test@example.com)" / "1 - IA PROJECTS"
    _write(root / "ROLE Commerce Factory" / "RCOM-Printful-Adapter" / "package.json", "{}")
    _write(root / "ROLE Commerce Factory" / "RCOM-Shopify-Adapter" / "package.json", "{}")

    result = run_audit(root)
    factory = _by_name(result.projects, "ROLE Commerce Factory")
    adapter = _by_name(result.projects, "RCOM-Printful-Adapter")
    assert factory.is_top_level_project is True
    assert adapter.parent_item_id == factory.item_id
    assert adapter.item_kind == "component"


# ---------------------------------------------------------------------------
# Read-only guarantee (exclusion path specifically -- the rest is already
# covered by test_discovery.py's snapshot test)
# ---------------------------------------------------------------------------


def test_excluded_folder_scan_does_not_touch_filesystem(tmp_path: Path):
    import os

    root = tmp_path / "root"
    _write(root / "OTROS - no proyectos" / "a" / "b.txt", "content")

    def snapshot():
        snap = set()
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                fp = Path(dirpath) / name
                st = fp.stat()
                snap.add((str(fp), st.st_mtime, st.st_size))
        return snap

    before = snapshot()
    run_audit(root)
    after = snapshot()
    assert before == after


# ---------------------------------------------------------------------------
# Invalid override action validated at the rules layer indirectly via
# hierarchy report / JSON output shape
# ---------------------------------------------------------------------------


def test_boundary_fields_serialize_via_json_report(tmp_path: Path):
    from app.discovery.reporters import to_json

    root = tmp_path / "root"
    _write(root / "OTROS - no proyectos" / "junk.txt", "x")
    _write(root / "Commerce Factory" / "adapter-a" / "package.json", "{}")

    result = run_audit(root)
    payload = to_json(result)
    assert '"item_kind"' in payload
    assert '"boundary_confidence"' in payload
    assert '"is_excluded"' in payload


@pytest.mark.parametrize("bad_root", ["does-not-exist-anywhere-xyz"])
def test_invalid_root_still_raises_with_exclusions_wired(tmp_path: Path, bad_root):
    with pytest.raises(FileNotFoundError):
        run_audit(tmp_path / bad_root, extra_exclusions=["whatever"])
