"""Rendering a run result."""

from __future__ import annotations

import json
from typing import Any

from upl_helper.checks.findings import Severity
from upl_helper.checks.registry import RunResult

_ORDER = {Severity.ERROR: 0, Severity.WARN: 1, Severity.INFO: 2}
_LABEL = {Severity.ERROR: "ERROR", Severity.WARN: "WARN ", Severity.INFO: "INFO "}


def render_text(result: RunResult, show_skipped: bool = True) -> str:
    lines: list[str] = []
    counts = result.counts

    findings = sorted(
        result.findings, key=lambda f: (_ORDER[f.severity], f.check_id, f.subject)
    )
    for finding in findings:
        location = f" [{finding.cell}]" if finding.cell else ""
        subject = f" {finding.subject}" if finding.subject else ""
        lines.append(
            f"{_LABEL[finding.severity]} {finding.check_id}{subject}: "
            f"{finding.message}{location}"
        )

    if show_skipped:
        skipped = [r for r in result.results if r.status == "skipped"]
        for skip in sorted(skipped, key=lambda r: r.check_id):
            lines.append(f"SKIP  {skip.check_id}: {skip.skip_reason}")

    for failed in [r for r in result.results if r.status == "failed"]:
        lines.append(f"BROKE {failed.check_id}: check raised an exception")

    if result.waived:
        lines.append("")
        lines.append(f"waived ({len(result.waived)}):")
        for waived in result.waived:
            lines.append(
                f"  {waived.finding.check_id} {waived.finding.subject}: "
                f"{waived.waiver.reason} (expires {waived.waiver.expires})"
            )

    ran = sum(1 for r in result.results if r.status == "ran")
    lines.append("")
    lines.append(
        f"{ran} check(s) ran, {counts['skipped']} skipped, {counts['failed']} broke | "
        f"{counts['error']} error, {counts['warn']} warn, {counts['info']} info, "
        f"{counts['waived']} waived"
    )
    return "\n".join(lines)


def render_json(result: RunResult) -> str:
    payload: dict[str, Any] = {
        "counts": result.counts,
        "findings": [f.to_dict() for f in result.findings],
        "waived": [
            {
                "finding": w.finding.to_dict(),
                "reason": w.waiver.reason,
                "expires": w.waiver.expires.isoformat(),
            }
            for w in result.waived
        ],
        "checks": [
            {
                "check_id": r.check_id,
                "status": r.status,
                "skip_reason": r.skip_reason,
                "findings": len(r.findings),
            }
            for r in result.results
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
