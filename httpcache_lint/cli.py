"""Command-line interface for httpcache-lint.

    httpcache-lint check response.txt
    httpcache-lint check --value "max-age=3600, no-cache, immutable"
    cat response.txt | httpcache-lint check -
"""

import argparse
import sys
from typing import List

from .headers import check_age, check_vary
from .parser import parse_cache_control
from .rules import check_directives


def _find_header_value_offsets(text: str, header_name: str) -> List[int]:
    """Return the offsets where each occurrence of `header_name`'s value starts."""
    offsets = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip(" \t")
        colon = stripped.find(":")
        if colon != -1 and stripped[:colon].strip().lower() == header_name:
            leading = len(line) - len(stripped)
            value_start = leading + colon + 1
            while value_start < len(line) and line[value_start] in " \t":
                value_start += 1
            offsets.append(pos + value_start)
        pos += len(line)
    return offsets


def _run_check(text: str, source_name: str) -> int:
    cache_control_offsets = _find_header_value_offsets(text, "cache-control")
    age_offsets = _find_header_value_offsets(text, "age")
    vary_offsets = _find_header_value_offsets(text, "vary")

    if not cache_control_offsets and not age_offsets and not vary_offsets:
        print(f"{source_name}: no Cache-Control, Age, or Vary header found", file=sys.stderr)
        return 1

    diagnostics = []
    for offset in cache_control_offsets:
        result = parse_cache_control(text, offset)
        diagnostics += list(result.diagnostics) + check_directives(result)
    for offset in age_offsets:
        diagnostics += check_age(text, offset)
    for offset in vary_offsets:
        diagnostics += check_vary(text, offset)

    had_error = False
    for diagnostic in sorted(diagnostics, key=lambda d: (d.pos.line, d.pos.column)):
        print(diagnostic.render(source_name))
        if diagnostic.severity == "error":
            had_error = True

    return 1 if had_error else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="httpcache-lint")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate Cache-Control, Age, and Vary headers")
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
