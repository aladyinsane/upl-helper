"""End-to-end CLI behavior for `upl profile` and `upl unprotect`."""

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


def test_extract_warns_when_the_mapping_is_unverified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SPEC-0003 AC-20."""
    from tests.builders import upl_workbook

    book = upl_workbook(tmp_path / "wb.xlsx")
    out = tmp_path / "frame.csv"
    exit_code = cli.main(
        [
            "extract",
            str(book),
            "-m",
            "config/templates/inpatient-hospital-provisional.yaml",
            "-o",
            str(out),
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "not verified against a real CMS template" in captured
    assert out.exists()
    assert "014001" in out.read_text()


def test_check_reports_findings_and_exits_nonzero_on_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SPEC-0004 AC-20, end to end."""
    from tests.builders import UPL_HEADERS, upl_workbook

    # Private Regional's payments exceed its UPL, and it is the only private
    # provider, so the category aggregate is over too.
    book = upl_workbook(tmp_path / "wb.xlsx", headers=UPL_HEADERS)
    exit_code = cli.main(
        [
            "check",
            str(book),
            "-m",
            "config/templates/inpatient-hospital-provisional.yaml",
            "--state",
            "IL",
            "--year",
            "2024",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 1
    assert "ERROR POL002" in out
    assert "WARN  PLA008" in out
    assert "not verified against a real CMS template" in out


def test_check_writes_json(tmp_path: Path) -> None:
    import json

    from tests.builders import upl_workbook

    book = upl_workbook(tmp_path / "wb.xlsx")
    out = tmp_path / "findings.json"
    cli.main(
        [
            "check",
            str(book),
            "-m",
            "config/templates/inpatient-hospital-provisional.yaml",
            "--format",
            "json",
            "-o",
            str(out),
        ]
    )
    payload = json.loads(out.read_text())
    assert {f["check_id"] for f in payload["findings"]} >= {"POL002", "PLA008"}
