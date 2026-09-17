"""Finding the header row or rows in a worksheet.

CMS templates put title banners, notes and blank spacer rows above the real
header, so the header cannot be assumed to be row 1. This scores candidate
rows and reports all of them rather than only the winner, because a human
reading a descriptor needs to see what was rejected.
"""

from __future__ import annotations

from typing import Any

from upl_helper.profile.models import HeaderCandidate
from upl_helper.profile.text import normalize_header

MAX_SCAN_ROWS = 30
LOOKAHEAD_ROWS = 10
MIN_NONEMPTY_CELLS = 3
SPARSE_ROW_PENALTY = 0.3
WIDE_MERGE_PENALTY = 0.5
WIDE_MERGE_COLUMNS = 4
MAX_CANDIDATES = 10

# A header row is mostly distinct text with numbers underneath it.
WEIGHT_STRING = 0.40
WEIGHT_DISTINCT = 0.25
WEIGHT_NUMERIC_BELOW = 0.35

# An adjacent row joins the header only if it scores nearly as well as the
# best row. Deliberately strict: a single-row header is the common case.
MULTI_ROW_THRESHOLD = 0.85


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and not value.startswith("=")


def _wide_merge_rows(worksheet: Any) -> set[int]:
    """Rows touched by a merged range spanning more than a few columns.

    These are almost always title banners rather than headers.
    """
    rows: set[int] = set()
    for merged in worksheet.merged_cells.ranges:
        if merged.max_col - merged.min_col + 1 > WIDE_MERGE_COLUMNS:
            rows.update(range(merged.min_row, merged.max_row + 1))
    return rows


def score_row(
    grid: list[list[Any]], row_offset: int, banner_rows: set[int], first_row: int
) -> tuple[float, int]:
    """Score one row as a header candidate. Returns (score, nonempty count)."""
    row_values = grid[row_offset]
    nonempty = [v for v in row_values if v is not None and str(v).strip() != ""]
    if not nonempty:
        return 0.0, 0

    texts = [v for v in nonempty if _is_text(v)]
    string_frac = len(texts) / len(nonempty)

    normalized = {normalize_header(t) for t in texts}
    distinct_frac = (len(normalized) / len(texts)) if texts else 0.0

    numeric_below = 0
    nonempty_below = 0
    for below in grid[row_offset + 1 : row_offset + 1 + LOOKAHEAD_ROWS]:
        for value in below:
            if value is None or (isinstance(value, str) and value.strip() == ""):
                continue
            nonempty_below += 1
            if isinstance(value, bool):
                continue
            is_number = isinstance(value, (int, float))
            is_formula = isinstance(value, str) and value.startswith("=")
            if is_number or is_formula:
                numeric_below += 1
    numeric_frac = (numeric_below / nonempty_below) if nonempty_below else 0.0

    score = (
        WEIGHT_STRING * string_frac
        + WEIGHT_DISTINCT * distinct_frac
        + WEIGHT_NUMERIC_BELOW * numeric_frac
    )

    if len(nonempty) < MIN_NONEMPTY_CELLS:
        score *= SPARSE_ROW_PENALTY
    if (first_row + row_offset) in banner_rows:
        score *= WIDE_MERGE_PENALTY

    return score, len(nonempty)


def detect_header_rows(
    worksheet: Any, max_scan: int = MAX_SCAN_ROWS
) -> list[HeaderCandidate]:
    """Score the first ``max_scan`` rows and return candidates, best first."""
    first_row = worksheet.min_row or 1
    last_row = min(worksheet.max_row or 1, first_row + max_scan + LOOKAHEAD_ROWS - 1)
    if worksheet.max_row is None or worksheet.max_row < first_row:
        return []

    grid = [
        list(row)
        for row in worksheet.iter_rows(
            min_row=first_row, max_row=last_row, values_only=True
        )
    ]
    banner_rows = _wide_merge_rows(worksheet)

    candidates: list[HeaderCandidate] = []
    scan_limit = min(max_scan, len(grid))
    for offset in range(scan_limit):
        score, nonempty = score_row(grid, offset, banner_rows, first_row)
        if score <= 0:
            continue
        candidates.append(
            HeaderCandidate(
                row=first_row + offset, score=round(score, 4), nonempty=nonempty
            )
        )

    candidates.sort(key=lambda c: (-c.score, c.row))
    return candidates[:MAX_CANDIDATES]


def select_header_rows(
    candidates: list[HeaderCandidate],
    override: list[int] | None = None,
    multi_row_threshold: float = MULTI_ROW_THRESHOLD,
) -> list[int]:
    """Pick the header row or rows from scored candidates.

    An adjacent row is included when it scores at least
    ``multi_row_threshold`` of the best row's score, which is how a two-row
    header is recognized.
    """
    if override:
        return sorted(set(override))
    if not candidates:
        return []

    best = candidates[0]
    by_row = {c.row: c for c in candidates}
    rows = {best.row}
    for neighbour in (best.row - 1, best.row + 1):
        candidate = by_row.get(neighbour)
        if candidate and candidate.score >= multi_row_threshold * best.score:
            rows.add(neighbour)
    return sorted(rows)
