"""Report rendering: JSON, Markdown, console table (§7 of the proposal).

Pure functions over a ScanResult — no filesystem access except the
optional `write_reports` helper, which only ever writes to the caller-
supplied output directory, never to the scanned tree.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from app.discovery.models import ScanResult

_KIND_ORDER = [
    "Software Project",
    "Website",
    "Mixed Project",
    "Documentation Project",
    "Brand / Asset Project",
    "Unknown",
    "Non-project",
]


def to_json(result: ScanResult) -> str:
    return json.dumps(dataclasses.asdict(result), indent=2, default=str)


def to_markdown(result: ScanResult) -> str:
    lines: list[str] = []
    lines.append(f"# Discovery Audit — `{result.root}`")
    lines.append("")
    lines.append(f"- Scanned at: {result.scanned_at}")
    lines.append(f"- Duration: {result.duration_seconds}s")
    lines.append(f"- Max depth: {result.max_depth}")
    lines.append(f"- Folders discovered: {len(result.projects)}")
    lines.append(f"- Paths skipped (permission/reparse): {len(result.skipped_paths)}")
    lines.append(f"- Errors: {len(result.errors)}")
    lines.append("")

    by_kind: dict[str, list] = {k: [] for k in _KIND_ORDER}
    for project in result.projects:
        by_kind.setdefault(project.classification, [])
        by_kind[project.classification].append(project)

    git_repo_count = sum(1 for p in result.projects if p.git.is_repo)
    website_count = len(by_kind.get("Website", []))
    python_count = sum(1 for p in result.projects if "Python" in p.languages)
    node_count = sum(
        1 for p in result.projects if "JavaScript" in p.languages or "TypeScript" in p.languages
    )
    unknown_count = len(by_kind.get("Unknown", []))
    safe_to_move_count = sum(1 for p in result.projects if p.move_risk == "low")
    needs_review_count = sum(1 for p in result.projects if p.recommendation == "Requires manual review")
    high_risk_count = sum(1 for p in result.projects if p.move_risk == "high")
    projects_detected = len(result.projects) - len(by_kind.get("Non-project", []))

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Folders scanned: {len(result.projects)}")
    lines.append(f"- Projects detected: {projects_detected}")
    lines.append(f"- Git repositories: {git_repo_count}")
    lines.append(f"- Static websites: {website_count}")
    lines.append(f"- Python projects: {python_count}")
    lines.append(f"- Node projects: {node_count}")
    lines.append(f"- Unknown folders: {unknown_count}")
    lines.append(f"- Safe to move: {safe_to_move_count}")
    lines.append(f"- Needs review: {needs_review_count}")
    lines.append(f"- High risk: {high_risk_count}")
    lines.append("")

    lines.append("## Summary by classification")
    lines.append("")
    lines.append("| Classification | Count |")
    lines.append("|---|---|")
    for kind in _KIND_ORDER:
        if by_kind.get(kind):
            lines.append(f"| {kind} | {len(by_kind[kind])} |")
    lines.append("")

    lines.append("## Projects")
    lines.append("")
    lines.append(
        "| Project | Type | Git | Health | Move Risk | Recommendation |"
    )
    lines.append("|---|---|---|---|---|---|")
    for project in sorted(result.projects, key=lambda p: (p.depth, p.name.lower())):
        git_summary = (
            f"{project.git.branch or '?'}@{(project.git.last_commit_hash or '')[:7]}"
            if project.git.is_repo
            else "-"
        )
        health = project.health_score if project.health_score is not None else "-"
        lines.append(
            f"| {project.name} | {project.classification} | {git_summary} | "
            f"{health} | {project.move_risk} | {project.recommendation} |"
        )
    lines.append("")

    lines.append("## Recommendations")
    lines.append("")
    for project in sorted(result.projects, key=lambda p: (p.depth, p.name.lower())):
        if project.recommendation_reasons:
            reason = "; ".join(project.recommendation_reasons)
            lines.append(f"- **{project.name}** -> {project.recommendation}: {reason}")
    lines.append("")

    high_risk = [p for p in result.projects if p.move_risk == "high"]
    if high_risk:
        lines.append("## Move-risk findings (high)")
        lines.append("")
        for project in high_risk:
            lines.append(f"### {project.name} (`{project.root_path}`)")
            for reason in project.move_risk_reasons:
                lines.append(f"- {reason}")
            lines.append("")

    if result.skipped_paths:
        lines.append("## Skipped paths")
        lines.append("")
        for path in result.skipped_paths:
            lines.append(f"- {path}")
        lines.append("")

    if result.errors:
        lines.append("## Errors")
        lines.append("")
        for err in result.errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def to_console_table(result: ScanResult) -> str:
    headers = ["Name", "Kind", "Conf", "Risk", "Maturity", "Commercial", "Depth"]
    widths = [28, 20, 5, 6, 9, 12, 5]
    rows = []
    for project in sorted(result.projects, key=lambda p: (p.depth, p.name.lower())):
        rows.append(
            [
                _truncate(project.name, widths[0]),
                _truncate(project.classification, widths[1]),
                f"{project.confidence_score:.2f}",
                project.move_risk,
                project.maturity,
                project.commercial_readiness,
                str(project.depth),
            ]
        )

    def fmt_row(cells: list[str]) -> str:
        return "  ".join(cell.ljust(w) for cell, w in zip(cells, widths))

    lines = [
        f"Discovery Audit — {result.root}",
        f"({len(result.projects)} folders, {result.duration_seconds}s, "
        f"{len(result.skipped_paths)} skipped, {len(result.errors)} errors)",
        "",
        fmt_row(headers),
        fmt_row(["-" * w for w in widths]),
    ]
    lines.extend(fmt_row(row) for row in rows)
    return "\n".join(lines)


def write_reports(result: ScanResult, output_dir: Path, basename: str = "discovery_audit") -> dict[str, Path]:
    """Write JSON + Markdown reports to `output_dir`. Read-only w.r.t. the
    scanned tree — the caller must ensure output_dir is outside `result.root`
    (the CLI enforces this)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{basename}.json"
    md_path = output_dir / f"{basename}.md"

    json_path.write_text(to_json(result), encoding="utf-8")
    md_path.write_text(to_markdown(result), encoding="utf-8")

    return {"json": json_path, "markdown": md_path}
