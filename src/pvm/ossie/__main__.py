"""Command-line interface for the PVM Ossie vendor-extension validator.

Usage::

    python -m pvm.ossie validate FILE [FILE ...]

Exits 1 if any file fails validation (has error-severity issues) or cannot
be read; exits 0 otherwise.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pvm.ossie.document import validate_document
from pvm.ossie.report import Issue


def _format_issue(file_arg: str, issue: Issue) -> str:
    return f"{file_arg}: {issue.severity} {issue.code} at {issue.path}: {issue.message}"


def _validate_file(file_arg: str) -> bool:
    """Validate one file argument, printing its issues. Return True if ok."""
    path = Path(file_arg)
    if not path.is_file():
        print(f"{file_arg}: error: no such file", file=sys.stderr)
        return False

    try:
        report = validate_document(path)
    except OSError as exc:
        print(f"{file_arg}: error: could not read file: {exc}", file=sys.stderr)
        return False

    for issue in report.issues:
        print(_format_issue(file_arg, issue))

    if report.ok and not report.issues:
        print(f"{file_arg}: ok")

    return report.ok


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pvm.ossie")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate Ossie document files")
    validate_parser.add_argument("files", nargs="+", metavar="FILE")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Return the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    all_ok = True
    for file_arg in args.files:
        if not _validate_file(file_arg):
            all_ok = False

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
