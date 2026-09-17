"""Header detection (SPEC-0002 AC-4 through AC-7)."""

from __future__ import annotations

from pathlib import Path

from tests.builders import multi_row_header_workbook, simple_workbook
from upl_helper.profile import profile_path
from upl_helper.profile.headers import select_header_rows


def test_header_found_below_a_merged_title_banner(tmp_path: Path) -> None:
    """AC-4."""
    book = simple_workbook(tmp_path / "banner.xlsx", banner=True)
    sheet = profile_path(book).sheets[0]
    assert sheet.header.rows == [4]
    assert sheet.header.detected is True


def test_header_found_without_a_banner(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "plain.xlsx", banner=False)
    assert profile_path(book).sheets[0].header.rows == [1]


def test_multiple_candidates_are_scored_and_reported(tmp_path: Path) -> None:
    """AC-5."""
    book = simple_workbook(tmp_path / "banner.xlsx", banner=True)
    candidates = profile_path(book).sheets[0].header.candidates
    assert len(candidates) >= 2
    scores = [c.score for c in candidates]
    assert scores == sorted(scores, reverse=True)
    assert all(c.score > 0 for c in candidates)


def test_banner_row_scores_below_the_real_header(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "banner.xlsx", banner=True)
    by_row = {c.row: c.score for c in profile_path(book).sheets[0].header.candidates}
    assert by_row[4] > by_row.get(1, 0.0)


def test_header_row_override(tmp_path: Path) -> None:
    """AC-6."""
    book = simple_workbook(tmp_path / "banner.xlsx", banner=True)
    descriptor = profile_path(book, header_row=[2])
    assert descriptor.sheets[0].header.rows == [2]
    assert descriptor.options.header_row_override == [2]


def test_multi_row_header_is_joined_top_to_bottom(tmp_path: Path) -> None:
    """AC-7."""
    book = multi_row_header_workbook(tmp_path / "multi.xlsx")
    sheet = profile_path(book).sheets[0]
    assert sheet.header.rows == [1, 2]
    headers = {c.letter: c.header_text for c in sheet.columns}
    assert headers["A"] == "Provider / Name"
    assert headers["B"] == "Provider / CCN"
    assert headers["D"] == "Rate / Per Diem"


def test_select_header_rows_prefers_the_single_best_row() -> None:
    from upl_helper.profile.models import HeaderCandidate

    candidates = [
        HeaderCandidate(row=4, score=0.90, nonempty=5),
        HeaderCandidate(row=1, score=0.30, nonempty=1),
    ]
    assert select_header_rows(candidates) == [4]


def test_select_header_rows_joins_a_close_adjacent_row() -> None:
    from upl_helper.profile.models import HeaderCandidate

    candidates = [
        HeaderCandidate(row=2, score=0.90, nonempty=5),
        HeaderCandidate(row=1, score=0.88, nonempty=5),
    ]
    assert select_header_rows(candidates) == [1, 2]


def test_select_header_rows_ignores_a_distant_adjacent_row() -> None:
    from upl_helper.profile.models import HeaderCandidate

    candidates = [
        HeaderCandidate(row=2, score=0.90, nonempty=5),
        HeaderCandidate(row=1, score=0.40, nonempty=5),
    ]
    assert select_header_rows(candidates) == [2]


def test_no_candidates_yields_no_header() -> None:
    assert select_header_rows([]) == []
