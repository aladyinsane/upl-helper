"""End-to-end CLI behaviour for `upl profile` and `upl unprotect`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.builders import simple_workbook
from upl_helper import cli


def test_profile_writes_a_default_named_descriptor(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "wb.xlsx")
    assert cli.main(["profile", str(book)]) == 0
    descriptor = tmp_path / "wb.descriptor.yaml"
    assert descriptor.exists()
    assert yaml.safe_load(descriptor.read_text())["descriptor_version"] == 1


def test_profile_honours_output_and_format(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "wb.xlsx")
    out = tmp_path / "custom.json"
    assert cli.main(["profile", str(book), "-o", str(out), "--format", "json"]) == 0
    assert out.read_text().lstrip().startswith("{")


def test_profile_accepts_a_comma_separated_header_row(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "wb.xlsx", banner=True)
    out = tmp_path / "d.yaml"
    assert cli.main(["profile", str(book), "-o", str(out), "--header-row", "4,5"]) == 0
    assert yaml.safe_load(out.read_text())["sheets"][0]["header"]["rows"] == [4, 5]


def test_profile_reports_a_bad_file_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bogus = tmp_path / "bogus.xlsx"
    bogus.write_text("not a workbook")
    assert cli.main(["profile", str(bogus)]) == 2
    assert "error:" in capsys.readouterr().err


def test_unprotect_writes_output_and_a_report(tmp_path: Path) -> None:
    book = simple_workbook(tmp_path / "wb.xlsx", protect=True, hidden_columns=("B",))
    out = tmp_path / "clean.xlsx"
    report = tmp_path / "report.yaml"
    exit_code = cli.main(
        ["unprotect", str(book), "-o", str(out), "--unhide", "--report", str(report)]
    )
    assert exit_code == 0
    assert out.exists()
    payload = yaml.safe_load(report.read_text())
    assert payload["removed_sheet_protection"] == ["Demonstration"]
