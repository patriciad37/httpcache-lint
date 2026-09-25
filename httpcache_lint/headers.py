"""Validation for the Age, Vary, and Expires header fields.

These are far simpler grammars than Cache-Control's directive list, so
they get their own small checks instead of being forced through the
directive parser. Age is RFC 9111 section 5.1; Vary is RFC 9110
section 12.5.5; Expires is RFC 9111 section 5.3 (value grammar is
HTTP-date, RFC 9110 section 5.6.7).
"""

import datetime
import re
from typing import List

from .parser import Diagnostic
from .positions import line_starts, line_text_at, offset_to_position, value_end

# token = 1*tchar (RFC 9110 section 5.6.2), used for Vary's field-names.
_TOKEN_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
_DELTA_SECONDS_RE = re.compile(r"[0-9]+")

_MONTH_NAMES = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_MONTHS = {name: i for i, name in enumerate(_MONTH_NAMES.split("|"), start=1)}
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# IMF-fixdate, the only format RFC 9110 5.6.7 allows a sender to
# generate: "Sun, 06 Nov 1994 08:49:37 GMT".
_IMF_FIXDATE_RE = re.compile(
    r"(?P<wkday>Mon|Tue|Wed|Thu|Fri|Sat|Sun), "
    r"(?P<day>\d{2}) (?P<month>" + _MONTH_NAMES + r") (?P<year>\d{4}) "
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}) GMT"
)

# rfc850-date, obsolete but still required reading for recipients:
# "Sunday, 06-Nov-94 08:49:37 GMT".
_RFC850_DATE_RE = re.compile(
    r"(?P<wkday>Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
    r"(?P<day>\d{2})-(?P<month>" + _MONTH_NAMES + r")-(?P<year>\d{2}) "
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}) GMT"
)

# asctime-date, also obsolete: "Sun Nov  6 08:49:37 1994".
_ASCTIME_RE = re.compile(
    r"(?P<wkday>Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
    r"(?P<month>" + _MONTH_NAMES + r") "
    r"(?P<day>[ \d]\d) "
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}) "
    r"(?P<year>\d{4})"
)


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


def check_expires(text: str, base_offset: int) -> List[Diagnostic]:
    """Validate an Expires header value: RFC 9111 5.3 requires an
    HTTP-date, with the literal value 0 as a special case that means
    "already expired". A cache is required to treat any other
    unparseable value as already expired too, so a bad date here isn't
    a hard failure the way a bad Cache-Control directive is - but it's
    almost never what the sender intended, so it's worth flagging.
    """
    starts = line_starts(text)
    end = value_end(text, base_offset)
    value = text[base_offset:end]
    trimmed = value.strip(" \t")

    def diag(severity: str, message: str) -> Diagnostic:
        pos = offset_to_position(base_offset, starts)
        return Diagnostic(severity, message, pos, line_text_at(text, starts, pos.line))

    if trimmed == "":
        return [diag("error", "Expires header has an empty value, expected an HTTP-date")]

    if trimmed == "0":
        return []

    match = _IMF_FIXDATE_RE.fullmatch(trimmed)
    if match:
        return _check_http_date(match, diag)

    match = _RFC850_DATE_RE.fullmatch(trimmed)
    if match:
        return _check_http_date(match, diag, obsolete="RFC 850", two_digit_year=True)

    match = _ASCTIME_RE.fullmatch(trimmed)
    if match:
        return _check_http_date(match, diag, obsolete="asctime")

    return [
        diag(
            "error",
            f"Expires value {trimmed!r} is not a valid HTTP-date; caches must treat unparseable "
            "dates as already expired",
        )
    ]


def _check_http_date(match, diag, obsolete: str = "", two_digit_year: bool = False) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []
    if obsolete:
        diagnostics.append(
            diag(
                "warning",
                f"Expires uses the obsolete {obsolete} date format; RFC 9110 prefers IMF-fixdate, "
                "e.g. 'Sun, 06 Nov 1994 08:49:37 GMT'",
            )
        )

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second = int(match.group("second"))
    if hour > 23 or minute > 59 or second > 59:
        diagnostics.append(diag("error", f"Expires time '{hour:02d}:{minute:02d}:{second:02d}' is out of range"))
        return diagnostics

    day = int(match.group("day"))
    month = _MONTHS[match.group("month")]
    year = int(match.group("year"))
    if two_digit_year:
        # RFC 9110 5.6.7 leaves the two-digit-year rule to the recipient's
        # judgment; the common convention treats anything in the past 30
        # years as this century, everything else as last century.
        year = 2000 + year if year < 70 else 1900 + year

    try:
        actual_date = datetime.date(year, month, day)
    except ValueError as exc:
        diagnostics.append(diag("error", f"Expires date is invalid: {exc}"))
        return diagnostics

    expected_wkday = _WEEKDAYS[actual_date.weekday()]
    given_wkday = match.group("wkday")[:3]
    if given_wkday != expected_wkday:
        diagnostics.append(
            diag(
                "error",
                f"Expires weekday '{match.group('wkday')}' does not match the date; "
                f"{actual_date.isoformat()} is a {expected_wkday}",
            )
        )

    return diagnostics
