"""The check suite. See SPEC-0004."""

from __future__ import annotations

import argparse
from pathlib import Path

from upl_helper.checks.findings import (
    Finding,
    Scope,
    Severity,
    WaiverSet,
    apply_waivers,
    load_waivers,
)
from upl_helper.checks.reference import load_reference_tables
from upl_helper.checks.registry import (
    REGISTRY,
    CheckContext,
    RunResult,
    Skip,
    check,
    run_checks,
)
from upl_helper.checks.report import render_json, render_text
from upl_helper.checks.thresholds import Thresholds, load_thresholds
from upl_helper.cli import register_command

# Imported for their registration side effects.
from upl_helper.checks import arithmetic as _arithmetic  # noqa: F401  isort:skip
from upl_helper.checks import identifiers as _identifiers  # noqa: F401  isort:skip
from upl_helper.checks import plausibility as _plausibility  # noqa: F401  isort:skip
from upl_helper.checks import policy as _policy  # noqa: F401  isort:skip

__all__ = [
    "REGISTRY",
    "CheckContext",
    "Finding",
    "RunResult",
    "Scope",
    "Severity",
    "Skip",
    "Thresholds",
    "WaiverSet",
    "apply_waivers",
    "build_context",
    "check",
    "load_thresholds",
    "load_waivers",
    "render_json",
    "render_text",
    "run_checks",
]


def build_context(
    extraction,
    thresholds: Thresholds | None = None,
    reference_path: str | Path | None = None,
) -> CheckContext:
    return CheckContext(
        frame=extraction.frame,
        provenance=extraction.provenance,
        thresholds=thresholds or Thresholds(),
        reference=load_reference_tables(reference_path),
        extraction_report=extraction.report,
        context=extraction.context,
    )


def _run(args: argparse.Namespace) -> int:
    from upl_helper.extract.extractor import extract_path
    from upl_helper.mapping.loader import load_mapping
    from upl_helper.model import ExtractionContext

    mapping = load_mapping(args.mapping)
    context = None
    if args.state or args.year:
        context = ExtractionContext(
            state=(args.state or "").upper(),
            provider_type=mapping.template.provider_type,
            demonstration_year=args.year or 0,
        )

    extraction = extract_path(args.workbook, mapping, context)
    ctx = build_context(extraction, load_thresholds(args.thresholds), args.reference)
    result = run_checks(ctx, load_waivers(args.waivers), args.include or None)

    rendered = render_json(result) if args.format == "json" else render_text(result)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(f"wrote {args.format} report -> {args.output}")
    else:
        print(rendered)

    if not mapping.template.verified_against_real_template:
        print(
            "\nwarning: the mapping is not verified against a real CMS template; "
            "these findings describe a smoke test, not a demonstration"
        )

    return 1 if result.has_blocking_errors else 0


@register_command("check", "Run the check suite against a workbook.")
def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("workbook", help="workbook to check")
    parser.add_argument("-m", "--mapping", required=True, help="template mapping YAML")
    parser.add_argument("--state", default=None, help="two-letter state code")
    parser.add_argument("--year", type=int, default=None, help="demonstration year")
    parser.add_argument("--thresholds", default=None, help="thresholds YAML")
    parser.add_argument("--waivers", default=None, help="waivers YAML")
    parser.add_argument("--reference", default=None, help="CCN reference tables YAML")
    parser.add_argument(
        "--include", action="append", default=[], help="limit to a family; repeatable"
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("-o", "--output", default=None, help="write the report here")
    parser.set_defaults(func=_run)
