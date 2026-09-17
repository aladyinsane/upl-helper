"""Assembling a workbook descriptor."""

from __future__ import annotations

import datetime as dt
from typing import Any

from upl_helper import __version__
from upl_helper.profile.columns import profile_columns
from upl_helper.profile.headers import detect_header_rows, select_header_rows
from upl_helper.profile.loader import LoadedWorkbook
from upl_helper.profile.models import (
    DESCRIPTOR_VERSION,
    DataValidationInfo,
    DefinedNameInfo,
    Dimensions,
    HeaderInfo,
    ProfileOptions,
    SheetDescriptor,
    SheetProtectionInfo,
    SourceInfo,
    WorkbookDescriptor,
    WorkbookInfo,
    WorkbookProperties,
    WorkbookProtectionInfo,
)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _sheet_protection(worksheet: Any) -> SheetProtectionInfo:
    protection = getattr(worksheet, "protection", None)
    if protection is None:
        return SheetProtectionInfo(False, False, False)
    password = getattr(protection, "password", None) or getattr(
        protection, "algorithmName", None
    )
    return SheetProtectionInfo(
        enabled=bool(getattr(protection, "sheet", False)),
        password_hash_present=password is not None,
        selection_locked=bool(getattr(protection, "selectLockedCells", False)),
    )


def _workbook_protection(workbook: Any) -> WorkbookProtectionInfo:
    security = getattr(workbook, "security", None)
    if security is None:
        return WorkbookProtectionInfo(False, False, False)
    lock_structure = bool(getattr(security, "lockStructure", False))
    lock_windows = bool(getattr(security, "lockWindows", False))
    has_password = getattr(security, "workbookPassword", None) is not None
    return WorkbookProtectionInfo(
        workbook_locked=lock_structure or lock_windows or has_password,
        lock_structure=lock_structure,
        lock_windows=lock_windows,
    )


def _defined_names(workbook: Any) -> list[DefinedNameInfo]:
    names: list[DefinedNameInfo] = []
    for name, defn in getattr(workbook, "defined_names", {}).items():
        names.append(
            DefinedNameInfo(
                name=name, scope=None, refers_to=str(getattr(defn, "value", ""))
            )
        )
    for worksheet in workbook.worksheets:
        for name, defn in getattr(worksheet, "defined_names", {}).items():
            names.append(
                DefinedNameInfo(
                    name=name,
                    scope=worksheet.title,
                    refers_to=str(getattr(defn, "value", "")),
                )
            )
    names.sort(key=lambda n: (n.scope or "", n.name))
    return names


def _data_validations(worksheet: Any, strict: bool) -> list[DataValidationInfo]:
    container = getattr(worksheet, "data_validations", None)
    if container is None:
        return []
    out: list[DataValidationInfo] = []
    for validation in getattr(container, "dataValidation", []):
        out.append(
            DataValidationInfo(
                range=str(validation.sqref),
                type=validation.type,
                # A pick list can carry literal values. They are template
                # metadata in every case we expect, but --strict drops them
                # so a reviewer does not have to take that on trust.
                formula1=None if strict else validation.formula1,
            )
        )
    out.sort(key=lambda d: d.range)
    return out


def _nonempty_row_count(worksheet: Any) -> int:
    count = 0
    for row in worksheet.iter_rows(values_only=True):
        if any(v is not None and str(v).strip() != "" for v in row):
            count += 1
    return count


def profile_sheet(
    worksheet: Any, index: int, options: ProfileOptions
) -> SheetDescriptor:
    candidates = detect_header_rows(worksheet)
    header_rows = select_header_rows(candidates, options.header_row_override)

    return SheetDescriptor(
        name=worksheet.title,
        index=index,
        state=worksheet.sheet_state,
        dimensions=Dimensions(
            min_row=worksheet.min_row or 0,
            max_row=worksheet.max_row or 0,
            min_col=worksheet.min_column or 0,
            max_col=worksheet.max_column or 0,
        ),
        freeze_panes=worksheet.freeze_panes,
        protection=_sheet_protection(worksheet),
        merged_ranges=sorted(str(r) for r in worksheet.merged_cells.ranges),
        data_validations=_data_validations(worksheet, options.strict),
        conditional_formatting_ranges=sorted(
            str(cf.sqref) for cf in worksheet.conditional_formatting
        ),
        nonempty_row_count=_nonempty_row_count(worksheet),
        header=HeaderInfo(
            rows=header_rows, detected=bool(header_rows), candidates=candidates
        ),
        columns=profile_columns(worksheet, header_rows),
    )


def profile_workbook(
    loaded: LoadedWorkbook,
    options: ProfileOptions | None = None,
    sheet_names: list[str] | None = None,
    now: dt.datetime | None = None,
) -> WorkbookDescriptor:
    options = options or ProfileOptions()
    workbook = loaded.workbook
    timestamp = now or dt.datetime.now(dt.UTC)

    # workbook.worksheets omits chartsheets; _sheets carries every sheet, and
    # a hidden sheet is exactly the kind of thing we must not skip.
    sheets = []
    for index, worksheet in enumerate(workbook.worksheets):
        if sheet_names and worksheet.title not in sheet_names:
            continue
        sheets.append(profile_sheet(worksheet, index, options))

    properties = workbook.properties
    return WorkbookDescriptor(
        descriptor_version=DESCRIPTOR_VERSION,
        source=SourceInfo(
            filename=loaded.path.name,
            sha256=loaded.sha256,
            size_bytes=loaded.size_bytes,
            profiled_at=timestamp.replace(microsecond=0).isoformat(),
            profiler_version=__version__,
        ),
        options=options,
        workbook=WorkbookInfo(
            properties=WorkbookProperties(
                creator=getattr(properties, "creator", None),
                title=getattr(properties, "title", None),
                created=_iso(getattr(properties, "created", None)),
                modified=_iso(getattr(properties, "modified", None)),
            ),
            protection=_workbook_protection(workbook),
            defined_names=_defined_names(workbook),
            sheet_count=len(workbook.worksheets),
        ),
        sheets=sheets,
    )
