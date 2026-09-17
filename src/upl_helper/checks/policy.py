"""POL - policy and regulatory conformance."""

from __future__ import annotations

from collections.abc import Iterator

from upl_helper.checks.findings import Finding, Scope, Severity
from upl_helper.checks.registry import CheckContext, check


@check(
    "POL002",
    "POL",
    "Aggregate payments within the aggregate UPL, by ownership category",
    Severity.ERROR,
)
def pol002_aggregate_upl(ctx: CheckContext) -> Iterator[Finding]:
    """The actual legal test.

    The UPL is demonstrated in aggregate by ownership category, not provider by
    provider. One provider over its own UPL is PLA008 at WARN; a category over
    its aggregate UPL is this, at ERROR.
    """
    ctx.require_fields("upl_amount", "medicaid_payments_total", "ownership_category")
    tol = ctx.thresholds.money_abs_tol

    totals = ctx.frame.groupby("ownership_category", dropna=False)[
        ["upl_amount", "medicaid_payments_total"]
    ].sum()

    for category, record in totals.iterrows():
        excess = record["medicaid_payments_total"] - record["upl_amount"]
        if excess > tol:
            yield Finding(
                check_id="POL002",
                severity=Severity.ERROR,
                scope=Scope.RUN,
                subject=str(category),
                field="medicaid_payments_total",
                message=(
                    f"aggregate payments {record['medicaid_payments_total']:,.2f} "
                    f"exceed the aggregate UPL {record['upl_amount']:,.2f} "
                    f"by {excess:,.2f}"
                ),
                observed=float(record["medicaid_payments_total"]),
                expected=float(record["upl_amount"]),
            )
