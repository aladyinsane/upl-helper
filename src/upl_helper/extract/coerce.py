"""Turning spreadsheet cell values into typed values.

The rule throughout: a value that cannot be parsed becomes null **and**
produces an issue. Silently nulling a malformed number hides exactly the kind
of defect this project exists to find.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from upl_helper.model import Dtype, Ownership
from upl_helper.profile.text import normalize_header

_CURRENCY = re.compile(r"^[\s$€£]+|[\s]+$")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}\b)")
_PARENTHESIZED = re.compile(r"^\((.*)\)$")


@dataclass(frozen=True)
class CoercionIssue:
    field: str
    dtype: str
    raw: str
    message: str


def _is_blank(raw: object) -> bool:
    return raw is None or (isinstance(raw, str) and raw.strip() == "")


def _parse_number(text: str) -> tuple[float | None, str | None]:
    cleaned = _CURRENCY.sub("", text.strip())
    negative = False

    match = _PARENTHESIZED.match(cleaned)
    if match:
        # Accounting negatives: (1,234.56) means -1234.56
        negative = True
        cleaned = match.group(1).strip()

    cleaned = _CURRENCY.sub("", cleaned)
    cleaned = _THOUSANDS.sub("", cleaned)
    if cleaned.startswith("-"):
        negative = not negative
        cleaned = cleaned[1:].strip()

    if cleaned in {"", "-", "."}:
        return None, "empty after cleaning"
    try:
        value = float(cleaned)
    except ValueError:
        return None, "not numeric"
    return (-value if negative else value), None


def coerce_value(
    raw: object, dtype: Dtype, field_name: str = ""
) -> tuple[object | None, CoercionIssue | None]:
    """Coerce one cell. Returns ``(value, issue)``; at most one is non-null."""
    if _is_blank(raw):
        return None, None

    if dtype is Dtype.STRING:
        if isinstance(raw, float) and raw.is_integer():
            # Excel hands back 14001.0 for a CCN typed as a number. Rendering
            # it as "14001.0" would be worse than useless downstream.
            return str(int(raw)), None
        return str(raw).strip(), None

    if dtype is Dtype.DATE:
        if isinstance(raw, dt.datetime):
            return raw.date(), None
        if isinstance(raw, dt.date):
            return raw, None
        text = str(raw).strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%Y", "%Y%m%d"):
            try:
                return dt.datetime.strptime(text, fmt).date(), None
            except ValueError:
                continue
        return None, CoercionIssue(field_name, dtype, text, "unrecognized date format")

    if isinstance(raw, bool):
        return None, CoercionIssue(
            field_name, dtype, str(raw), "boolean in a numeric field"
        )

    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip()
        percent = dtype is Dtype.RATIO and text.endswith("%")
        if percent:
            text = text[:-1]
        parsed, problem = _parse_number(text)
        if parsed is None:
            return None, CoercionIssue(
                field_name, dtype, str(raw), problem or "not numeric"
            )
        value = parsed / 100.0 if percent else parsed

    if dtype is Dtype.INTEGER:
        if abs(value - round(value)) > 1e-9:
            return None, CoercionIssue(
                field_name, dtype, str(raw), "expected a whole number"
            )
        return round(value), None

    return value, None


def coerce_ownership(
    raw: object, values: dict[str, list[str]]
) -> tuple[str, CoercionIssue | None]:
    """Map a workbook ownership label onto a canonical category."""
    if _is_blank(raw):
        return Ownership.UNKNOWN.value, CoercionIssue(
            "ownership_category", "string", "", "blank ownership category"
        )

    normalized = normalize_header(str(raw))
    for canonical, aliases in values.items():
        for alias in aliases:
            if normalize_header(alias) == normalized:
                return canonical, None

    # A label we do not recognize is reported rather than guessed at: ownership
    # decides which UPL group a provider belongs to.
    return Ownership.UNKNOWN.value, CoercionIssue(
        "ownership_category",
        "string",
        str(raw),
        "unrecognized ownership category",
    )
