"""Remove worksheet and workbook protection from a copy of a workbook.

This works on the xlsx zip directly rather than through openpyxl, because
openpyxl does not round-trip charts, images, pivot tables or VBA, and CMS
templates contain several of those. Every zip entry is copied byte for byte
except the workbook and worksheet XML parts, which are edited in place.

No password is needed. Worksheet protection in OOXML is an advisory flag plus
an optional password hash. Removing the element removes the protection; the
hash is never read.
"""

from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from upl_helper.cli import register_command
from upl_helper.errors import UnsupportedWorkbookError
from upl_helper.profile.loader import file_sha256

_SHEET_PROTECTION = re.compile(rb"<sheetProtection\b[^>]*/>")
_WORKBOOK_PROTECTION = re.compile(rb"<workbookProtection\b[^>]*/>")
_FILE_SHARING = re.compile(rb"<fileSharing\b[^>]*/>")
_SHEET_STATE = re.compile(rb'\s+state="(?:hidden|veryHidden)"')
_COL_HIDDEN = re.compile(rb'(<col\b[^>]*?)\s+hidden="(?:1|true)"')
_ROW_HIDDEN = re.compile(rb'(<row\b[^>]*?)\s+hidden="(?:1|true)"')
_SHEET_ELEMENT = re.compile(rb"<sheet\b[^>]*/>")
_ATTR = re.compile(rb'(\w+(?::\w+)?)="([^"]*)"')

WORKSHEET_PREFIX = "xl/worksheets/"
WORKBOOK_PART = "xl/workbook.xml"
WORKBOOK_RELS = "xl/_rels/workbook.xml.rels"


@dataclass
class UnprotectReport:
    source: dict[str, str]
    output: dict[str, str]
    removed_workbook_protection: bool = False
    removed_sheet_protection: list[str] = field(default_factory=list)
    unhidden_sheets: list[str] = field(default_factory=list)
    unhidden_columns: dict[str, int] = field(default_factory=dict)
    unhidden_rows: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"source: {self.source['filename']}",
            f"output: {self.output['filename']}",
            f"workbook protection removed: {self.removed_workbook_protection}",
            f"sheets unprotected: {len(self.removed_sheet_protection)}",
        ]
        for name in self.removed_sheet_protection:
            lines.append(f"  - {name}")
        if self.unhidden_sheets:
            lines.append(f"sheets unhidden: {', '.join(self.unhidden_sheets)}")
        if self.unhidden_columns:
            detail = ", ".join(f"{k}: {v}" for k, v in self.unhidden_columns.items())
            lines.append(f"column groups unhidden: {detail}")
        if self.unhidden_rows:
            detail = ", ".join(f"{k}: {v}" for k, v in self.unhidden_rows.items())
            lines.append(f"row groups unhidden: {detail}")
        lines.extend(f"warning: {w}" for w in self.warnings)
        return "\n".join(lines)


def _attrs(element: bytes) -> dict[bytes, bytes]:
    return dict(_ATTR.findall(element))


def _sheet_part_names(archive: zipfile.ZipFile) -> dict[str, str]:
    """Map worksheet part name -> sheet display name.

    Falls back to the part's own filename when the relationship cannot be
    resolved, so the report is always populated with something recognizable.
    """
    try:
        workbook_xml = archive.read(WORKBOOK_PART)
        rels_xml = archive.read(WORKBOOK_RELS)
    except KeyError:
        return {}

    rel_targets: dict[bytes, bytes] = {}
    for element in re.findall(rb"<Relationship\b[^>]*/>", rels_xml):
        attrs = _attrs(element)
        if b"Id" in attrs and b"Target" in attrs:
            rel_targets[attrs[b"Id"]] = attrs[b"Target"]

    mapping: dict[str, str] = {}
    for element in _SHEET_ELEMENT.findall(workbook_xml):
        attrs = _attrs(element)
        name = attrs.get(b"name")
        rel_id = attrs.get(b"r:id") or attrs.get(b"id")
        if name is None or rel_id is None:
            continue
        target = rel_targets.get(rel_id)
        if target is None:
            continue
        part = target.decode("utf-8").lstrip("/")
        if not part.startswith("xl/"):
            part = "xl/" + part
        mapping[part] = name.decode("utf-8")
    return mapping


