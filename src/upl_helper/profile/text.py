"""Header text normalization and formula templating.

Both of these turn something that varies between template versions into
something stable enough to compare across them.
"""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_TRAILING_PUNCT = re.compile(r"[\s:;.,*]+$")

# An A1-style reference: optional $ before column, optional $ before row.
# The lookbehind keeps us off the tail of an identifier such as LOG10; the
# lookahead keeps us off function calls like SUM( and off the tail of a quoted
# sheet name such as 'FY2024'!. A reference after a sheet separator (Sheet2!D7)
# is deliberately still matched, because it moves with the cell like any other
# relative reference.
_A1_REF = re.compile(r"(?<![A-Za-z0-9_.$])(\$?)([A-Za-z]{1,3})(\$?)(\d+)(?![0-9('])")


def normalize_header(text: str | None) -> str | None:
    """Reduce header text to a stable identifier.

    ``"Medicare Provider Number (CCN)"`` becomes
    ``"medicare_provider_number_ccn"``.
    """
    if text is None:
        return None
    collapsed = " ".join(str(text).split())
    if not collapsed:
        return None
    lowered = _TRAILING_PUNCT.sub("", collapsed.casefold())
    slug = _NON_ALNUM.sub("_", lowered).strip("_")
    return slug or None


def _split_on_string_literals(formula: str) -> list[tuple[str, bool]]:
    """Split a formula into (text, is_string_literal) segments.

    Excel escapes a double quote inside a string literal by doubling it, which
    this handles by treating the escaped pair as ordinary literal content.
    """
    segments: list[tuple[str, bool]] = []
    buffer: list[str] = []
    in_string = False
    index = 0

    while index < len(formula):
        char = formula[index]
        if char == '"':
            if in_string and index + 1 < len(formula) and formula[index + 1] == '"':
                buffer.append('""')
                index += 2
                continue
            buffer.append(char)
            if in_string:
                segments.append(("".join(buffer), True))
                buffer = []
                in_string = False
            else:
                if buffer[:-1]:
                    segments.append(("".join(buffer[:-1]), False))
                buffer = [char]
                in_string = True
            index += 1
            continue
        buffer.append(char)
        index += 1

    if buffer:
        segments.append(("".join(buffer), in_string))
    return segments


def templatize_formula(formula: str, row: int) -> str:
    """Replace this cell's own row number with ``{row}`` in relative refs.

    ``=D7*E7`` in row 7 becomes ``=D{row}*E{row}``. Absolute references such
    as ``$E$7`` are left alone, since they do not move with the cell, and so
    are references to other rows. String literals are never touched.
    """

    def replace(match: re.Match[str]) -> str:
        col_abs, col, row_abs, row_text = match.groups()
        if row_abs:
            return match.group(0)
        if int(row_text) != row:
            return match.group(0)
        return f"{col_abs}{col}{row_abs}{{row}}"

    rendered: list[str] = []
    for text, is_literal in _split_on_string_literals(formula):
        rendered.append(text if is_literal else _A1_REF.sub(replace, text))
    return "".join(rendered)
