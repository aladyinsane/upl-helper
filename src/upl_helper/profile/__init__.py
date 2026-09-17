"""Template profiling: describe a workbook's structure without its data.

See SPEC-0002. The descriptor carries no cell values except header text and
formula strings.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from upl_helper.cli import register_command
from upl_helper.profile.emit import render, write_descriptor
from upl_helper.profile.loader import load_workbook_structure
from upl_helper.profile.models import ProfileOptions, WorkbookDescriptor
from upl_helper.profile.profiler import profile_workbook

__all__ = [
    "ProfileOptions",
    "WorkbookDescriptor",
    "load_workbook_structure",
    "profile_path",
    "profile_workbook",
    "render",
    "write_descriptor",
]


def profile_path(
    workbook_path: str | Path,
    strict: bool = False,
    header_row: list[int] | None = None,
    sheet_names: list[str] | None = None,
) -> WorkbookDescriptor:
    """Profile a workbook from a path. The convenience entry point."""
    loaded = load_workbook_structure(workbook_path)
    options = ProfileOptions(strict=strict, header_row_override=header_row)
    return profile_workbook(loaded, options, sheet_names=sheet_names)


def _parse_header_rows(value: str | None) -> list[int] | None:
    if not value:
        return None
    try:
        rows = [int(part) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--header-row expects one or more row numbers, got {value!r}"
        ) from exc
    return rows or None


def _run(args: argparse.Namespace) -> int:
    descriptor = profile_path(
        args.workbook,
        strict=args.strict,
        header_row=_parse_header_rows(args.header_row),
        sheet_names=args.sheet or None,
    )
    output = args.output or Path(args.workbook).with_suffix("").with_name(
        f"{Path(args.workbook).stem}.descriptor.{args.format}"
    )
    write_descriptor(descriptor, output, args.format)
    sheets = len(descriptor.sheets)
    columns = sum(len(s.columns) for s in descriptor.sheets)
    print(f"profiled {sheets} sheet(s), {columns} column(s) -> {output}")
    return 0


@register_command("profile", "Describe a workbook's structure without its data.")
def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("workbook", help="workbook to profile (.xlsx or .xlsm)")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="output path (default: <stem>.descriptor.<fmt>)",
    )
    parser.add_argument("--format", choices=["yaml", "json"], default="yaml")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="also drop data validation formulas, which can carry literal pick lists",
    )
    parser.add_argument(
        "--header-row",
        default=None,
        help="override header detection; one row number or a comma-separated list",
    )
    parser.add_argument(
        "--sheet",
        action="append",
        default=[],
        help="profile only this sheet; repeatable",
    )
    parser.set_defaults(func=_run)
