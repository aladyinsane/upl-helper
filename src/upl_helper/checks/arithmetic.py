"""ARI - arithmetic and internal consistency.

Every derived value the workbook states is recomputed here independently. The
extractor deliberately does not compute any of them, so these comparisons are
real rather than tautological.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from upl_helper.checks.findings import Finding, Scope, Severity
from upl_helper.checks.registry import CheckContext, check


def _rows_with(frame: pd.DataFrame, *fields: str) -> pd.DataFrame:
    return frame.dropna(subset=list(fields))


@check("ARI004", "ARI", "UPL gap equals UPL minus total payments", Severity.ERROR)
def ari004_gap_arithmetic(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("upl_gap", "upl_amount", "medicaid_payments_total")
    tol = ctx.thresholds.money_abs_tol

    for row, record in _rows_with(
        ctx.frame, "upl_gap", "upl_amount", "medicaid_payments_total"
    ).iterrows():
        expected = record["upl_amount"] - record["medicaid_payments_total"]
        observed = record["upl_gap"]
        if abs(observed - expected) > tol:
            yield Finding(
                check_id="ARI004",
                severity=Severity.ERROR,
                scope=Scope.CELL,
                subject=ctx.subject(row),
                field="upl_gap",
                message=(
                    f"stated gap {observed:,.2f} does not equal UPL minus payments "
                    f"({expected:,.2f}); off by {observed - expected:,.2f}"
                ),
                observed=float(observed),
                expected=float(expected),
                cell=ctx.cell(row, "upl_gap"),
            )


@check("ARI005", "ARI", "Total payments equal base plus supplemental", Severity.ERROR)
def ari005_payment_components(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields(
        "medicaid_payments_total",
        "medicaid_payments_base",
        "medicaid_payments_supplemental",
    )
    tol = ctx.thresholds.money_abs_tol

    for row, record in _rows_with(
        ctx.frame,
        "medicaid_payments_total",
        "medicaid_payments_base",
        "medicaid_payments_supplemental",
    ).iterrows():
        expected = (
            record["medicaid_payments_base"] + record["medicaid_payments_supplemental"]
        )
        observed = record["medicaid_payments_total"]
        if abs(observed - expected) > tol:
            yield Finding(
                check_id="ARI005",
                severity=Severity.ERROR,
                scope=Scope.CELL,
                subject=ctx.subject(row),
                field="medicaid_payments_total",
                message=(
                    f"total payments {observed:,.2f} do not equal base plus "
                    f"supplemental ({expected:,.2f})"
                ),
                observed=float(observed),
                expected=float(expected),
                cell=ctx.cell(row, "medicaid_payments_total"),
            )


@check("ARI006", "ARI", "Cost equals charges times the CCR", Severity.WARN)
def ari006_cost_from_ccr(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("medicaid_cost", "medicaid_charges", "cost_to_charge_ratio")
    tol = ctx.thresholds.money_abs_tol

    for row, record in _rows_with(
        ctx.frame, "medicaid_cost", "medicaid_charges", "cost_to_charge_ratio"
    ).iterrows():
        expected = record["medicaid_charges"] * record["cost_to_charge_ratio"]
        observed = record["medicaid_cost"]
        # Scale the tolerance: a rounded CCR on large charges will not tie to
        # the cent, and flagging that would bury the real breaks.
        scaled_tol = max(tol, abs(expected) * 1e-6)
        if abs(observed - expected) > scaled_tol:
            yield Finding(
                check_id="ARI006",
                severity=Severity.WARN,
                scope=Scope.CELL,
                subject=ctx.subject(row),
                field="medicaid_cost",
                message=(
                    f"cost {observed:,.2f} does not equal charges times CCR "
                    f"({expected:,.2f})"
                ),
                observed=float(observed),
                expected=float(expected),
                cell=ctx.cell(row, "medicaid_cost"),
            )
