"""Command-line interface for httpcache-lint.

    httpcache-lint check response.txt
    httpcache-lint check --value "max-age=3600, no-cache, immutable"
    cat response.txt | httpcache-lint check -
"""

import argparse
import sys
from typing import List

from .parser import parse_cache_control
from .rules import check_directives

HEADER_NAME = "cache-control"


def _find_header_values(text: str) -> List[int]:
    """Return the offsets where each Cache-Control header's value starts."""
    offsets = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip(" \t")
        colon = stripped.find(":")
        if colon != -1 and stripped[:colon].strip().lower() == HEADER_NAME:
            leading = len(line) - len(stripped)
            value_start = leading + colon + 1
            while value_start < len(line) and line[value_start] in " \t":
                value_start += 1
            offsets.append(pos + value_start)
        pos += len(line)
    return offsets


def _run_check(text: str, source_name: str) -> int:
    offsets = _find_header_values(text)
    if not offsets:
        print(f"{source_name}: no Cache-Control header found", file=sys.stderr)
        return 1

    had_error = False
    for offset in offsets:
        result = parse_cache_control(text, offset)
        diagnostics = list(result.diagnostics) + check_directives(result)
        for diagnostic in sorted(diagnostics, key=lambda d: (d.pos.line, d.pos.column)):
            print(diagnostic.render(source_name))
            if diagnostic.severity == "error":
                had_error = True

    return 1 if had_error else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="httpcache-lint")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate Cache-Control headers")
    check.add_argument("path", nargs="?", help="file to read, or '-' for stdin")
    check.add_argument("--value", help="check a single Cache-Control value directly")

    args = parser.parse_args(argv)

    if args.command == "check":
        if args.value is not None:
            return _run_check(f"Cache-Control: {args.value}\n", "<value>")
        if not args.path or args.path == "-":
            return _run_check(sys.stdin.read(), "<stdin>")
        with open(args.path, "r", encoding="utf-8") as f:
            return _run_check(f.read(), args.path)

    return 1


if __name__ == "__main__":
    sys.exit(main())
