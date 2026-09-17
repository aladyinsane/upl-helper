"""The canonical model.

Every check is written against these field names. A template revision or a new
provider type changes the mapping, never this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Dtype(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    DATE = "date"
    RATIO = "ratio"
    MONEY = "money"


class Ownership(StrEnum):
    STATE = "state"
    NON_STATE_GOVERNMENT = "non_state_government"
    PRIVATE = "private"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dtype: Dtype
    required: bool
    description: str


# Grain: one row per provider per demonstration period.
CANONICAL_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("provider_name", Dtype.STRING, True, "Provider name as written"),
    FieldSpec(
        "ccn",
        Dtype.STRING,
        True,
        "Medicare provider number. String, so leading zeros survive.",
    ),
    FieldSpec("npi", Dtype.STRING, False, "National Provider Identifier"),
    FieldSpec("medicaid_provider_id", Dtype.STRING, False, "State Medicaid ID"),
    FieldSpec(
        "ownership_category",
        Dtype.STRING,
        True,
        "state, non_state_government, private or unknown",
    ),
    FieldSpec("cost_report_period_start", Dtype.DATE, False, "Cost report FY begin"),
    FieldSpec("cost_report_period_end", Dtype.DATE, False, "Cost report FY end"),
    FieldSpec("medicaid_days", Dtype.NUMBER, False, "Medicaid inpatient days"),
    FieldSpec("medicaid_discharges", Dtype.NUMBER, False, "Medicaid discharges"),
    FieldSpec("medicaid_charges", Dtype.MONEY, False, "Medicaid covered charges"),
    FieldSpec(
        "cost_to_charge_ratio",
        Dtype.RATIO,
        False,
        "CCR, cost-based methodology's Medicare-side conversion ratio",
    ),
    FieldSpec(
        "payment_to_charge_ratio",
        Dtype.RATIO,
        False,
        "PTC, payment-based methodology's analog to the CCR",
    ),
    FieldSpec("medicaid_cost", Dtype.MONEY, False, "Medicaid cost, the UPL basis"),
    FieldSpec(
        "upl_trend_factor",
        Dtype.RATIO,
        False,
        "Factor inflating the calculated UPL basis to the demonstration year, "
        "distinct from medicaid_trend_factor",
    ),
    FieldSpec("upl_amount", Dtype.MONEY, True, "Demonstrated upper payment limit"),
    FieldSpec("medicaid_payments_base", Dtype.MONEY, False, "Base FFS payments"),
    FieldSpec(
        "medicaid_trend_factor",
        Dtype.RATIO,
        False,
        "Factor inflating base Medicaid payments to the demonstration year, "
        "distinct from upl_trend_factor. Applies to base payments only, not "
        "supplemental.",
    ),
    FieldSpec(
        "medicaid_other_adjustment_factor",
        Dtype.RATIO,
        False,
        "Non-inflation adjustment factor (e.g. volume) applied alongside "
        "medicaid_trend_factor to base payments only",
    ),
    FieldSpec(
        "medicaid_payments_supplemental", Dtype.MONEY, False, "Supplemental payments"
    ),
    FieldSpec("medicaid_payments_total", Dtype.MONEY, True, "Total Medicaid payments"),
    FieldSpec(
        "upl_gap",
        Dtype.MONEY,
        False,
        "UPL minus total payments, as stated in the workbook. Never computed here.",
    ),
)

FIELD_NAMES: tuple[str, ...] = tuple(f.name for f in CANONICAL_FIELDS)
FIELDS_BY_NAME: dict[str, FieldSpec] = {f.name: f for f in CANONICAL_FIELDS}

# Added by the extractor, not mapped from the workbook.
SOURCE_SHEET_COLUMN = "source_sheet"


@dataclass(frozen=True)
class ExtractionContext:
    """Run-level facts that are constant for every row.

    These are deliberately not columns. A demonstration year that varies row to
    row is a contradiction, not data.
    """

    state: str
    provider_type: str
    demonstration_year: int
    methodology: str | None = None
