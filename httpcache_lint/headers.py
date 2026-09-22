"""Validation for the Age and Vary header fields.

Both are far simpler grammars than Cache-Control's directive list, so
they get their own small checks instead of being forced through the
directive parser. Age is RFC 9111 section 5.1; Vary is RFC 9110
section 12.5.5.
"""

import re
from typing import List

from .parser import Diagnostic
from .positions import line_starts, line_text_at, offset_to_position, value_end

# token = 1*tchar (RFC 9110 section 5.6.2), used for Vary's field-names.
_TOKEN_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_DELTA_SECONDS_RE = re.compile(r"[0-9]+")


def check_age(text: str, base_offset: int) -> List[Diagnostic]:
    """Validate an Age header value: RFC 9111 5.1 defines it as
    delta-seconds, a non-negative integer number of seconds and nothing
    else (no sign, no decimal point, no units).
    """
    starts = line_starts(text)
    end = value_end(text, base_offset)
    value = text[base_offset:end]
    trimmed = value.strip(" \t")

    def diag(severity: str, offset: int, message: str) -> Diagnostic:
        pos = offset_to_position(offset, starts)
        return Diagnostic(severity, message, pos, line_text_at(text, starts, pos.line))

    if trimmed == "":
        return [diag("error", base_offset, "Age header has an empty value, expected a non-negative integer")]

    if not _DELTA_SECONDS_RE.fullmatch(trimmed):
        return [
            diag(
                "error",
                base_offset,
                f"Age header value {trimmed!r} is not a non-negative integer (delta-seconds)",
            )
        ]

    return []


def check_vary(text: str, base_offset: int) -> List[Diagnostic]:
    """Validate a Vary header value: RFC 9110 12.5.5 defines it as either
    a single '*' or a comma-separated list of field-names.
    """
    starts = line_starts(text)
    end = value_end(text, base_offset)
    diagnostics: List[Diagnostic] = []

    def add(severity: str, offset: int, message: str) -> None:
        pos = offset_to_position(offset, starts)
        diagnostics.append(Diagnostic(severity, message, pos, line_text_at(text, starts, pos.line)))

    cursor = base_offset
    expect_member = True
    members = []  # list of (name, offset)
    while cursor < end:
        ch = text[cursor]
        if ch in " \t":
            cursor += 1
            continue
        if ch == ",":
            if expect_member:
                add("error", cursor, "empty member in Vary list (two commas in a row)")
            cursor += 1
            expect_member = True
            continue

        name_start = cursor
        while cursor < end and text[cursor] not in ", \t":
            cursor += 1
        name = text[name_start:cursor]
        expect_member = False

        if not _TOKEN_RE.fullmatch(name):
            add("error", name_start, f"'{name}' is not a valid field-name")
            continue

        members.append((name, name_start))

    if not members and text[base_offset:end].strip(" \t") == "":
        add("warning", base_offset, "Vary header has an empty value")

    seen = set()
    for name, offset in members:
        key = name.lower()
        if key in seen:
            add("warning", offset, f"field name '{name}' repeated in Vary list")
        seen.add(key)

    if len(members) > 1 and any(name == "*" for name, _ in members):
        star_offset = next(offset for name, offset in members if name == "*")
        add(
            "error",
            star_offset,
            "'*' must appear alone in a Vary list; it cannot be combined with other field names",
        )

    return diagnostics
