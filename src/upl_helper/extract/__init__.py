"""Extraction: workbook plus mapping -> canonical frame.

See SPEC-0003.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from upl_helper.cli import register_command
from upl_helper.extract.extractor import Extraction, extract, extract_path
from upl_helper.mapping.loader import load_mapping
from upl_helper.model import ExtractionContext

__all__ = ["Extraction", "ExtractionContext", "extract", "extract_path"]


def _run(args: argparse.Namespace) -> int:
    mapping = load_mapping(args.mapping)
    context = None
    if args.state and args.year:
        context = ExtractionContext(
            state=args.state,
            provider_type=mapping.template.provider_type,
            demonstration_year=args.year,
        )

    extraction = extract_path(args.workbook, mapping, context)

    if not mapping.template.verified_against_real_template:
        print(
            "warning: this mapping is not verified against a real CMS template; "
            "treat the output as a smoke test, not a reading of a demonstration"
        )

    print(extraction.report.summary())

    if args.output:
        out = Path(args.output)
        if out.suffix.lower() == ".parquet":
            extraction.frame.to_parquet(out, index=False)
        else:
            extraction.frame.to_csv(out, index=False)
        print(f"wrote {len(extraction.frame)} row(s) -> {out}")
    return 0


@register_command("extract", "Read a mapped workbook into the canonical model.")
def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("workbook", help="workbook to extract")
    parser.add_argument("-m", "--mapping", required=True, help="template mapping YAML")
    parser.add_argument(
        "-o", "--output", default=None, help="write the frame (.csv or .parquet)"
    )
    parser.add_argument("--state", default=None, help="two-letter state code")
    parser.add_argument("--year", type=int, default=None, help="demonstration year")
    parser.set_defaults(func=_run)
