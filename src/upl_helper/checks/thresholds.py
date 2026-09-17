"""Tunable bounds.

Every bound lives here rather than in a check body. States differ, and a
threshold nobody can tune gets ignored instead of fixed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from upl_helper.errors import UplHelperError


class ThresholdError(UplHelperError):
    """The thresholds file is invalid."""


@dataclass
class Thresholds:
    money_abs_tol: float = 0.01
    ratio_abs_tol: float = 0.0005

    # Guessed. Real state data should set these. See SPEC-0004 open question 1.
    ccr_min: float = 0.05
    ccr_max: float = 1.20

    # Modified z-score above which a per-unit value is called an outlier.
    outlier_mad_threshold: float = 3.5
    outlier_min_rows: int = 8

    benford_min_rows: int = 50
    benford_max_abs_deviation: float = 0.08

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def load_thresholds(path: str | Path | None) -> Thresholds:
    if path is None:
        return Thresholds()
    path = Path(path)
    if not path.exists():
        raise ThresholdError(f"{path}: no such thresholds file")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    known = set(Thresholds().to_dict())
    unknown = set(payload) - known
    if unknown:
        raise ThresholdError(
            f"{path}: unknown threshold(s): {', '.join(sorted(unknown))}. "
            f"Known: {', '.join(sorted(known))}"
        )
    return Thresholds(**payload)
