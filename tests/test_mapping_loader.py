"""Mapping validation (SPEC-0003 AC-5)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from upl_helper.mapping.loader import load_mapping, parse_mapping
from upl_helper.mapping.models import MappingError

MINIMAL = {
    "mapping_version": 1,
    "template": {"provider_type": "inpatient_hospital", "template_version": "t"},
    "sheets": [
        {
            "role": "demonstration",
            "match": {"name_equals": "Demo"},
            "key_field": "ccn",
            "fields": {
                "provider_name": {"aliases": ["provider name"]},
                "ccn": {"aliases": ["ccn"]},
                "ownership_category": {"aliases": ["ownership"]},
                "upl_amount": {"aliases": ["upl"]},
                "medicaid_payments_total": {"aliases": ["total payments"]},
            },
        }
    ],
}


def _mapping(**overrides: object) -> dict:
    import copy

    payload = copy.deepcopy(MINIMAL)
    payload.update(overrides)
    return payload


def test_minimal_mapping_parses() -> None:
    mapping = parse_mapping(_mapping())
    assert mapping.template.provider_type == "inpatient_hospital"
    assert mapping.sheets[0].key_field == "ccn"
    assert mapping.template.verified_against_real_template is False


def test_alias_listed_under_two_fields_is_rejected() -> None:
    """AC-5. Caught at load time, before any workbook is opened."""
    payload = _mapping()
    payload["sheets"][0]["fields"]["upl_amount"]["aliases"] = ["ccn"]
    with pytest.raises(MappingError) as excinfo:
        parse_mapping(payload)
    assert "listed under both" in str(excinfo.value)


def test_unknown_canonical_field_is_rejected() -> None:
    payload = _mapping()
    payload["sheets"][0]["fields"]["not_a_field"] = {"aliases": ["x"]}
    with pytest.raises(MappingError) as excinfo:
        parse_mapping(payload)
    assert "not a canonical field" in str(excinfo.value)


def test_wrong_mapping_version_is_rejected() -> None:
    with pytest.raises(MappingError):
        parse_mapping(_mapping(mapping_version=99))


def test_match_requires_exactly_one_strategy() -> None:
    payload = _mapping()
    payload["sheets"][0]["match"] = {"name_equals": "a", "name_matches": "b"}
    with pytest.raises(MappingError) as excinfo:
        parse_mapping(payload)
    assert "exactly one" in str(excinfo.value)


def test_key_field_must_be_a_mapped_field() -> None:
    payload = _mapping()
    payload["sheets"][0]["key_field"] = "npi"
    with pytest.raises(MappingError) as excinfo:
        parse_mapping(payload)
    assert "key_field" in str(excinfo.value)


def test_total_row_marker_must_be_a_mapped_field() -> None:
    payload = _mapping()
    payload["sheets"][0]["data_rows"] = {"total_row_markers": ["npi"]}
    with pytest.raises(MappingError):
        parse_mapping(payload)


def test_unknown_ownership_category_is_rejected() -> None:
    payload = _mapping()
    payload["sheets"][0]["ownership"] = {
        "from": "column",
        "column": "ownership_category",
        "values": {"municipal": ["city"]},
    }
    with pytest.raises(MappingError) as excinfo:
        parse_mapping(payload)
    assert "ownership category" in str(excinfo.value)


def test_shipped_provisional_mapping_is_valid() -> None:
    mapping = load_mapping("config/templates/inpatient-hospital-provisional.yaml")
    assert mapping.template.verified_against_real_template is False, (
        "the shipped mapping must stay marked unverified until phase 0 confirms it"
    )


REAL_INPATIENT_TEMPLATE = "templates/upl-2022/inpatient-hospital-upl-template-2022.xlsx"


def test_verified_inpatient_mapping_is_marked_verified() -> None:
    mapping = load_mapping("config/templates/inpatient-hospital-2022.yaml")
    assert mapping.template.verified_against_real_template is True


def test_verified_inpatient_mapping_resolves_against_the_real_template() -> None:
    """Ties the mapping to the actual committed CMS workbook, not a guess.

    The real template is blank (no filled provider rows), so this only
    proves every required field resolves to exactly one column on each of
    the four methodology tabs -- it cannot prove the values come out right.
    """
    from upl_helper.extract.extractor import extract_path

    mapping = load_mapping("config/templates/inpatient-hospital-2022.yaml")
    extraction = extract_path(REAL_INPATIENT_TEMPLATE, mapping)
    matched = {m["sheet"] for m in extraction.report.sheets_matched}
    assert matched == {"IP Cost", "IP Payment", "IP DRG", "IP Per Diem"}
    assert not extraction.report.rules_unmatched
    for sheet, missing in extraction.report.fields_missing.items():
        assert missing == [], f"{sheet}: required-adjacent fields unresolved: {missing}"


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(MappingError):
        load_mapping(tmp_path / "nope.yaml")


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [1,\n")
    with pytest.raises(MappingError):
        load_mapping(bad)


def test_top_level_list_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "list.yaml"
    bad.write_text(yaml.safe_dump([1, 2, 3]))
    with pytest.raises(MappingError):
        load_mapping(bad)
