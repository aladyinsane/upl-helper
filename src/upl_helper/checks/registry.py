"""The check registry and runner."""

from __future__ import annotations

import datetime as dt
import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from upl_helper.checks.findings import (
    Finding,
    Scope,
    Severity,
    WaivedFinding,
    WaiverSet,
    apply_waivers,
)
from upl_helper.checks.reference import ReferenceTables
from upl_helper.checks.thresholds import Thresholds


class Skip(Exception):
    """Raised by a check that cannot run. Carries the reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class CheckContext:
    frame: pd.DataFrame
    provenance: pd.DataFrame
    thresholds: Thresholds
    reference: ReferenceTables
    extraction_report: Any = None
    context: Any = None

    def cell(self, row: int, field_name: str) -> str | None:
        """The workbook cell a value came from, if it is known."""
        if (
            field_name not in self.provenance.columns
            or row not in self.provenance.index
        ):
            return None
        value = self.provenance.loc[row, field_name]
        return None if pd.isna(value) else str(value)

    def subject(self, row: int) -> str:
        value = self.frame.loc[row, "ccn"]
        if value is None or pd.isna(value):
            name = self.frame.loc[row, "provider_name"]
            return f"row{row}" if pd.isna(name) else str(name)
        return str(value)

    def require_fields(self, *names: str) -> None:
        """Skip the whole check when a field the workbook never supplied is needed."""
        missing = [
            n
            for n in names
            if n not in self.frame.columns or self.frame[n].isna().all()
        ]
        if missing:
            raise Skip(f"no data for: {', '.join(missing)}")


CheckFunction = Callable[[CheckContext], Iterable[Finding]]


@dataclass
class CheckSpec:
    check_id: str
    family: str
    title: str
    severity: Severity
    func: CheckFunction


@dataclass
class CheckResult:
    check_id: str
    status: str
    findings: list[Finding] = field(default_factory=list)
    skip_reason: str | None = None
    rows_evaluated: int = 0
    rows_not_evaluated: int = 0
    error: str | None = None


@dataclass
class RunResult:
    results: list[CheckResult]
    findings: list[Finding]
    waived: list[WaivedFinding]
    expired_waivers: list[Finding]

    @property
    def counts(self) -> dict[str, int]:
        return {
            "error": sum(1 for f in self.findings if f.severity is Severity.ERROR),
            "warn": sum(1 for f in self.findings if f.severity is Severity.WARN),
            "info": sum(1 for f in self.findings if f.severity is Severity.INFO),
            "waived": len(self.waived),
            "skipped": sum(1 for r in self.results if r.status == "skipped"),
            "failed": sum(1 for r in self.results if r.status == "failed"),
        }

    @property
    def has_blocking_errors(self) -> bool:
        return self.counts["error"] > 0


REGISTRY: dict[str, CheckSpec] = {}


def check(
    check_id: str, family: str, title: str, severity: Severity
) -> Callable[[CheckFunction], CheckFunction]:
    def decorator(func: CheckFunction) -> CheckFunction:
        if check_id in REGISTRY:
            raise ValueError(f"duplicate check id {check_id!r}")
        REGISTRY[check_id] = CheckSpec(check_id, family, title, severity, func)
        return func

    return decorator


def run_checks(
    ctx: CheckContext,
    waivers: WaiverSet | None = None,
    families: Iterable[str] | None = None,
    today: dt.date | None = None,
) -> RunResult:
    wanted = {f.upper() for f in families} if families else None
    results: list[CheckResult] = []
    all_findings: list[Finding] = []

    for check_id in sorted(REGISTRY):
        spec = REGISTRY[check_id]
        if wanted and spec.family.upper() not in wanted:
            continue

        try:
            findings = list(spec.func(ctx))
        except Skip as skip:
            results.append(
                CheckResult(
                    check_id=check_id, status="skipped", skip_reason=skip.reason
                )
            )
            continue
        except Exception:
            # One broken check must not take the run down with it.
            results.append(
                CheckResult(
                    check_id=check_id,
                    status="failed",
                    error=traceback.format_exc(limit=3),
                )
            )
            all_findings.append(
                Finding(
                    check_id=check_id,
                    severity=Severity.ERROR,
                    scope=Scope.RUN,
                    message=f"check {check_id} raised an exception and did not run",
                )
            )
            continue

        results.append(CheckResult(check_id=check_id, status="ran", findings=findings))
        all_findings.extend(findings)

    unwaived, waived, expired = apply_waivers(
        all_findings, waivers or WaiverSet(), today
    )
    return RunResult(
        results=results,
        findings=unwaived + expired,
        waived=waived,
        expired_waivers=expired,
    )
