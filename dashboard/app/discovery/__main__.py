"""CLI for the Discovery Engine.

Usage (run from the `dashboard/` directory, or with `dashboard` on
PYTHONPATH — same convention as `uvicorn app.main:app`):

    python -m app.discovery audit --root "<path>" --output "<path>"
    python -m app.discovery audit --root "<path>" --exclude "Old Stuff" --exclude "*.bak"

Strictly read-only against `--root`: the only filesystem writes this
command ever performs are the report files under `--output`, which must
not be located inside `--root`. `--exclude` folders are reported (with
their exclusion reason) but never walked recursively -- see
`app.discovery.boundary.exclusions`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.discovery.reporters import to_console_table, write_reports
from app.discovery.service import run_audit


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.discovery",
        description="ROLE OS Discovery Engine — read-only project folder audit.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Scan a root folder and report discovered projects.")
    audit.add_argument("--root", required=True, help="Folder to scan (read-only).")
    audit.add_argument(
        "--output",
        required=False,
        help="Directory to write JSON/Markdown reports into. Must not be inside --root.",
    )
    audit.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="How many folder levels deep to scan (default: 2).",
    )
    audit.add_argument(
        "--basename",
        default="discovery_audit",
        help="Base filename for report output (default: discovery_audit).",
    )
    audit.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the console table (still writes reports if --output is set).",
    )
    audit.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="NAME_OR_GLOB",
        help=(
            "Extra folder name or glob pattern to exclude, on top of the default "
            "exclusion list (app/discovery/boundary/exclusions_config.json). "
            "Repeatable, e.g. --exclude 'Old Stuff' --exclude '*.bak'."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "audit":
        parser.print_help()
        return 1

    root = Path(args.root).resolve()
    output_dir = Path(args.output).resolve() if args.output else None

    if output_dir is not None:
        try:
            output_dir.relative_to(root)
        except ValueError:
            pass
        else:
            print(
                f"error: --output ({output_dir}) must not be inside --root ({root}); "
                "the audit is read-only and will not write into the scanned tree.",
                file=sys.stderr,
            )
            return 2

    try:
        result = run_audit(root, max_depth=args.max_depth, extra_exclusions=args.exclude)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(to_console_table(result))

    if output_dir is not None:
        written = write_reports(result, output_dir, basename=args.basename)
        print(f"\nReports written:\n  {written['json']}\n  {written['markdown']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
