"""Workbook profiling (SPEC-0002 AC-1..3, AC-9..14, AC-20, AC-21)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tests.builders import (
    CANARY,
    CANARY_NUMBER,
    empty_below_header_workbook,
    simple_workbook,
)
from upl_helper.errors import UnsupportedWorkbookError
from upl_helper.profile import profile_path, render
from upl_helper.profile.loader import file_sha256


def test_hidden_sheets_are_included_with_their_state(tmp_path: Path) -> None:
    """AC-1."""
    book = simple_workbook(tmp_path / "hidden.xlsx", hidden_sheet=True)
    states = {s.name: s.state for s in profile_path(book).sheets}
    assert states["Demonstration"] == "visible"
    assert states["Lookups"] == "hidden"
    assert states["Internal"] == "veryHidden"


def test_hidden_columns_are_included_and_flagged(tmp_path: Path) -> None:
    """AC-2."""
    book = simple_workbook(tmp_path / "cols.xlsx", hidden_columns=("B", "D"))
    columns = {c.letter: c.hidden for c in profile_path(book).sheets[0].columns}
    assert columns["B"] is True
    assert columns["D"] is True
    assert columns["A"] is False


def test_protected_sheet_profiles_without_modifying_the_input(tmp_path: Path) -> None:
    """AC-3."""
    book = simple_workbook(
        tmp_path / "prot.xlsx", protect=True, protect_password="secret"
    )
    before = file_sha256(book)
    sheet = profile_path(book).sheets[0]
    assert sheet.protection.enabled is True
    assert sheet.protection.password_hash_present is True
    assert file_sha256(book) == before


def test_uniform_formula_column_collapses_to_one_pattern(tmp_path: Path) -> None:
    """AC-9."""
    book = simple_workbook(tmp_path / "f.xlsx", rows=10)
    column_e = next(c for c in profile_path(book).sheets[0].columns if c.letter == "E")
    assert len(column_e.formula_patterns) == 1
    pattern = column_e.formula_patterns[0]
    assert pattern.pattern == "=C{row}*D{row}"
    assert pattern.count == 10
    assert column_e.cell_type_counts.formula == 10


def test_one_hardcoded_constant_among_formulas_is_visible(tmp_path: Path) -> None:
    """AC-10. This is the defect STR003 will look for."""
    book = simple_workbook(
        tmp_path / "const.xlsx", rows=40, constant_in_formula_column=True
    )
    column_e = next(c for c in profile_path(book).sheets[0].columns if c.letter == "E")
    assert len(column_e.formula_patterns) == 1
    assert column_e.formula_patterns[0].count == 39
    assert column_e.cell_type_counts.numeric >= 1


def test_number_format_is_recorded(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "fmt.xlsx")
    column_e = next(c for c in profile_path(book).sheets[0].columns if c.letter == "E")
    assert column_e.number_format == "#,##0.00"


def test_header_normalization_reaches_the_descriptor(tmp_path: Path) -> None:
    """AC-8, end to end."""
    book = simple_workbook(tmp_path / "h.xlsx")
    normalized = [c.header_normalized for c in profile_path(book).sheets[0].columns]
    assert "medicare_provider_number_ccn" in normalized


def test_two_profiles_differ_only_in_the_timestamp(tmp_path: Path) -> None:
    """AC-11."""
    book = simple_workbook(tmp_path / "det.xlsx")
    first = render(profile_path(book))
    second = render(profile_path(book))

    def strip_timestamp(text: str) -> list[str]:
        return [ln for ln in text.splitlines() if "profiled_at" not in ln]

    assert strip_timestamp(first) == strip_timestamp(second)


def test_descriptor_keys_are_sorted(tmp_path: Path) -> None:
    """AC-12."""
    book = simple_workbook(tmp_path / "sorted.xlsx")
    payload = json.loads(render(profile_path(book), "json"))
    assert list(payload) == sorted(payload)
    sheet = payload["sheets"][0]
    assert list(sheet) == sorted(sheet)


@pytest.mark.parametrize("fmt", ["yaml", "json"])
@pytest.mark.parametrize("strict", [False, True])
def test_no_cell_values_reach_the_descriptor(
    tmp_path: Path, fmt: str, strict: bool
) -> None:
    """AC-13. The redaction rule, enforced rather than trusted."""
    book = simple_workbook(
        tmp_path / f"canary-{fmt}-{strict}.xlsx",
        canary_data=True,
        data_validation=True,
        hidden_sheet=True,
    )
    text = render(profile_path(book, strict=strict), fmt)
    assert CANARY not in text


@pytest.mark.parametrize("fmt", ["yaml", "json"])
def test_no_numeric_cell_values_reach_the_descriptor(tmp_path: Path, fmt: str) -> None:
    """AC-14. A numeric canary, which would not survive as a string."""
    book = simple_workbook(tmp_path / f"num-{fmt}.xlsx", canary_data=True)
    text = render(profile_path(book), fmt)
    assert str(CANARY_NUMBER) not in text
    assert "987654321" not in text


def test_strict_drops_data_validation_formulas(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "dv.xlsx", data_validation=True)
    lenient = profile_path(book).sheets[0].data_validations
    strict = profile_path(book, strict=True).sheets[0].data_validations
    assert lenient and lenient[0].formula1 is not None
    assert strict and strict[0].formula1 is None


def test_merged_ranges_are_recorded(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "merge.xlsx", banner=True)
    assert "A1:E1" in profile_path(book).sheets[0].merged_ranges


def test_sheet_filter_limits_output(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "filter.xlsx", hidden_sheet=True)
    descriptor = profile_path(book, sheet_names=["Lookups"])
    assert [s.name for s in descriptor.sheets] == ["Lookups"]
    assert descriptor.workbook.sheet_count == 3


def test_empty_data_area_profiles_cleanly(tmp_path: Path) -> None:
    """AC-21."""
    book = empty_below_header_workbook(tmp_path / "empty.xlsx")
    sheet = profile_path(book).sheets[0]
    assert sheet.nonempty_row_count == 1
    assert all(c.cell_type_counts.formula == 0 for c in sheet.columns)


def test_non_zip_input_raises_a_clear_error(tmp_path: Path) -> None:
    """AC-20."""
    bogus = tmp_path / "notreally.xlsx"
    bogus.write_text("this is not a workbook")
    with pytest.raises(UnsupportedWorkbookError) as excinfo:
        profile_path(bogus)
    assert "notreally.xlsx" in str(excinfo.value)


def test_missing_file_raises_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedWorkbookError):
        profile_path(tmp_path / "absent.xlsx")


def test_legacy_xls_is_rejected_by_extension(tmp_path: Path) -> None:
    legacy = tmp_path / "old.xls"
    legacy.write_bytes(b"\xd0\xcf\x11\xe0")
    with pytest.raises(UnsupportedWorkbookError) as excinfo:
        profile_path(legacy)
    assert ".xls" in str(excinfo.value)


def test_yaml_output_round_trips(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "rt.xlsx")
    payload = yaml.safe_load(render(profile_path(book), "yaml"))
    assert payload["descriptor_version"] == 1
    assert payload["source"]["filename"] == "rt.xlsx"
    assert payload["source"]["sha256"] == file_sha256(book)
