"""Command line for metalm-gendocs: the pre-commit hook entry and the staleness check.

Exit codes follow pre-commit: 0 nothing changed, 1 files changed (or stale with
--check), 2 the code could not be read.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from metalm_gendocs.generate import GenDocsError, stale, uncovered, write


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="metalm-gendocs",
        description="Regenerate docs/generated/ from docstrings and cuj test markers. Example: metalm-gendocs --check",
    )
    parser.add_argument("--root", default=".", help="repo root (default: current directory)")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when a generated file is stale")
    parser.add_argument("files", nargs="*", help=argparse.SUPPRESS)  # pre-commit may pass filenames; ignored
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        files = stale(root) if args.check else write(root)
    except GenDocsError as exc:
        print(f"metalm-gendocs: {exc}", file=sys.stderr)
        return 2
    skipped = uncovered(root)
    if skipped:
        print(f"metalm-gendocs: not covered: {', '.join(sorted(skipped))}; see docs/generated/index.md", file=sys.stderr)
    verb = "stale" if args.check else "regenerated"
    for rel in files:
        print(f"{verb}: {rel}")
    if files and not args.check:
        print("metalm-gendocs: docs/generated changed; add them and commit again", file=sys.stderr)
    return 1 if files else 0


if __name__ == "__main__":
    sys.exit(main())
