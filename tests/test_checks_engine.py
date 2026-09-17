"""Engine, waivers, identifiers and reporting (SPEC-0004 AC-1, 12..23)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from tests.checkhelpers import VERIFIED_REFERENCE, ids, make_context, provider
from upl_helper.checks.findings import (
    Finding,
    Scope,
    Severity,
    WaiverError,
    apply_waivers,
    load_waivers,
)
from upl_helper.checks.identifiers import (
    idn001_ccn_format,
    idn002_ccn_state_prefix,
    idn003_ccn_facility_type,
    idn004_npi_check_digit,
)
from upl_helper.checks.registry import REGISTRY, Skip, check, run_checks
from upl_helper.checks.report import render_json, render_text
from upl_helper.checks.thresholds import ThresholdError, load_thresholds
from upl_helper.model import ExtractionContext

IL = ExtractionContext(
    state="IL", provider_type="inpatient_hospital", demonstration_year=2024
)


def finding(check_id: str = "X001", subject: str = "140001", **kw) -> Finding:
    return Finding(
        check_id=check_id,
        severity=kw.pop("severity", Severity.ERROR),
        scope=Scope.PROVIDER,
        subject=subject,
        message=kw.pop("message", "something"),
        **kw,
    )


# --- engine -----------------------------------------------------------------


def test_a_broken_check_does_not_take_the_run_down() -> None:
    """AC-1."""

    @check("ZZZ999", "ZZZ", "deliberately broken", Severity.ERROR)
    def _broken(ctx):
        raise RuntimeError("boom")
        yield  # pragma: no cover

    try:
        result = run_checks(make_context([provider()]))
        broken = next(r for r in result.results if r.check_id == "ZZZ999")
        assert broken.status == "failed"
        assert any(r.status == "ran" for r in result.results)
        assert "ZZZ999" in ids(result.findings)
    finally:
        del REGISTRY["ZZZ999"]


def test_families_can_be_filtered() -> None:
    result = run_checks(make_context([provider()]), families=["ARI"])
    assert {r.check_id[:3] for r in result.results} == {"ARI"}


def test_skipped_checks_are_recorded_with_a_reason() -> None:
    result = run_checks(make_context([provider(npi=None)]), families=["IDN"])
    skipped = {
        r.check_id: r.skip_reason for r in result.results if r.status == "skipped"
    }
    assert "IDN004" in skipped
    assert "npi" in skipped["IDN004"]


# --- identifiers ------------------------------------------------------------


def test_idn001_rejects_malformed_ccns() -> None:
    """AC-12."""
    ctx = make_context([provider(ccn="14001"), provider(ccn="14ABCD")])
    findings = list(idn001_ccn_format(ctx))
    assert len(findings) == 2
    assert "expected 6 characters" in findings[0].message
    assert "not digits" in findings[1].message


def test_idn001_accepts_a_well_formed_ccn() -> None:
    assert list(idn001_ccn_format(make_context([provider()]))) == []


def test_idn002_and_idn003_skip_while_tables_are_unverified() -> None:
    """AC-13. A check must not invent findings from an unchecked table."""
    ctx = make_context([provider()], context=IL)
    for func in (idn002_ccn_state_prefix, idn003_ccn_facility_type):
        with pytest.raises(Skip) as excinfo:
            list(func(ctx))
        assert "unverified" in excinfo.value.reason


def test_idn002_runs_against_a_verified_table() -> None:
    """AC-13, the running half."""
    ctx = make_context(
        [provider(ccn="140001"), provider(ccn="450002")],
        reference=VERIFIED_REFERENCE,
        context=IL,
    )
    findings = list(idn002_ccn_state_prefix(ctx))
    assert [f.subject for f in findings] == ["450002"]
    assert "belongs to TX" in findings[0].message


def test_idn003_flags_a_sequence_outside_the_provider_type_ranges() -> None:
    ctx = make_context(
        [provider(ccn="140001"), provider(ccn="145500")],
        reference=VERIFIED_REFERENCE,
        context=IL,
    )
    findings = list(idn003_ccn_facility_type(ctx))
    assert [f.subject for f in findings] == ["145500"]


def test_idn004_flags_a_bad_npi() -> None:
    ctx = make_context([provider(npi="1234567893"), provider(npi="1234567839")])
    findings = list(idn004_npi_check_digit(ctx))
    assert [f.subject for f in findings] == ["1234567839"]


# --- fingerprints and waivers ----------------------------------------------


def test_fingerprint_is_stable_across_a_changed_observed_value() -> None:
    """AC-14. A waiver that dies when next year's number moves is not a waiver."""
    first = finding(observed=100.0)
    second = finding(observed=999_999.0)
    assert first.fingerprint == second.fingerprint


def test_fingerprint_differs_by_subject_and_check() -> None:
    assert finding().fingerprint != finding(subject="140002").fingerprint
    assert finding().fingerprint != finding(check_id="Y001").fingerprint


