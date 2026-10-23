"""Command line for metalm-gendocs: the pre-commit hook entry and the staleness check.

Exit codes: 0 nothing changed, 1 files changed (or stale with --dry-run) or the
code could not be read; pre-commit fails the hook on any non-zero exit.
`--check` is a hidden alias of `--dry-run` until every repo's staleness test
says `--dry-run`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from metalm_gendocs.generate import GenDocsError, stale, uncovered, write


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="metalm-gendocs",
        description="Regenerate docs/generated/ from docstrings and cuj test markers.",
        epilog="example: metalm-gendocs --dry-run",
    )
    parser.add_argument("--root", default=".", help="repo root (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="write nothing; exit 1 when a generated file is stale")
    parser.add_argument("--check", dest="dry_run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("files", nargs="*", help=argparse.SUPPRESS)  # pre-commit may pass filenames; ignored
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        files = stale(root) if args.dry_run else write(root)
    except GenDocsError as exc:
        print(f"error: {exc}. Fix the file named, then run: metalm-gendocs", file=sys.stderr)
        return 1
    skipped = uncovered(root)
    if skipped:
        print(f"metalm-gendocs: not covered: {', '.join(sorted(skipped))}; see docs/generated/index.md", file=sys.stderr)
    verb = "stale" if args.dry_run else "regenerated"
    for rel in files:
        print(f"{verb}: {rel}")
    if files and not args.dry_run:
        print("metalm-gendocs: docs/generated changed; add them and commit again", file=sys.stderr)
    return 1 if files else 0


if __name__ == "__main__":
    sys.exit(main())
