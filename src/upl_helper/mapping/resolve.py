"""Matching a mapping against an actual workbook.

Sheets are matched by name or regex; columns by normalized header text. Neither
is ever matched by position.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from upl_helper.mapping.models import MappingError, SheetRule, TemplateMapping
from upl_helper.profile.headers import detect_and_select
from upl_helper.profile.text import normalize_header

HEADER_JOIN = " / "


@dataclass
class ColumnResolution:
    columns: dict[str, int] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    unmapped_columns: list[str] = field(default_factory=list)


@dataclass
class ResolvedSheet:
    rule: SheetRule
    worksheet: Any
    header_rows: list[int]
    resolution: ColumnResolution

    @property
    def name(self) -> str:
        return self.worksheet.title


def sheet_headers(worksheet: Any, header_rows: list[int]) -> dict[int, str]:
    """Column index -> header text, joining multi-row headers top to bottom."""
    if not header_rows:
        return {}
    min_col = worksheet.min_column or 1
    max_col = worksheet.max_column or 1
    parts: dict[int, list[str]] = {col: [] for col in range(min_col, max_col + 1)}

    for row_index in sorted(header_rows):
        for col in range(min_col, max_col + 1):
            value = worksheet.cell(row=row_index, column=col).value
            if value is not None and str(value).strip():
                parts[col].append(str(value).strip())

    return {col: HEADER_JOIN.join(bits) for col, bits in parts.items() if bits}


def resolve_columns(headers: dict[int, str], rule: SheetRule) -> ColumnResolution:
    """Resolve each field to exactly one column, or fail loudly."""
    normalized_headers = {col: normalize_header(text) for col, text in headers.items()}
    resolution = ColumnResolution()
    claimed: set[int] = set()

    for name, field_rule in rule.fields.items():
        wanted = {normalize_header(alias) for alias in field_rule.aliases}
        wanted.discard(None)
        matches = [
            col
            for col, normalized in normalized_headers.items()
            if normalized in wanted
        ]

        if len(matches) > 1:
            columns = ", ".join(f"{headers[c]!r} (column {c})" for c in sorted(matches))
            raise MappingError(
                f"sheet {rule.label!r}: field {name!r} matches more than one "
                f"column: {columns}. Narrow the aliases; the extractor will not "
                "guess between them."
            )
        if not matches:
            if field_rule.required:
                aliases = ", ".join(repr(a) for a in field_rule.aliases)
                raise MappingError(
                    f"sheet {rule.label!r}: required field {name!r} matched no "
                    f"column. Tried: {aliases}."
                )
            resolution.missing_fields.append(name)
            continue

        resolution.columns[name] = matches[0]
        claimed.add(matches[0])

    resolution.unmapped_columns = [
        headers[col] for col in sorted(headers) if col not in claimed
    ]
    resolution.missing_fields.sort()
    return resolution


def _sheet_matches(rule: SheetRule, title: str) -> bool:
    if rule.name_equals is not None:
        return title == rule.name_equals
    return re.search(rule.name_matches or "", title) is not None


def resolve_sheets(
    workbook: Any, mapping: TemplateMapping
) -> tuple[list[ResolvedSheet], list[str], list[str]]:
    """Returns (resolved sheets, unmapped sheet names, unmatched rule labels)."""
    resolved: list[ResolvedSheet] = []
    matched_titles: set[str] = set()
    unmatched_rules: list[str] = []

    for rule in mapping.sheets:
        candidates = [
            ws for ws in workbook.worksheets if _sheet_matches(rule, ws.title)
        ]
        if not candidates:
            if rule.required:
                raise MappingError(
                    f"sheet rule {rule.label!r} is required but matched no sheet. "
                    f"Workbook has: {', '.join(ws.title for ws in workbook.worksheets)}"
                )
            unmatched_rules.append(rule.label)
            continue

        for worksheet in candidates:
            matched_titles.add(worksheet.title)
            if rule.role == "ignore":
                continue
            header_rows, _ = detect_and_select(worksheet, rule.header_rows)
            headers = sheet_headers(worksheet, header_rows)
            resolved.append(
                ResolvedSheet(
                    rule=rule,
                    worksheet=worksheet,
                    header_rows=header_rows,
                    resolution=resolve_columns(headers, rule),
                )
            )

    unmapped = [
        ws.title for ws in workbook.worksheets if ws.title not in matched_titles
    ]
    return resolved, unmapped, unmatched_rules
