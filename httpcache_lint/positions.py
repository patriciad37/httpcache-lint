"""Offset-to-line/column mapping shared by every header check.

Pulled out of parser.py once the Age and Vary checks needed the same
line/column math the Cache-Control parser already had, so there's one
place that defines what "position" means across the whole tool.
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Position:
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.line}:{self.column}"


def line_starts(text: str) -> List[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def offset_to_position(offset: int, starts: List[int]) -> Position:
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    line = lo + 1
    column = offset - starts[lo] + 1
    return Position(line, column)


def line_text_at(text: str, starts: List[int], line_number: int) -> str:
    start = starts[line_number - 1]
    end = len(text)
    for idx in range(start, len(text)):
        if text[idx] in "\r\n":
            end = idx
            break
    return text[start:end]


def value_end(text: str, start: int) -> int:
    """Offset of the end of a single-line header value starting at `start`."""
    for idx in range(start, len(text)):
        if text[idx] in "\r\n":
            return idx
    return len(text)
