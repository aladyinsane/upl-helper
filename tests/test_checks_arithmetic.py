"""ARI checks (SPEC-0004 AC-2..4)."""

from __future__ import annotations

from tests.checkhelpers import make_context, provider
from upl_helper.checks.arithmetic import (
    ari004_gap_arithmetic,
    ari005_payment_components,
    ari006_cost_from_ccr,
)
from upl_helper.checks.registry import Skip


def test_ari004_passes_a_consistent_gap() -> None:
    """AC-2, the passing half."""
    ctx = make_context([provider()])
    assert list(ari004_gap_arithmetic(ctx)) == []


def test_ari004_flags_an_inconsistent_gap() -> None:
    """AC-2."""
    ctx = make_context([provider(upl_gap=123_456.0)])
    findings = list(ari004_gap_arithmetic(ctx))
    assert len(findings) == 1
    assert findings[0].expected == 100_000.0
    assert findings[0].observed == 123_456.0
    assert findings[0].cell is not None


def test_ari004_tolerates_a_rounding_cent() -> None:
    ctx = make_context([provider(upl_gap=100_000.005)])
    assert list(ari004_gap_arithmetic(ctx)) == []


def test_ari004_skips_rows_with_a_missing_input() -> None:
    """AC-3."""
    ctx = make_context([provider(), provider(ccn="140002", upl_amount=None)])
    assert list(ari004_gap_arithmetic(ctx)) == []


def test_ari004_skips_entirely_when_gap_is_absent() -> None:
    """AC-23. The whole check skips rather than flagging every row."""
    ctx = make_context([provider(upl_gap=None)])
    try:
        list(ari004_gap_arithmetic(ctx))
    except Skip as skip:
        assert "upl_gap" in skip.reason
    else:
        raise AssertionError("expected the check to skip")


def test_ari005_flags_components_that_do_not_sum() -> None:
    """AC-4."""
    ctx = make_context([provider(medicaid_payments_supplemental=150_000.0)])
    findings = list(ari005_payment_components(ctx))
    assert len(findings) == 1
    assert findings[0].expected == 450_000.0


def test_ari005_passes_when_they_sum() -> None:
    assert list(ari005_payment_components(make_context([provider()]))) == []


def test_ari005_inflates_base_before_summing() -> None:
    """A trend factor other than 1.0 applies to base payments only, per CMS's
    own formula (inpatient hospital variable 318) -- not to supplemental."""
    ctx = make_context(
        [
            provider(
                medicaid_trend_factor=1.10,
                medicaid_payments_total=430_000.0,  # 100_000 + (300_000 * 1.10)
            )
        ]
    )
    assert list(ari005_payment_components(ctx)) == []


def test_ari005_flags_a_total_that_ignores_the_trend_factor() -> None:
    ctx = make_context(
        [provider(medicaid_trend_factor=1.10)]
    )  # total stays the un-inflated default, 400_000.0
    findings = list(ari005_payment_components(ctx))
    assert len(findings) == 1
    assert findings[0].expected == 430_000.0


def test_ari005_treats_missing_factors_as_no_change() -> None:
    """A mapping that never supplies the factor fields gets the pre-fix
    behaviour: total == base + supplemental, unscaled."""
    ctx = make_context(
        [provider(medicaid_trend_factor=None, medicaid_other_adjustment_factor=None)]
    )
    assert list(ari005_payment_components(ctx)) == []


def test_ari006_flags_cost_that_does_not_follow_from_the_ccr() -> None:
    ctx = make_context([provider(medicaid_cost=900_000.0)])
    findings = list(ari006_cost_from_ccr(ctx))
    assert len(findings) == 1
    assert findings[0].expected == 400_000.0


def test_ari006_tolerates_ccr_rounding_on_large_charges() -> None:
    ctx = make_context(
        [provider(medicaid_charges=1_000_000_000.0, medicaid_cost=400_000_100.0)]
    )
    assert list(ari006_cost_from_ccr(ctx)) == []