def _strip_workbook(data: bytes, unhide: bool) -> tuple[bytes, bool, list[str]]:
    unhidden: list[str] = []
    new_data, count = _WORKBOOK_PROTECTION.subn(b"", data)
    new_data = _FILE_SHARING.sub(b"", new_data)

    if unhide:

        def unhide_sheet(match: re.Match[bytes]) -> bytes:
            element = match.group(0)
            if _SHEET_STATE.search(element):
                attrs = _attrs(element)
                if b"name" in attrs:
                    unhidden.append(attrs[b"name"].decode("utf-8"))
                return _SHEET_STATE.sub(b"", element)
            return element

        new_data = _SHEET_ELEMENT.sub(unhide_sheet, new_data)

    return new_data, bool(count), unhidden


def _strip_worksheet(data: bytes, unhide: bool) -> tuple[bytes, bool, int, int]:
    new_data, protection_count = _SHEET_PROTECTION.subn(b"", data)
    cols = rows = 0
    if unhide:
        new_data, cols = _COL_HIDDEN.subn(rb"\1", new_data)
        new_data, rows = _ROW_HIDDEN.subn(rb"\1", new_data)
    return new_data, bool(protection_count), cols, rows


def unprotect_workbook(
    src: str | Path, dst: str | Path | None = None, unhide: bool = False
) -> UnprotectReport:
    src = Path(src)
    if not src.exists():
        raise UnsupportedWorkbookError(f"{src}: no such file")
    if not zipfile.is_zipfile(src):
        raise UnsupportedWorkbookError(
            f"{src}: not a readable .xlsx/.xlsm file (it is not a zip archive). "
            "Legacy .xls workbooks are not supported; re-save as .xlsx first."
        )

    if dst is None:
        dst = src.with_name(f"{src.stem}.unprotected{src.suffix}")
    dst = Path(dst)
    if dst.resolve() == src.resolve():
        raise UnsupportedWorkbookError(
            f"{src}: refusing to write over the input file; choose another -o path"
        )

    report = UnprotectReport(
        source={"filename": src.name, "sha256": file_sha256(src)},
        output={"filename": dst.name, "sha256": ""},
    )

    with zipfile.ZipFile(src) as source_zip:
        sheet_names = _sheet_part_names(source_zip)
        tmp = dst.with_suffix(dst.suffix + ".partial")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out_zip:
            for info in source_zip.infolist():
                data = source_zip.read(info.filename)

                if info.filename == WORKBOOK_PART:
                    data, removed, unhidden = _strip_workbook(data, unhide)
                    report.removed_workbook_protection = removed
                    report.unhidden_sheets.extend(unhidden)
                elif info.filename.startswith(WORKSHEET_PREFIX) and (
                    info.filename.endswith(".xml")
                ):
                    name = sheet_names.get(info.filename, info.filename)
                    data, removed, cols, rows = _strip_worksheet(data, unhide)
                    if removed:
                        report.removed_sheet_protection.append(name)
                    if cols:
                        report.unhidden_columns[name] = cols
                    if rows:
                        report.unhidden_rows[name] = rows

                # Preserve each entry's own compression rather than forcing one.
                new_info = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                new_info.compress_type = info.compress_type
                new_info.external_attr = info.external_attr
                new_info.internal_attr = info.internal_attr
                new_info.create_system = info.create_system
                out_zip.writestr(new_info, data)

        shutil.move(str(tmp), str(dst))

    report.removed_sheet_protection.sort()
    report.unhidden_sheets.sort()
    report.output["sha256"] = file_sha256(dst)
    return report


def _run(args: argparse.Namespace) -> int:
    report = unprotect_workbook(args.workbook, args.output, unhide=args.unhide)
    print(report.summary())
    if args.report:
        import dataclasses

        import yaml

        Path(args.report).write_text(
            yaml.safe_dump(dataclasses.asdict(report), sort_keys=True),
            encoding="utf-8",
        )
    return 0


@register_command("unprotect", "Write an unprotected copy of a workbook.")
def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("workbook", help="workbook to copy and unprotect")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="output path (default: <stem>.unprotected<ext>)",
    )
    parser.add_argument(
        "--unhide",
        action="store_true",
        help="also make hidden sheets, columns and rows visible",
    )
    parser.add_argument("--report", default=None, help="write the report to this path")
    parser.set_defaults(func=_run)
