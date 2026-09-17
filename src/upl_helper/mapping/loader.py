"""Loading and validating a template mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from upl_helper.mapping.models import (
    DataRowRule,
    FieldRule,
    MappingError,
    OwnershipRule,
    SheetRule,
    TemplateInfo,
    TemplateMapping,
)
from upl_helper.model import FIELDS_BY_NAME, Dtype, Ownership
from upl_helper.profile.text import normalize_header

SUPPORTED_MAPPING_VERSION = 1
VALID_ROLES = {"demonstration", "summary", "input", "ignore"}


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise MappingError(f"{where}: missing required key {key!r}")
    return mapping[key]


def _parse_field(name: str, raw: dict[str, Any], where: str) -> FieldRule:
    if name not in FIELDS_BY_NAME:
        known = ", ".join(sorted(FIELDS_BY_NAME))
        raise MappingError(
            f"{where}: {name!r} is not a canonical field. Known fields: {known}"
        )
    aliases = _require(raw, "aliases", f"{where}.{name}")
    if not isinstance(aliases, list) or not aliases:
        raise MappingError(f"{where}.{name}.aliases: expected a non-empty list")

    declared = raw.get("dtype")
    dtype = Dtype(declared) if declared else FIELDS_BY_NAME[name].dtype
    return FieldRule(
        name=name,
        aliases=[str(a) for a in aliases],
        required=bool(raw.get("required", FIELDS_BY_NAME[name].required)),
        dtype=dtype,
    )


def _parse_ownership(raw: dict[str, Any] | None, where: str) -> OwnershipRule | None:
    if raw is None:
        return None
    source = _require(raw, "from", f"{where}.ownership")
    if source not in {"column", "constant"}:
        raise MappingError(f"{where}.ownership.from: expected 'column' or 'constant'")
    if source == "constant":
        constant = _require(raw, "constant", f"{where}.ownership")
        if constant not in {o.value for o in Ownership}:
            raise MappingError(
                f"{where}.ownership.constant: {constant!r} is not an ownership category"
            )
    values = raw.get("values", {}) or {}
    for canonical in values:
        if canonical not in {o.value for o in Ownership}:
            raise MappingError(
                f"{where}.ownership.values: {canonical!r} is not an ownership category"
            )
    return OwnershipRule(
        source=source,
        column=raw.get("column"),
        constant=raw.get("constant"),
        values={k: [str(v) for v in vs] for k, vs in values.items()},
    )


def _check_alias_collisions(fields: dict[str, FieldRule], where: str) -> None:
    """An alias meaning two things is a mapping bug, caught before any workbook."""
    seen: dict[str, str] = {}
    for field_rule in fields.values():
        for alias in field_rule.aliases:
            normalized = normalize_header(alias)
            if normalized is None:
                raise MappingError(
                    f"{where}.{field_rule.name}: alias {alias!r} normalizes to nothing"
                )
            if normalized in seen and seen[normalized] != field_rule.name:
                raise MappingError(
                    f"{where}: alias {alias!r} is listed under both "
                    f"{seen[normalized]!r} and {field_rule.name!r}"
                )
            seen[normalized] = field_rule.name


def _parse_sheet(raw: dict[str, Any], index: int) -> SheetRule:
    where = f"sheets[{index}]"
    role = raw.get("role", "demonstration")
    if role not in VALID_ROLES:
        raise MappingError(
            f"{where}.role: {role!r} is not one of {', '.join(sorted(VALID_ROLES))}"
        )

    match = _require(raw, "match", where)
    name_equals = match.get("name_equals")
    name_matches = match.get("name_matches")
    if bool(name_equals) == bool(name_matches):
        raise MappingError(
            f"{where}.match: set exactly one of 'name_equals' or 'name_matches'"
        )

    raw_fields = _require(raw, "fields", where)
    fields = {
        name: _parse_field(name, spec, f"{where}.fields")
        for name, spec in raw_fields.items()
    }
    _check_alias_collisions(fields, f"{where}.fields")

    key_field = raw.get("key_field", "ccn")
    if key_field not in fields:
        raise MappingError(
            f"{where}.key_field: {key_field!r} is not among this sheet's fields"
        )

    data_rows_raw = raw.get("data_rows", {}) or {}
    for marker in data_rows_raw.get("total_row_markers", []) or []:
        if marker not in fields:
            raise MappingError(
                f"{where}.data_rows.total_row_markers: {marker!r} is not a "
                "field on this sheet"
            )

    header = raw.get("header", {}) or {}
    return SheetRule(
        role=role,
        required=bool(raw.get("required", role == "demonstration")),
        name_equals=name_equals,
        name_matches=name_matches,
        header_rows=header.get("rows"),
        key_field=key_field,
        data_rows=DataRowRule(
            stop_on_blank_key=bool(data_rows_raw.get("stop_on_blank_key", True)),
            total_row_markers=list(data_rows_raw.get("total_row_markers", []) or []),
            exclude_if_normalized_in=[
                str(v) for v in (data_rows_raw.get("exclude_if_normalized_in") or [])
            ],
            start_row=data_rows_raw.get("start_row"),
        ),
        ownership=_parse_ownership(raw.get("ownership"), where),
        fields=fields,
    )


def parse_mapping(payload: dict[str, Any]) -> TemplateMapping:
    version = payload.get("mapping_version")
    if version != SUPPORTED_MAPPING_VERSION:
        raise MappingError(
            f"mapping_version: expected {SUPPORTED_MAPPING_VERSION}, got {version!r}"
        )

    template_raw = _require(payload, "template", "mapping")
    sheets_raw = _require(payload, "sheets", "mapping")
    if not isinstance(sheets_raw, list) or not sheets_raw:
        raise MappingError("sheets: expected a non-empty list")

    return TemplateMapping(
        mapping_version=version,
        template=TemplateInfo(
            provider_type=_require(template_raw, "provider_type", "template"),
            template_version=str(
                _require(template_raw, "template_version", "template")
            ),
            verified_against_real_template=bool(
                template_raw.get("verified_against_real_template", False)
            ),
            notes=template_raw.get("notes"),
        ),
        sheets=[_parse_sheet(raw, i) for i, raw in enumerate(sheets_raw)],
    )


def load_mapping(path: str | Path) -> TemplateMapping:
    path = Path(path)
    if not path.exists():
        raise MappingError(f"{path}: no such mapping file")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MappingError(f"{path}: not valid YAML ({exc})") from exc
    if not isinstance(payload, dict):
        raise MappingError(f"{path}: expected a YAML mapping at the top level")
    return parse_mapping(payload)
