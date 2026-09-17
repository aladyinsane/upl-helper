"""Reference tables for identifier checks.

These are small, static lookups, not the phase-4 reference data cache. They
carry a `verified` flag, and checks that depend on an unverified table skip
rather than producing findings from data nobody has confirmed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_TABLE_PATH = Path("config/reference/ccn-tables.yaml")


@dataclass
class ReferenceTables:
    verified: bool = False
    ssa_state_codes: dict[str, str] = field(default_factory=dict)
    facility_type_ranges: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    source: str | None = None

    def state_for_prefix(self, prefix: str) -> str | None:
        return self.ssa_state_codes.get(prefix)

    def ranges_for(self, provider_type: str) -> list[tuple[int, int]] | None:
        return self.facility_type_ranges.get(provider_type)


def load_reference_tables(path: str | Path | None = None) -> ReferenceTables:
    path = Path(path) if path is not None else DEFAULT_TABLE_PATH
    if not path.exists():
        return ReferenceTables(source=str(path))
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ReferenceTables(
        verified=bool(payload.get("verified", False)),
        ssa_state_codes={
            str(k): str(v) for k, v in (payload.get("ssa_state_codes") or {}).items()
        },
        facility_type_ranges={
            str(k): [(int(lo), int(hi)) for lo, hi in v]
            for k, v in (payload.get("facility_type_ranges") or {}).items()
        },
        source=str(path),
    )
