"""Descriptor data model.

These dataclasses are the serialized contract defined in SPEC-0002. Field
names are the YAML/JSON keys, so renaming one is a breaking change to every
committed descriptor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DESCRIPTOR_VERSION = 1


@dataclass
class HeaderCandidate:
    row: int
    score: float
    nonempty: int


@dataclass
class FormulaPattern:
    pattern: str
    count: int
    first_row: int
    last_row: int


@dataclass
class CellTypeCounts:
    numeric: int = 0
    string: int = 0
    formula: int = 0
    date: int = 0
    boolean: int = 0
    error: int = 0
    blank: int = 0


@dataclass
class ColumnProfile:
    letter: str
    index: int
    hidden: bool
    width: float | None
    header_text: str | None
    header_normalized: str | None
    number_format: str | None
    cell_type_counts: CellTypeCounts
    formula_patterns: list[FormulaPattern] = field(default_factory=list)


@dataclass
class DataValidationInfo:
    range: str
    type: str | None
    formula1: str | None


@dataclass
class SheetProtectionInfo:
    enabled: bool
    password_hash_present: bool
    selection_locked: bool


@dataclass
class HeaderInfo:
    rows: list[int]
    detected: bool
    candidates: list[HeaderCandidate]


@dataclass
class Dimensions:
    min_row: int
    max_row: int
    min_col: int
    max_col: int


@dataclass
class SheetDescriptor:
    name: str
    index: int
    state: str
    dimensions: Dimensions
    freeze_panes: str | None
    protection: SheetProtectionInfo
    merged_ranges: list[str]
    data_validations: list[DataValidationInfo]
    conditional_formatting_ranges: list[str]
    nonempty_row_count: int
    header: HeaderInfo
    columns: list[ColumnProfile]


@dataclass
class DefinedNameInfo:
    name: str
    scope: str | None
    refers_to: str


@dataclass
class WorkbookProtectionInfo:
    workbook_locked: bool
    lock_structure: bool
    lock_windows: bool


@dataclass
class WorkbookProperties:
    creator: str | None
    title: str | None
    created: str | None
    modified: str | None


@dataclass
class WorkbookInfo:
    properties: WorkbookProperties
    protection: WorkbookProtectionInfo
    defined_names: list[DefinedNameInfo]
    sheet_count: int


@dataclass
class SourceInfo:
    filename: str
    sha256: str
    size_bytes: int
    profiled_at: str
    profiler_version: str


@dataclass
class ProfileOptions:
    strict: bool = False
    header_row_override: list[int] | None = None


@dataclass
class WorkbookDescriptor:
    descriptor_version: int
    source: SourceInfo
    options: ProfileOptions
    workbook: WorkbookInfo
    sheets: list[SheetDescriptor]
