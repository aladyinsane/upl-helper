"""PLA and POL checks (SPEC-0004 AC-5..10)."""

from __future__ import annotations

import pytest

from tests.checkhelpers import make_context, provider
from upl_helper.checks.identifiers import npi_check_digit_valid
from upl_helper.checks.plausibility import (
    pla001_ccr_range,
    pla005_negative_values,
    pla008_payments_over_upl,
    pla009_per_unit_outliers,
    pla010_benford,
    pla011_duplicate_providers,
)
from upl_helper.checks.policy import pol002_aggregate_upl
from upl_helper.checks.registry import Skip
from upl_helper.checks.thresholds import Thresholds


def test_pla001_flags_an_implausible_ccr() -> None:
    ctx = make_context([provider(cost_to_charge_ratio=2.5)])
    findings = list(pla001_ccr_range(ctx))
    assert len(findings) == 1
    assert findings[0].observed == 2.5


def test_pla001_respects_thresholds() -> None:
    """AC-21. Widening the bound silences the finding."""
    record = provider(cost_to_charge_ratio=2.5)
    assert list(pla001_ccr_range(make_context([record]))) != []
    widened = make_context([record], thresholds=Thresholds(ccr_max=3.0))
    assert list(pla001_ccr_range(widened)) == []


def test_pla005_flags_negative_days_and_negative_upl() -> None:
    """AC-5."""
    ctx = make_context(
        [
            provider(medicaid_days=-5.0),
            provider(ccn="140002", upl_amount=-1.0),
        ]
    )
    fields = {f.field for f in pla005_negative_values(ctx)}
    assert fields == {"medicaid_days", "upl_amount"}


def test_pla005_ignores_a_negative_gap() -> None:
    """A negative gap means payments exceed the UPL. That is PLA008, not a typo."""
    ctx = make_context([provider(upl_gap=-100.0)])
    assert list(pla005_negative_values(ctx)) == []


def test_pla008_flags_a_provider_over_its_own_upl() -> None:
    """AC-6."""
    ctx = make_context([provider(medicaid_payments_total=600_000.0)])
    findings = list(pla008_payments_over_upl(ctx))
    assert len(findings) == 1
    assert "exceed this provider's UPL" in findings[0].message


def test_pol002_flags_a_category_over_its_aggregate_upl() -> None:
    """AC-7."""
    ctx = make_context(
        [
            provider(ccn="140001", upl_amount=100.0, medicaid_payments_total=150.0),
            provider(ccn="140002", upl_amount=100.0, medicaid_payments_total=120.0),
        ]
    )
    findings = list(pol002_aggregate_upl(ctx))
    assert len(findings) == 1
    assert findings[0].subject == "private"
    assert findings[0].observed == 270.0


def test_pol002_is_silent_when_the_category_nets_out() -> None:
    """AC-7, the important half.

    One provider over its own UPL does not breach the aggregate test. The
    demonstration is by category, so POL002 must not fire here even though
    PLA008 does.
    """
    records = [
        provider(ccn="140001", upl_amount=100.0, medicaid_payments_total=150.0),
        provider(ccn="140002", upl_amount=300.0, medicaid_payments_total=100.0),
    ]
    ctx = make_context(records)
    assert list(pol002_aggregate_upl(ctx)) == []
    assert len(list(pla008_payments_over_upl(ctx))) == 1


def test_pol002_treats_categories_separately() -> None:
    ctx = make_context(
        [
            provider(
                ccn="140001",
                ownership_category="state",
                upl_amount=100.0,
                medicaid_payments_total=200.0,
            ),
            provider(
                ccn="140002",
                ownership_category="private",
                upl_amount=500.0,
                medicaid_payments_total=100.0,
            ),
        ]
    )
    findings = list(pol002_aggregate_upl(ctx))
    assert [f.subject for f in findings] == ["state"]


def test_pla011_flags_a_duplicate_provider_and_names_both_rows() -> None:
    """AC-8."""
    ctx = make_context([provider(), provider(provider_name="Same CCN Twice")])
    findings = list(pla011_duplicate_providers(ctx))
    assert len(findings) == 1
    assert findings[0].observed == 2
    assert "Demo!B2" in findings[0].message
    assert "Demo!B3" in findings[0].message


def test_pla009_flags_a_per_unit_outlier() -> None:
    """AC-9."""
    records = [
        provider(ccn=f"14{i:04d}", medicaid_days=1000.0, medicaid_cost=400_000.0 + i)
        for i in range(12)
    ]
    records.append(
        provider(ccn="149999", medicaid_days=1000.0, medicaid_cost=9_000_000.0)
    )
    findings = list(pla009_per_unit_outliers(make_context(records)))
    assert [f.subject for f in findings] == ["149999"]


def test_pla009_skips_when_there_is_no_spread() -> None:
    """AC-9. MAD of zero must not divide by zero."""
    records = [
        provider(ccn=f"14{i:04d}", medicaid_days=1000.0, medicaid_cost=400_000.0)
        for i in range(12)
    ]
    with pytest.raises(Skip) as excinfo:
        list(pla009_per_unit_outliers(make_context(records)))
    assert "MAD is zero" in excinfo.value.reason


def test_pla009_skips_on_too_few_rows() -> None:
    with pytest.raises(Skip):
        list(pla009_per_unit_outliers(make_context([provider()])))


def test_pla010_skips_below_the_minimum_row_count() -> None:
    """AC-10."""
    records = [provider(ccn=f"14{i:04d}") for i in range(10)]
    with pytest.raises(Skip) as excinfo:
        list(pla010_benford(make_context(records)))
    assert "at least 50" in excinfo.value.reason


def test_pla010_runs_on_a_large_enough_population() -> None:
    # Every payment starting with 9 is about as un-Benford as it gets.
    records = [
        provider(ccn=f"14{i:04d}", medicaid_payments_total=900_000.0 + i)
        for i in range(60)
    ]
    findings = list(pla010_benford(make_context(records)))
    assert len(findings) == 1
    assert findings[0].severity == "info"


def test_npi_luhn_accepts_valid_and_rejects_transposed() -> None:
    """AC-11."""
    assert npi_check_digit_valid("1234567893") is True
    assert npi_check_digit_valid("1234567839") is False
    assert npi_check_digit_valid("123456789") is False
    assert npi_check_digit_valid("12345abcd9") is False
