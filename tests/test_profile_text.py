"""Header normalization and formula templating (SPEC-0002 AC-8, AC-9)."""

from __future__ import annotations

import pytest

from upl_helper.profile.text import normalize_header, templatize_formula


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Medicare Provider Number (CCN)", "medicare_provider_number_ccn"),
        ("  Total   Medicaid  Days  ", "total_medicaid_days"),
        ("Cost-to-Charge Ratio:", "cost_to_charge_ratio"),
        ("UPL Gap *", "upl_gap"),
        ("", None),
        ("   ", None),
        (None, None),
        ("***", None),
    ],
)
def test_normalize_header(raw: str | None, expected: str | None) -> None:
    assert normalize_header(raw) == expected


@pytest.mark.parametrize(
    ("formula", "row", "expected"),
    [
        ("=D7*E7", 7, "=D{row}*E{row}"),
        ("=SUM(D7:D20)", 7, "=SUM(D{row}:D20)"),
        ("=LOG10(E7)", 7, "=LOG10(E{row})"),
        ("=$C$7+C7", 7, "=$C$7+C{row}"),
        ("=$C7", 7, "=$C{row}"),
        ("=D7", 8, "=D7"),
        ("=Sheet2!D7+D8", 7, "=Sheet2!D{row}+D8"),
        ("='FY2024'!D2024", 2024, "='FY2024'!D{row}"),
        ('=IF(A7="row7",B7,0)', 7, '=IF(A{row}="row7",B{row},0)'),
        ('=CONCATENATE("A7 ",A7)', 7, '=CONCATENATE("A7 ",A{row})'),
        ("=AA100/AB100", 100, "=AA{row}/AB{row}"),
    ],
)
def test_templatize_formula(formula: str, row: int, expected: str) -> None:
    assert templatize_formula(formula, row) == expected


def test_templatize_leaves_escaped_quotes_intact() -> None:
    formula = '=IF(A5="say ""A5""",B5,0)'
    assert templatize_formula(formula, 5) == '=IF(A{row}="say ""A5""",B{row},0)'
