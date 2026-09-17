"""PLA - plausibility, outliers and duplicates."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator

from upl_helper.checks.findings import Finding, Scope, Severity
from upl_helper.checks.registry import CheckContext, Skip, check

# Fields that cannot sensibly be negative. upl_gap is absent on purpose: a
# negative gap means payments exceed the UPL, which is a finding of its own
# (PLA008), not a data-entry error.
NON_NEGATIVE_FIELDS = (
    "medicaid_days",
    "medicaid_discharges",
    "medicaid_charges",
    "cost_to_charge_ratio",
    "medicaid_cost",
    "upl_amount",
    "medicaid_payments_base",
    "medicaid_payments_total",
)

MAD_SCALE = 0.6745


@check("PLA001", "PLA", "Cost-to-charge ratio within plausible bounds", Severity.WARN)
def pla001_ccr_range(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("cost_to_charge_ratio")
    low, high = ctx.thresholds.ccr_min, ctx.thresholds.ccr_max

    for row, value in ctx.frame["cost_to_charge_ratio"].dropna().items():
        if value < low or value > high:
            yield Finding(
                check_id="PLA001",
                severity=Severity.WARN,
                scope=Scope.CELL,
                subject=ctx.subject(row),
                field="cost_to_charge_ratio",
                message=(
                    f"CCR {value:.4f} is outside the plausible range [{low}, {high}]"
                ),
                observed=float(value),
                expected=f"[{low}, {high}]",
                cell=ctx.cell(row, "cost_to_charge_ratio"),
            )


@check("PLA005", "PLA", "No negative values where none are possible", Severity.ERROR)
def pla005_negative_values(ctx: CheckContext) -> Iterator[Finding]:
    for field_name in NON_NEGATIVE_FIELDS:
        if field_name not in ctx.frame.columns:
            continue
        series = ctx.frame[field_name].dropna()
        for row, value in series[series < 0].items():
            yield Finding(
                check_id="PLA005",
                severity=Severity.ERROR,
                scope=Scope.CELL,
                subject=ctx.subject(row),
                field=field_name,
                message=f"{field_name} is negative ({value:,.2f})",
                observed=float(value),
                expected=">= 0",
                cell=ctx.cell(row, field_name),
            )


@check("PLA008", "PLA", "Provider payments do not exceed its UPL", Severity.WARN)
def pla008_payments_over_upl(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("upl_amount", "medicaid_payments_total")
    tol = ctx.thresholds.money_abs_tol

    rows = ctx.frame.dropna(subset=["upl_amount", "medicaid_payments_total"])
    for row, record in rows.iterrows():
        excess = record["medicaid_payments_total"] - record["upl_amount"]
        if excess > tol:
            yield Finding(
                check_id="PLA008",
                severity=Severity.WARN,
                scope=Scope.PROVIDER,
                subject=ctx.subject(row),
                field="medicaid_payments_total",
                message=(
                    f"payments {record['medicaid_payments_total']:,.2f} exceed this "
                    f"provider's UPL {record['upl_amount']:,.2f} by {excess:,.2f}"
                ),
                observed=float(record["medicaid_payments_total"]),
                expected=float(record["upl_amount"]),
                cell=ctx.cell(row, "medicaid_payments_total"),
            )


@check("PLA009", "PLA", "Per-unit cost outliers", Severity.WARN)
def pla009_per_unit_outliers(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("medicaid_cost", "medicaid_days")

    rows = ctx.frame.dropna(subset=["medicaid_cost", "medicaid_days"])
    rows = rows[rows["medicaid_days"] > 0]
    if len(rows) < ctx.thresholds.outlier_min_rows:
        raise Skip(
            f"needs at least {ctx.thresholds.outlier_min_rows} rows with cost and "
            f"days; have {len(rows)}"
        )

    per_unit = rows["medicaid_cost"] / rows["medicaid_days"]
    median = per_unit.median()
    # Median absolute deviation, not a standard deviation: a mean and SD are
    # dragged around by the very outliers being looked for.
    mad = (per_unit - median).abs().median()
    if mad == 0:
        raise Skip("no spread in cost per day (MAD is zero)")

    scores = MAD_SCALE * (per_unit - median) / mad
    for row, score in scores.items():
        if abs(score) > ctx.thresholds.outlier_mad_threshold:
            yield Finding(
                check_id="PLA009",
                severity=Severity.WARN,
                scope=Scope.PROVIDER,
                subject=ctx.subject(row),
                field="medicaid_cost",
                message=(
                    f"cost per day {per_unit[row]:,.2f} is a long way from the median "
                    f"{median:,.2f} (modified z-score {score:.1f})"
                ),
                observed=float(per_unit[row]),
                expected=float(median),
                cell=ctx.cell(row, "medicaid_cost"),
            )


@check("PLA010", "PLA", "Leading-digit distribution (Benford)", Severity.INFO)
def pla010_benford(ctx: CheckContext) -> Iterator[Finding]:
    import math

    ctx.require_fields("medicaid_payments_total")
    values = ctx.frame["medicaid_payments_total"].dropna().abs()
    values = values[values > 0]
    if len(values) < ctx.thresholds.benford_min_rows:
        raise Skip(
            f"needs at least {ctx.thresholds.benford_min_rows} non-zero values; "
            f"have {len(values)}"
        )

    digits = Counter(int(str(int(v))[0]) for v in values if int(v) > 0)
    total = sum(digits.values())
    worst_digit, worst_deviation = 0, 0.0
    for digit in range(1, 10):
        expected = math.log10(1 + 1 / digit)
        actual = digits.get(digit, 0) / total
        deviation = abs(actual - expected)
        if deviation > worst_deviation:
            worst_digit, worst_deviation = digit, deviation

    if worst_deviation > ctx.thresholds.benford_max_abs_deviation:
        # INFO on purpose. A Benford departure is a reason to look, never a
        # finding on its own: small or bounded populations break it honestly.
        yield Finding(
            check_id="PLA010",
            severity=Severity.INFO,
            scope=Scope.RUN,
            field="medicaid_payments_total",
            message=(
                f"leading digit {worst_digit} appears {worst_deviation:.1%} away from "
                f"the Benford expectation across {total} payments; worth a look, not "
                "a finding on its own"
            ),
            observed=round(worst_deviation, 4),
            expected=ctx.thresholds.benford_max_abs_deviation,
        )


@check("PLA011", "PLA", "No duplicate providers", Severity.ERROR)
def pla011_duplicate_providers(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("ccn")
    keys = ctx.frame["ccn"].dropna()
    counts = keys.value_counts()

    for key, count in counts[counts > 1].items():
        rows = list(keys[keys == key].index)
        cells = [ctx.cell(r, "ccn") for r in rows]
        located = ", ".join(c for c in cells if c) or f"rows {rows}"
        yield Finding(
            check_id="PLA011",
            severity=Severity.ERROR,
            scope=Scope.PROVIDER,
            subject=str(key),
            field="ccn",
            message=f"CCN {key} appears on {count} rows: {located}",
            observed=int(count),
            expected=1,
            cell=cells[0] if cells else None,
        )
