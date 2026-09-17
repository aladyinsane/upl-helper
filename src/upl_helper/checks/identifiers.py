"""IDN - provider identifier integrity.

The cheapest real checks in the suite. IDN004 in particular needs no reference
data at all and catches transposed digits outright.
"""

from __future__ import annotations

from collections.abc import Iterator

from upl_helper.checks.findings import Finding, Scope, Severity
from upl_helper.checks.registry import CheckContext, Skip, check

NPI_PREFIX = "80840"
CCN_LENGTH = 6

UNVERIFIED_TABLES = (
    "the CCN reference tables are marked unverified "
    "(config/reference/ccn-tables.yaml). Verify them against a CMS source and "
    "set verified: true; until then this check would invent findings."
)


def npi_check_digit_valid(npi: str) -> bool:
    """Luhn over the NPI with the 80840 prefix, per the CMS NPI standard."""
    if len(npi) != 10 or not npi.isdigit():
        return False

    digits = [int(d) for d in NPI_PREFIX + npi[:9]]
    total = 0
    # Double every second digit from the right of the payload.
    for position, digit in enumerate(reversed(digits)):
        if position % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return (total + int(npi[9])) % 10 == 0


@check("IDN001", "IDN", "CCN is well formed", Severity.ERROR)
def idn001_ccn_format(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("ccn")
    for row, raw in ctx.frame["ccn"].dropna().items():
        value = str(raw).strip()
        problem = None
        if len(value) != CCN_LENGTH:
            problem = f"expected {CCN_LENGTH} characters, got {len(value)}"
        elif not value[:2].isdigit():
            problem = "the first two characters are not a numeric state code"
        elif not value[2:].isdigit():
            problem = "the last four characters are not digits"

        if problem:
            yield Finding(
                check_id="IDN001",
                severity=Severity.ERROR,
                scope=Scope.CELL,
                subject=value,
                field="ccn",
                message=f"CCN {value!r} is malformed: {problem}",
                observed=value,
                expected="6 characters: 2-digit state code plus 4 digits",
                cell=ctx.cell(row, "ccn"),
            )


@check("IDN002", "IDN", "CCN state prefix matches the filing state", Severity.WARN)
def idn002_ccn_state_prefix(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("ccn")
    if not ctx.reference.verified:
        raise Skip(UNVERIFIED_TABLES)
    if ctx.context is None or not getattr(ctx.context, "state", None):
        raise Skip("no state given for this run; pass --state")

    expected_state = ctx.context.state.upper()
    for row, raw in ctx.frame["ccn"].dropna().items():
        value = str(raw).strip()
        if len(value) < 2 or not value[:2].isdigit():
            continue  # IDN001's problem, not this one's
        actual = ctx.reference.state_for_prefix(value[:2])
        if actual is None:
            yield Finding(
                check_id="IDN002",
                severity=Severity.WARN,
                scope=Scope.CELL,
                subject=value,
                field="ccn",
                message=f"CCN prefix {value[:2]!r} is not a known state code",
                observed=value[:2],
                expected=expected_state,
                cell=ctx.cell(row, "ccn"),
            )
        elif actual != expected_state:
            yield Finding(
                check_id="IDN002",
                severity=Severity.WARN,
                scope=Scope.CELL,
                subject=value,
                field="ccn",
                message=(
                    f"CCN {value} belongs to {actual}, but this demonstration is "
                    f"for {expected_state}"
                ),
                observed=actual,
                expected=expected_state,
                cell=ctx.cell(row, "ccn"),
            )


@check("IDN003", "IDN", "CCN facility type fits the provider type", Severity.WARN)
def idn003_ccn_facility_type(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("ccn")
    if not ctx.reference.verified:
        raise Skip(UNVERIFIED_TABLES)
    provider_type = getattr(ctx.context, "provider_type", None)
    if not provider_type:
        raise Skip("no provider type given for this run")

    ranges = ctx.reference.ranges_for(provider_type)
    if not ranges:
        raise Skip(f"no CCN ranges recorded for provider type {provider_type!r}")

    readable = ", ".join(f"{lo:04d}-{hi:04d}" for lo, hi in ranges)
    for row, raw in ctx.frame["ccn"].dropna().items():
        value = str(raw).strip()
        if len(value) != CCN_LENGTH or not value[2:].isdigit():
            continue
        sequence = int(value[2:])
        if not any(lo <= sequence <= hi for lo, hi in ranges):
            yield Finding(
                check_id="IDN003",
                severity=Severity.WARN,
                scope=Scope.CELL,
                subject=value,
                field="ccn",
                message=(
                    f"CCN {value} has sequence {sequence:04d}, outside the ranges "
                    f"expected for {provider_type} ({readable})"
                ),
                observed=sequence,
                expected=readable,
                cell=ctx.cell(row, "ccn"),
            )


@check("IDN004", "IDN", "NPI passes its check digit", Severity.ERROR)
def idn004_npi_check_digit(ctx: CheckContext) -> Iterator[Finding]:
    ctx.require_fields("npi")
    for row, raw in ctx.frame["npi"].dropna().items():
        value = str(raw).strip()
        if not npi_check_digit_valid(value):
            yield Finding(
                check_id="IDN004",
                severity=Severity.ERROR,
                scope=Scope.CELL,
                subject=value,
                field="npi",
                message=(
                    f"NPI {value!r} fails its check digit. Most often a transposed "
                    "or mistyped digit."
                ),
                observed=value,
                expected="a 10-digit NPI passing the Luhn check",
                cell=ctx.cell(row, "npi"),
            )
