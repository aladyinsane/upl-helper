"""Findings, fingerprints and waivers.

A check never prints. It yields findings, and the reporting layer renders them.
That separation is what makes waivers, JSON output and annotated workbooks
possible without every check knowing about any of them.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from upl_helper.errors import UplHelperError

WAIVER_EXPIRED_CHECK_ID = "WAIVER_EXPIRED"


class WaiverError(UplHelperError):
    """The waiver file is invalid."""


class Severity(StrEnum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


class Scope(StrEnum):
    RUN = "run"
    SHEET = "sheet"
    PROVIDER = "provider"
    CELL = "cell"


@dataclass
class Finding:
    check_id: str
    severity: Severity
    scope: Scope
    message: str
    subject: str = ""
    field: str | None = None
    observed: Any = None
    expected: Any = None
    cell: str | None = None

    @property
    def fingerprint(self) -> str:
        """Stable across runs, and across changes in the observed value.

        The observed value is deliberately excluded. A waiver that expires the
        moment next year's number moves by a dollar is not a waiver.
        """
        key = f"{self.check_id}|{self.subject}|{self.field or ''}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["severity"] = str(self.severity)
        payload["scope"] = str(self.scope)
        payload["fingerprint"] = self.fingerprint
        return payload


@dataclass
class Waiver:
    reason: str
    expires: dt.date
    fingerprint: str | None = None
    check_id: str | None = None
    subject: str | None = None

    def matches(self, finding: Finding) -> bool:
        if self.fingerprint:
            return self.fingerprint == finding.fingerprint
        if self.check_id and self.check_id == finding.check_id:
            return self.subject is None or self.subject == finding.subject
        return False

    def is_expired(self, today: dt.date) -> bool:
        return self.expires < today


@dataclass
class WaivedFinding:
    finding: Finding
    waiver: Waiver


@dataclass
class WaiverSet:
    waivers: list[Waiver] = field(default_factory=list)

    def find(self, finding: Finding) -> Waiver | None:
        for waiver in self.waivers:
            if waiver.matches(finding):
                return waiver
        return None


def _parse_waiver(raw: dict[str, Any], index: int) -> Waiver:
    where = f"waivers[{index}]"

    reason = str(raw.get("reason") or "").strip()
    if not reason:
        raise WaiverError(
            f"{where}: 'reason' is required and must not be empty. A waiver "
            "without a stated reason is a silent suppression."
        )

    if "expires" not in raw or raw["expires"] is None:
        raise WaiverError(
            f"{where}: 'expires' is required. A waiver file is where real "
            "problems go to be forgotten; a date forces the question back."
        )
    expires = raw["expires"]
    if isinstance(expires, dt.datetime):
        expires = expires.date()
    elif isinstance(expires, str):
        try:
            expires = dt.date.fromisoformat(expires)
        except ValueError as exc:
            raise WaiverError(f"{where}.expires: {expires!r} is not a date") from exc
    elif not isinstance(expires, dt.date):
        raise WaiverError(f"{where}.expires: {expires!r} is not a date")

    fingerprint = raw.get("fingerprint")
    check_id = raw.get("check_id")
    if not fingerprint and not check_id:
        raise WaiverError(f"{where}: set either 'fingerprint' or 'check_id'")

    return Waiver(
        reason=reason,
        expires=expires,
        fingerprint=str(fingerprint) if fingerprint else None,
        check_id=str(check_id) if check_id else None,
        subject=str(raw["subject"]) if raw.get("subject") is not None else None,
    )


def load_waivers(path: str | Path | None) -> WaiverSet:
    if path is None:
        return WaiverSet()
    path = Path(path)
    if not path.exists():
        raise WaiverError(f"{path}: no such waiver file")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_waivers = payload.get("waivers") or []
    if not isinstance(raw_waivers, list):
        raise WaiverError(f"{path}: 'waivers' must be a list")
    return WaiverSet([_parse_waiver(raw, i) for i, raw in enumerate(raw_waivers)])


def apply_waivers(
    findings: list[Finding], waivers: WaiverSet, today: dt.date | None = None
) -> tuple[list[Finding], list[WaivedFinding], list[Finding]]:
    """Split findings into (unwaived, waived, expired-waiver notices)."""
    today = today or dt.date.today()
    unwaived: list[Finding] = []
    waived: list[WaivedFinding] = []
    expired: list[Finding] = []

    for finding in findings:
        waiver = waivers.find(finding)
        if waiver is None:
            unwaived.append(finding)
            continue
        if waiver.is_expired(today):
            # An expired waiver does not suppress. It surfaces the finding and
            # says why it is back.
            unwaived.append(finding)
            expired.append(
                Finding(
                    check_id=WAIVER_EXPIRED_CHECK_ID,
                    severity=Severity.WARN,
                    scope=Scope.RUN,
                    subject=finding.subject,
                    message=(
                        f"waiver for {finding.check_id} expired on "
                        f"{waiver.expires.isoformat()}: {waiver.reason}"
                    ),
                )
            )
            continue
        waived.append(WaivedFinding(finding=finding, waiver=waiver))

    return unwaived, waived, expired
