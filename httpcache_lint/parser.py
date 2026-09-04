"""Parser for the Cache-Control grammar (RFC 9111 section 5.2).

Every position is tracked as an offset into the *original* source text
handed to parse_cache_control, not into some extracted substring. That
is what lets a caller who read a whole raw HTTP response report errors
at the line and column they actually appear on, instead of "somewhere
in the header".
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Position:
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


@dataclass(frozen=True)
class Directive:
    name: str
    value: Optional[str]
    quoted: bool
    pos: Position
    line_text: str


@dataclass(frozen=True)
class Diagnostic:
    severity: str  # "error" or "warning"
    message: str
    pos: Position
    line_text: str

    def render(self, source_name: str = "<input>") -> str:
        pointer = " " * (self.pos.column - 1) + "^"
        return (
            f"{source_name}:{self.pos}: {self.severity}: {self.message}\n"
            f"    {self.line_text}\n"
            f"    {pointer}"
        )


@dataclass(frozen=True)
class ParseResult:
    directives: List[Directive]
    diagnostics: List[Diagnostic]

    @property
    def ok(self) -> bool:
        return not any(d.severity == "error" for d in self.diagnostics)


def _line_starts(text: str) -> List[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _offset_to_position(offset: int, line_starts: List[int]) -> Position:
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    line = lo + 1
    column = offset - line_starts[lo] + 1
    return Position(line, column)


def _line_text(text: str, line_starts: List[int], line_number: int) -> str:
    start = line_starts[line_number - 1]
    end = len(text)
    for idx in range(start, len(text)):
        if text[idx] in "\r\n":
            end = idx
            break
    return text[start:end]


def parse_cache_control(text: str, base_offset: int = 0) -> ParseResult:
    """Parse a single Cache-Control header value found within `text`.

    `text` is the whole document the caller has (a raw response, a log
    line, whatever), and `base_offset` is where the header's value
    starts. Everything after `base_offset` up to the next line break
    (outside of a quoted string) is treated as the value.
    """
    line_starts = _line_starts(text)
    diagnostics: List[Diagnostic] = []
    directives: List[Directive] = []

    end = len(text)
    idx = base_offset
    in_quotes = False
    while idx < end and not (text[idx] in "\r\n" and not in_quotes):
        if text[idx] == '"':
            in_quotes = not in_quotes
        idx += 1
    value_end = idx

    def pos_at(offset: int) -> Position:
        return _offset_to_position(offset, line_starts)

    def text_of_line_at(offset: int) -> str:
        return _line_text(text, line_starts, pos_at(offset).line)

    def add(severity: str, offset: int, message: str) -> None:
        diagnostics.append(Diagnostic(severity, message, pos_at(offset), text_of_line_at(offset)))

    cursor = base_offset
    expect_directive = True
    while cursor < value_end:
        ch = text[cursor]
        if ch in " \t":
            cursor += 1
            continue
        if ch == ",":
            if expect_directive:
                add("error", cursor, "empty directive (two commas in a row)")
            cursor += 1
            expect_directive = True
            continue

        name_start = cursor
        while cursor < value_end and (text[cursor].isalnum() or text[cursor] in "-_"):
            cursor += 1
        if cursor == name_start:
            add("error", cursor, f"unexpected character {text[cursor]!r}, expected a directive name")
            cursor += 1
            continue

        name = text[name_start:cursor]
        name_pos = pos_at(name_start)
        line_text = text_of_line_at(name_start)
        expect_directive = False

        lookahead = cursor
        while lookahead < value_end and text[lookahead] in " \t":
            lookahead += 1

        value: Optional[str] = None
        quoted = False
        if lookahead < value_end and text[lookahead] == "=":
            eq_offset = lookahead
            lookahead += 1
            while lookahead < value_end and text[lookahead] in " \t":
                lookahead += 1
            if lookahead < value_end and text[lookahead] == '"':
                quoted = True
                q_start = lookahead
                lookahead += 1
                str_start = lookahead
                while lookahead < value_end and text[lookahead] != '"':
                    lookahead += 1
                if lookahead >= value_end:
                    add("error", q_start, f"unterminated quoted value for '{name}'")
                    value = text[str_start:lookahead]
                    cursor = lookahead
                else:
                    value = text[str_start:lookahead]
                    cursor = lookahead + 1
            else:
                v_start = lookahead
                while lookahead < value_end and text[lookahead] not in ", \t":
                    lookahead += 1
                value = text[v_start:lookahead]
                cursor = lookahead
                if value == "":
                    add("error", eq_offset + 1, f"directive '{name}' has '=' but no value")

        directives.append(Directive(name, value, quoted, name_pos, line_text))

        while cursor < value_end and text[cursor] in " \t":
            cursor += 1
        if cursor < value_end:
            if text[cursor] == ",":
                cursor += 1
                expect_directive = True
            else:
                add("error", cursor, f"expected ',' after directive '{name}', found {text[cursor]!r}")
                cursor += 1

    return ParseResult(directives=directives, diagnostics=diagnostics)
