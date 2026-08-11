"""Context Package (hotfix §11): Resume Work must embed real local file
content, not just paths, so a browser-based Claude conversation (no
filesystem access) can act without asking to see the files. These tests
exercise `app.project_memory.context_package` directly against real
files on disk -- no mocking, same convention as the rest of this suite.
"""

from __future__ import annotations

from pathlib import Path

from app.project_memory.context_package import _is_safe_to_embed, build_context_package


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_embeds_real_heading_and_excerpt_from_readme(tmp_path):
    _write(
        tmp_path / "README.md",
        "# Demo Project\n\n## Overview\n\nDemo Project ships widgets to retailers.\n",
    )
    package = build_context_package(str(tmp_path), "Fix the widget importer", None)
    assert package["context_sufficient"] is True
    assert package["embedded_resource_count"] == 1
    resource = package["resources"][0]
    assert resource["resource_name"] == "README.md"
    assert resource["relative_path"] == "README.md"
    assert resource["selected_heading"] == "Overview"
    assert "Demo Project ships widgets to retailers." in resource["excerpt"]
    assert resource["sensitive_content_redacted"] is False


def test_requested_action_aware_resource_selection(tmp_path):
    _write(tmp_path / "README.md", "# P\n\nA project.\n")
    _write(tmp_path / "ROADMAP.md", "# Roadmap\n\n## Current Phase\n\nPhase 2: rollout.\n")
    _write(tmp_path / "SYSTEM.md", "# System\n\nThe system has three services.\n")
    _write(tmp_path / "ARCHITECTURE.md", "# Architecture\n\nLayered architecture.\n")

    status_package = build_context_package(str(tmp_path), "Ship the next release", None)
    status_names = [r["resource_name"] for r in status_package["resources"]]
    assert status_names[0] == "README.md"
    assert "ROADMAP.md" in status_names
    assert "SYSTEM.md" not in status_names

    architecture_package = build_context_package(
        str(tmp_path), "Document the system architecture", None
    )
    architecture_names = [r["resource_name"] for r in architecture_package["resources"]]
    assert architecture_names[0] == "SYSTEM.md"

    implementation_package = build_context_package(
        str(tmp_path), "Implement the new billing adapter", None
    )
    implementation_names = [r["resource_name"] for r in implementation_package["resources"]]
    assert "ARCHITECTURE.md" in implementation_names
    assert implementation_names[0] != "README.md"


def test_changelog_prefers_unreleased_section(tmp_path):
    _write(
        tmp_path / "CHANGELOG.md",
        "# Changelog\n\n## 1.0.0\n\nOld stuff.\n\n## Unreleased\n\nNew fix landed.\n",
    )
    package = build_context_package(str(tmp_path), "Ship the release", None)
    changelog = next(r for r in package["resources"] if r["resource_name"] == "CHANGELOG.md")
    assert changelog["selected_heading"] == "Unreleased"
    assert "New fix landed." in changelog["excerpt"]


def test_bounded_excerpt_per_resource(tmp_path):
    long_body = "word " * 2000
    _write(tmp_path / "README.md", f"# P\n\n## Overview\n\n{long_body}\n")
    package = build_context_package(str(tmp_path), "Ship the release", None)
    resource = package["resources"][0]
    assert len(resource["excerpt"]) <= 2000
    assert resource["omitted_character_count"] > 0


def test_truncation_is_deterministic(tmp_path):
    long_body = "Sentence one. " * 500
    _write(tmp_path / "README.md", f"# P\n\n## Overview\n\n{long_body}\n")
    first = build_context_package(str(tmp_path), "Ship the release", None)
    second = build_context_package(str(tmp_path), "Ship the release", None)
    assert first["resources"][0]["excerpt"] == second["resources"][0]["excerpt"]


def test_total_context_budget_is_respected(tmp_path):
    body = "word " * 2000
    for name in ("README.md", "ROADMAP.md", "TODO.md", "NEXT_ACTION.md", "CHANGELOG.md"):
        _write(tmp_path / name, f"# {name}\n\n{body}\n")
    package = build_context_package(
        str(tmp_path),
        "Ship the release",
        None,
        max_total_chars=3000,
        max_chars_per_resource=2000,
    )
    total = sum(len(r["excerpt"]) for r in package["resources"])
    assert total <= 3000
    assert package["embedded_character_count"] == total


def test_secret_is_redacted(tmp_path):
    _write(
        tmp_path / "README.md",
        "# P\n\n## Overview\n\nSetup:\nAPI_KEY=sk-abcdef1234567890abcd\nDone.\n",
    )
    package = build_context_package(str(tmp_path), "Ship the release", None)
    resource = package["resources"][0]
    assert "sk-abcdef1234567890abcd" not in resource["excerpt"]
    assert "[REDACTED]" in resource["excerpt"]
    assert resource["sensitive_content_redacted"] is True


def test_env_file_is_never_embedded(tmp_path):
    env_path = tmp_path / ".env"
    _write(env_path, "SECRET=supersecretvalue12345\n")
    _write(tmp_path / "README.md", "# P\n\nA project.\n")
    # `.env` explicitly named as the requested action's own source file --
    # even then, it must never be treated as a candidate resource.
    package = build_context_package(str(tmp_path), "Ship the release", str(env_path))
    names = [r["resource_name"] for r in package["resources"]]
    assert ".env" not in names
    assert not any("supersecretvalue12345" in r["excerpt"] for r in package["resources"])


def test_paths_outside_adopted_root_are_rejected(tmp_path):
    # `build_context_package` only ever searches for a candidate *filename*
    # within the adopted root (never a caller-supplied full path), so this
    # exercises the underlying containment guard directly -- the same guard
    # that would catch a symlink escape inside an adopted root.
    outside = tmp_path.parent / "outside-secret.md"
    _write(outside, "# Outside\n\nShould never be embedded.\n")
    adopted_root = tmp_path / "project"
    _write(adopted_root / "README.md", "# P\n\nA project.\n")

    safe, reason = _is_safe_to_embed(outside, adopted_root)
    assert safe is False
    assert "outside adopted project root" in reason

    # And the end-to-end path: a requested-action source outside the root
    # is reduced to a bare filename and never resolves to the outside file.
    package = build_context_package(str(adopted_root), "Ship the release", str(outside))
    names = [r["resource_name"] for r in package["resources"]]
    assert "outside-secret.md" not in names


def test_binary_file_is_excluded(tmp_path):
    (tmp_path / "README.md").write_bytes(b"\x00\x01binary data, not really markdown")
    package = build_context_package(str(tmp_path), "Ship the release", None)
    assert package["embedded_resource_count"] == 0
    assert package["context_sufficient"] is False


def test_missing_root_reports_context_insufficient(tmp_path):
    missing_root = tmp_path / "does-not-exist"
    package = build_context_package(str(missing_root), "Ship the release", None)
    assert package["context_sufficient"] is False
    assert package["resources"] == []
    assert package["missing_context"]


def test_no_root_path_is_out_of_scope_for_the_guard():
    # No filesystem-backed project root at all (e.g. a Project row with
    # no adopted folder) -- nothing local to embed, but that's not a
    # failure state the sufficiency guard should block on.
    package = build_context_package(None, "Ship the release", None)
    assert package["context_sufficient"] is True
    assert package["embedded_resource_count"] == 0


def test_empty_project_reports_context_insufficient(tmp_path):
    (tmp_path / "notes.txt").write_text("not a supported filename", encoding="utf-8")
    package = build_context_package(str(tmp_path), "Ship the release", None)
    assert package["context_sufficient"] is False
    assert "no supported project documentation" in package["missing_context"][-1]