def test_waiver_by_fingerprint_suppresses(tmp_path: Path) -> None:
    """AC-15."""
    target = finding()
    unwaived, waived, expired = apply_waivers(
        [target],
        load_waivers(
            _write(
                tmp_path,
                [
                    {
                        "fingerprint": target.fingerprint,
                        "reason": "known",
                        "expires": "2099-01-01",
                    }
                ],
            )
        ),
        today=dt.date(2026, 9, 17),
    )
    assert unwaived == []
    assert len(waived) == 1
    assert waived[0].waiver.reason == "known"
    assert expired == []


def test_waiver_by_check_and_subject_matches(tmp_path: Path) -> None:
    """AC-19."""
    waivers = load_waivers(
        _write(
            tmp_path,
            [
                {
                    "check_id": "X001",
                    "subject": "140001",
                    "reason": "ok",
                    "expires": "2099-01-01",
                }
            ],
        )
    )
    unwaived, waived, _ = apply_waivers(
        [finding()], waivers, today=dt.date(2026, 9, 17)
    )
    assert unwaived == []
    assert len(waived) == 1


def test_waiver_by_check_id_alone_matches_every_subject(tmp_path: Path) -> None:
    waivers = load_waivers(
        _write(
            tmp_path, [{"check_id": "X001", "reason": "ok", "expires": "2099-01-01"}]
        )
    )
    unwaived, waived, _ = apply_waivers(
        [finding(), finding(subject="140002")], waivers, today=dt.date(2026, 9, 17)
    )
    assert unwaived == []
    assert len(waived) == 2


def test_waiver_without_a_reason_is_rejected(tmp_path: Path) -> None:
    """AC-16."""
    with pytest.raises(WaiverError) as excinfo:
        load_waivers(_write(tmp_path, [{"check_id": "X001", "expires": "2099-01-01"}]))
    assert "silent suppression" in str(excinfo.value)


def test_waiver_with_a_blank_reason_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(WaiverError):
        load_waivers(
            _write(
                tmp_path,
                [{"check_id": "X001", "reason": "   ", "expires": "2099-01-01"}],
            )
        )


def test_waiver_without_an_expiration_is_rejected(tmp_path: Path) -> None:
    """AC-17."""
    with pytest.raises(WaiverError) as excinfo:
        load_waivers(_write(tmp_path, [{"check_id": "X001", "reason": "ok"}]))
    assert "expires" in str(excinfo.value)


def test_an_expired_waiver_does_not_suppress(tmp_path: Path) -> None:
    """AC-18."""
    waivers = load_waivers(
        _write(
            tmp_path,
            [{"check_id": "X001", "reason": "lapsed", "expires": "2025-01-01"}],
        )
    )
    unwaived, waived, expired = apply_waivers(
        [finding()], waivers, today=dt.date(2026, 9, 17)
    )
    assert len(unwaived) == 1
    assert waived == []
    assert len(expired) == 1
    assert expired[0].check_id == "WAIVER_EXPIRED"
    assert "lapsed" in expired[0].message


def test_shipped_example_waivers_load() -> None:
    assert len(load_waivers("config/waivers.example.yaml").waivers) == 2


# --- thresholds and reporting ----------------------------------------------


def test_thresholds_load_from_yaml() -> None:
    """AC-21."""
    assert load_thresholds("config/thresholds/default.yaml").ccr_max == 1.20


def test_unknown_threshold_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "t.yaml"
    bad.write_text("ccr_maximum: 3.0\n")
    with pytest.raises(ThresholdError) as excinfo:
        load_thresholds(bad)
    assert "ccr_maximum" in str(excinfo.value)


def test_json_report_round_trips_findings_with_fingerprints() -> None:
    """AC-22."""
    result = run_checks(make_context([provider(upl_gap=1.0)]), families=["ARI"])
    payload = json.loads(render_json(result))
    assert payload["counts"]["error"] >= 1
    assert all(len(f["fingerprint"]) == 16 for f in payload["findings"])


def test_text_report_lists_findings_and_skips() -> None:
    result = run_checks(make_context([provider(upl_gap=1.0)]))
    text = render_text(result)
    assert "ERROR ARI004" in text
    assert "SKIP" in text
    assert "check(s) ran" in text


def test_waived_errors_do_not_block(tmp_path: Path) -> None:
    """AC-20."""
    ctx = make_context([provider(upl_gap=1.0)])
    unwaived = run_checks(ctx, families=["ARI"])
    assert unwaived.has_blocking_errors

    target = unwaived.findings[0]
    waivers = load_waivers(
        _write(
            tmp_path,
            [
                {
                    "fingerprint": target.fingerprint,
                    "reason": "ok",
                    "expires": "2099-01-01",
                }
            ],
        )
    )
    waived = run_checks(ctx, waivers, families=["ARI"])
    assert not waived.has_blocking_errors
    assert len(waived.waived) == 1


def _write(tmp_path: Path, waivers: list[dict]) -> Path:
    import yaml

    path = tmp_path / "waivers.yaml"
    path.write_text(yaml.safe_dump({"waivers": waivers}))
    return path
