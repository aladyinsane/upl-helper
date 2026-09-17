"""Finding the header row or rows in a worksheet.

CMS templates put title banners, notes and blank spacer rows above the real
header, so the header cannot be assumed to be row 1. This scores candidate
rows and reports all of them rather than only the winner, because a human
reading a descriptor needs to see what was rejected.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
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

# A header row is mostly distinct text, with numbers underneath it, and with a
# run of consistently shaped data rows beneath that. The last term matters: a
# stray text row near the bottom of a sheet can otherwise out-score the real
# header, because the handful of rows under it happen to look tidy.
WEIGHT_STRING = 0.30
WEIGHT_DISTINCT = 0.20
WEIGHT_NUMERIC_BELOW = 0.25
WEIGHT_SUPPORT = 0.25

# How many consistently shaped rows below count as full support.
FULL_SUPPORT_ROWS = 5

# An adjacent row joins the header only if it scores nearly as well as the
# best row. Deliberately strict: a single-row header is the common case.
MULTI_ROW_THRESHOLD = 0.85

# How many rows below the header block to sample when deciding what a data row
# in this sheet looks like.
DATA_SIGNATURE_ROWS = 5


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

    # How many rows below share one shape. A real header sits on top of a run
    # of uniform data rows; a stray text row sits on top of almost nothing.
    modal = _modal_signature(grid, row_offset + 1, count=LOOKAHEAD_ROWS)
    supporting = 0
    if modal is not None:
        for below in grid[row_offset + 1 : row_offset + 1 + LOOKAHEAD_ROWS]:
            if row_signature(below) == modal:
                supporting += 1
    support_frac = min(supporting, FULL_SUPPORT_ROWS) / FULL_SUPPORT_ROWS

    score = (
        WEIGHT_STRING * string_frac
        + WEIGHT_DISTINCT * distinct_frac
        + WEIGHT_NUMERIC_BELOW * numeric_frac
        + WEIGHT_SUPPORT * support_frac
    )

    if len(nonempty) < MIN_NONEMPTY_CELLS:
        score *= SPARSE_ROW_PENALTY
    if (first_row + row_offset) in banner_rows:
        score *= WIDE_MERGE_PENALTY

    return score, len(nonempty)


def _cell_kind(value: Any) -> str:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "b"
    if isinstance(value, str):
        return "f" if value.startswith("=") else "s"
    if isinstance(value, bool):
        return "s"
    if isinstance(value, (int, float)):
        return "n"
    return "d"


def row_signature(values: list[Any]) -> tuple[str, ...]:
    """A row's per-column shape: text, number, formula, date or blank.

    Two rows with the same signature are the same kind of row. This is what
    separates a genuine second header row from the first row of data, which
    scoring alone cannot do -- a data row full of provider names and CCNs
    scores almost as well as the header above it.
    """
    return tuple(_cell_kind(v) for v in values)


def _modal_signature(
    grid: list[list[Any]], start_offset: int, count: int = DATA_SIGNATURE_ROWS
) -> tuple[str, ...] | None:
    signatures = [
        row_signature(row)
        for row in grid[start_offset : start_offset + count]
        if any(_cell_kind(v) != "b" for v in row)
    ]
    if not signatures:
        return None
    return Counter(signatures).most_common(1)[0][0]


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
    is_data_row: Callable[[int], bool] | None = None,
) -> list[int]:
    """Pick the header row or rows from scored candidates.

    An adjacent row joins the header when it scores at least
    ``multi_row_threshold`` of the best row's score *and* does not look like
    one of the sheet's data rows. Score alone is not enough: the first data
    row of a provider table is mostly text and scores nearly as well as the
    header above it.
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
        if candidate is None:
            continue
        if candidate.score < multi_row_threshold * best.score:
            continue
        if is_data_row is not None and is_data_row(neighbour):
            continue
        rows.add(neighbour)
    return sorted(rows)


def detect_and_select(
    worksheet: Any, override: list[int] | None = None
) -> tuple[list[int], list[HeaderCandidate]]:
    """Detect header candidates and choose the header rows. The usual entry point."""
    candidates = detect_header_rows(worksheet)
    if override:
        return sorted(set(override)), candidates
    if not candidates:
        return [], candidates

    first_row = worksheet.min_row or 1
    last_row = min(
        worksheet.max_row or 1, first_row + MAX_SCAN_ROWS + LOOKAHEAD_ROWS - 1
    )
    grid = [
        list(row)
        for row in worksheet.iter_rows(
            min_row=first_row, max_row=last_row, values_only=True
        )
    ]

    def is_data_row(row: int) -> bool:
        offset = row - first_row
        if offset < 0 or offset >= len(grid):
            return False
        # Compare against the rows that would follow if this row joined the
        # header block.
        modal = _modal_signature(grid, offset + 1)
        return modal is not None and row_signature(grid[offset]) == modal

    return select_header_rows(candidates, is_data_row=is_data_row), candidates
