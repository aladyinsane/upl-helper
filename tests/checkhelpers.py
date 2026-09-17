"""Building a CheckContext straight from records, without a workbook."""

from __future__ import annotations

from typing import Any

import pandas as pd

from upl_helper.checks.reference import ReferenceTables
from upl_helper.checks.registry import CheckContext
from upl_helper.checks.thresholds import Thresholds
from upl_helper.model import FIELD_NAMES, SOURCE_SHEET_COLUMN, ExtractionContext

VERIFIED_REFERENCE = ReferenceTables(
    verified=True,
    ssa_state_codes={"14": "IL", "45": "TX"},
    facility_type_ranges={"inpatient_hospital": [(1, 879), (3300, 3399)]},
    source="test",
)


def make_context(
    records: list[dict[str, Any]],
    thresholds: Thresholds | None = None,
    reference: ReferenceTables | None = None,
    context: ExtractionContext | None = None,
    sheet: str = "Demo",
) -> CheckContext:
    frame = pd.DataFrame(records)
    for name in FIELD_NAMES:
        if name not in frame.columns:
            frame[name] = None
    frame[SOURCE_SHEET_COLUMN] = sheet
    frame = frame[[*FIELD_NAMES, SOURCE_SHEET_COLUMN]].reset_index(drop=True)

    provenance = pd.DataFrame(
        [
            {
                name: f"{sheet}!{chr(65 + i)}{row + 2}"
                for i, name in enumerate(FIELD_NAMES)
            }
            for row in range(len(frame))
        ],
        columns=list(FIELD_NAMES),
    )

    return CheckContext(
        frame=frame,
        provenance=provenance,
        thresholds=thresholds or Thresholds(),
        reference=reference or ReferenceTables(),
        context=context,
    )


def provider(**overrides: Any) -> dict[str, Any]:
    """A plausible, internally consistent provider row."""
    record = {
        "provider_name": "Example Hospital",
        "ccn": "140001",
        "ownership_category": "private",
        "medicaid_days": 1000.0,
        "medicaid_charges": 1_000_000.0,
        "cost_to_charge_ratio": 0.40,
        "medicaid_cost": 400_000.0,
        "upl_amount": 500_000.0,
        "medicaid_payments_base": 300_000.0,
        "medicaid_trend_factor": 1.0,
        "medicaid_other_adjustment_factor": 1.0,
        "medicaid_payments_supplemental": 100_000.0,
        "medicaid_payments_total": 400_000.0,
        "upl_gap": 100_000.0,
    }
    record.update(overrides)
    return record


def ids(findings: list[Any]) -> list[str]:
    return [f.check_id for f in findings]
