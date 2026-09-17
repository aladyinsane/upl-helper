"""Mapping file data model."""

from __future__ import annotations

from dataclasses import dataclass, field

from upl_helper.errors import UplHelperError
from upl_helper.model import Dtype


class MappingError(UplHelperError):
    """The mapping is invalid, or does not fit the workbook it was applied to."""


@dataclass
class FieldRule:
    name: str
    aliases: list[str]
    required: bool
    dtype: Dtype


@dataclass
class DataRowRule:
    stop_on_blank_key: bool = True
    total_row_markers: list[str] = field(default_factory=list)
    exclude_if_normalized_in: list[str] = field(default_factory=list)


@dataclass
class OwnershipRule:
    source: str  # "column" or "constant"
    column: str | None = None
    constant: str | None = None
    values: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class SheetRule:
    role: str
    required: bool
    name_equals: str | None
    name_matches: str | None
    header_rows: list[int] | None
    key_field: str
    data_rows: DataRowRule
    ownership: OwnershipRule | None
    fields: dict[str, FieldRule]

    @property
    def label(self) -> str:
        return self.name_equals or f"~{self.name_matches}"


@dataclass
class TemplateInfo:
    provider_type: str
    template_version: str
    verified_against_real_template: bool
    notes: str | None = None


@dataclass
class TemplateMapping:
    mapping_version: int
    template: TemplateInfo
    sheets: list[SheetRule]
