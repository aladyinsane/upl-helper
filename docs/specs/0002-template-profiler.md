# SPEC-0002: Template profiler and unprotect utility

Implements ADR-0001, phase 1 (first half).

## Goal

Two commands. `upl profile` reads a CMS UPL workbook and writes a structural
descriptor — sheets, columns, headers, formulas, protection — that carries no
cell data. `upl unprotect` writes an unprotected copy of a workbook without
otherwise altering it.

Together these let the real templates be described, committed and worked
against from an environment that has never seen them.

## Context & constraints

- Python 3.11+. Dependencies: `openpyxl` for workbook structure, `pyyaml` for
  output, standard library otherwise. **No pandas in this spec** — nothing here
  is tabular.
- Input is `.xlsx` or `.xlsm`. Legacy `.xls` is out of scope.
- The workbooks are protected and contain hidden sheets and hidden columns. The
  profiler reads all of them. Protection is not an error condition.
- The profiler will be run against **filled** workbooks containing real
  provider-level payment data. Its output is intended to be committed to a
  public repository. Everything below follows from that.
- `unprotect` must not silently drop workbook features it does not understand.

## The redaction rule

**The descriptor contains no cell values, with two deliberate exceptions:**

1. Text from the detected header row or rows.
2. Formula strings.

Everything else about a cell is described by metadata only — its type, its
number format, whether it is empty — never its content.

Rationale for the exceptions: header text *is* the template structure and is
the entire point of profiling. Formulas are template logic; a formula in a CMS
template describes the calculation, not a provider. Where a formula embeds a
literal, that literal came from the template author, not from state data.

`--strict` additionally drops data validation formulas, which can carry literal
pick lists. Pick lists are template metadata in every case we expect, but the
flag exists for a reviewer who does not want to have to check.

This rule is enforced by test, not by convention. See AC-13.

## Pipeline / stages

### Stage 1 — load
`upl_helper.profile.loader.load_workbook_structure(path) -> LoadedWorkbook`

Opens with `openpyxl`, `data_only=False` so formulas are readable as text, and
`keep_vba=True` for `.xlsm`. Returns the workbook plus the source file's
sha256, size and name.

Raises `UnsupportedWorkbookError` on `.xls` or on a file that is not a zip.

### Stage 2 — header detection
`upl_helper.profile.headers.detect_header_rows(worksheet, max_scan=30) -> list[HeaderCandidate]`

Scores each of the first `max_scan` rows:

- fraction of non-empty cells that are strings (higher is better)
- fraction of those strings that are distinct (higher is better)
- fraction of cells in the 10 rows below that are numeric (higher is better —
  a header row sits above data)
- penalty if the row has fewer than 3 non-empty cells
- penalty if any cell is part of a merged range spanning more than 4 columns,
  which usually indicates a title banner rather than a header

Returns all candidates with scores, sorted descending. The caller takes the
best unless `--header-row` overrides it. Emitting candidates rather than only
the winner is deliberate: CMS templates have title banners and multi-row
headers, and a human looking at the descriptor needs to see what was rejected.

Multi-row headers are represented by returning more than one candidate above
the `multi_row_threshold` on **adjacent** rows; the column's header text is
then the non-empty parts joined top to bottom with `" / "`.

### Stage 3 — column profiling
`upl_helper.profile.columns.profile_columns(worksheet, header_rows) -> list[ColumnProfile]`

The entry point is plural because columns are profiled in **one pass** over the
sheet. A per-column signature reads better but makes the work quadratic in
column count, and a real UPL template is wide.

Per column: letter, 1-based index, hidden flag, width, header text and its
normalized form, the dominant number format, counts of cell types below the
header (`numeric`, `string`, `formula`, `date`, `boolean`, `error`, `blank`),
and the formula pattern.

**Formula pattern.** For each formula cell, the cell's own row number is
replaced by `{row}` wherever it appears in a relative A1 reference. `=D7*E7`
in row 7 becomes `=D{row}*E{row}`. Identical patterns collapse. The result is
`formula_patterns: [{pattern, count, first_row, last_row}]`, sorted by count.

A column that should be entirely formula-driven but shows one constant among
forty formulas is exactly the defect `STR003` will look for later. Recording
the distribution here is what makes that check possible.

**Header normalization.** Casefold, strip, collapse internal whitespace,
strip trailing punctuation, replace non-alphanumerics with `_`, collapse
repeated `_`. `"Medicare Provider Number (CCN)"` becomes
`medicare_provider_number_ccn`. The raw text is kept alongside it.

### Stage 4 — sheet and workbook profiling
`upl_helper.profile.profiler.profile_workbook(loaded, options) -> WorkbookDescriptor`

Assembles per sheet: name, index, visibility state, used dimensions, freeze
panes, sheet protection, merged ranges, data validations, conditional
formatting ranges, non-empty row count, header candidates, and column profiles.
At workbook level: document properties, workbook protection, defined names,
sheet count.

### Stage 5 — emit
`upl_helper.profile.emit.write_descriptor(descriptor, path, fmt) -> None`

YAML by default, JSON with `--format json`. Keys sorted so descriptors diff
cleanly between template versions — a CMS revision should show as a readable
diff, which is the whole point of committing these.

### Unprotect
`upl_helper.unprotect.unprotect_workbook(src, dst, unhide=False) -> UnprotectReport`

Operates on the xlsx zip directly rather than through `openpyxl`, because
`openpyxl` does not round-trip charts, images, pivot tables or VBA, and a
CMS template contains several of those. The implementation copies every zip
entry byte for byte except the sheet and workbook XML parts, from which it
removes `<sheetProtection/>` and `<workbookProtection/>` elements. With
`--unhide` it also sets hidden sheets to visible and clears column and row
hidden flags.

No password is needed. Worksheet protection in OOXML is an advisory flag plus
an optional password hash; removing the element removes the protection. The
hash is never read and never cracked.

Returns a report of what was removed, which is printed and can be written to a
file with `--report`.

## Data contracts

### `WorkbookDescriptor`

```yaml
descriptor_version: 1
source:
  filename: str
  sha256: str
  size_bytes: int
  profiled_at: str          # ISO 8601 UTC
  profiler_version: str
options:
  strict: bool
  header_row_override: int | null
workbook:
  properties: {creator, title, created, modified}   # nulls allowed
  protection: {workbook_locked: bool, lock_structure: bool, lock_windows: bool}
  defined_names: [{name: str, scope: str | null, refers_to: str}]
  sheet_count: int
sheets:
  - name: str
    index: int
    state: visible | hidden | veryHidden
    dimensions: {min_row: int, max_row: int, min_col: int, max_col: int}
    freeze_panes: str | null
    protection: {enabled: bool, password_hash_present: bool, selection_locked: bool}
    merged_ranges: [str]
    data_validations: [{range: str, type: str, formula1: str | null}]
    conditional_formatting_ranges: [str]
    nonempty_row_count: int
    header:
      rows: [int]
      detected: bool
      candidates: [{row: int, score: float, nonempty: int}]
    columns:
      - letter: str
        index: int
        hidden: bool
        width: float | null
        header_text: str | null
        header_normalized: str | null
        number_format: str | null
        cell_type_counts: {numeric: int, string: int, formula: int,
                           date: int, boolean: int, error: int, blank: int}
        formula_patterns: [{pattern: str, count: int,
                            first_row: int, last_row: int}]
```

`data_validations[].formula1` is `null` under `--strict`.

### `UnprotectReport`

```yaml
source: {filename: str, sha256: str}
output: {filename: str, sha256: str}
removed:
  workbook_protection: bool
  sheet_protection: [str]        # sheet names
unhidden:
  sheets: [str]
  columns: {sheet_name: [str]}   # column letters
  rows: {sheet_name: int}        # count
warnings: [str]
```

## CLI

```
upl profile WORKBOOK [-o PATH] [--format yaml|json] [--strict]
                     [--header-row N] [--sheet NAME]...
upl unprotect SRC [-o PATH] [--unhide] [--report PATH]
```

`upl profile` with no `-o` writes `<workbook stem>.descriptor.yaml` next to the
workbook. `upl unprotect` with no `-o` writes `<stem>.unprotected.<ext>`.
Neither command ever writes to its input.

## Validation / acceptance criteria

1. `profile` on a workbook with hidden sheets includes every hidden sheet, with
   `state` reported as `hidden` or `veryHidden` as appropriate.
2. `profile` on a workbook with hidden columns includes every hidden column,
   with `hidden: true`.
3. `profile` on a protected sheet succeeds and reports
   `protection.enabled: true`, without modifying the input file.
4. Header detection selects the correct row for a workbook whose data starts
   below a merged title banner.
5. Header detection returns at least two scored candidates when the first 30
   rows contain more than one plausible header row.
6. `--header-row N` overrides detection and the descriptor records the override
   in `options.header_row_override`.
7. A multi-row header produces header text joined with `" / "` in top-to-bottom
   order.
8. Header normalization maps `"Medicare Provider Number (CCN)"` to
   `medicare_provider_number_ccn`.
9. A column whose cells all carry the same relative formula produces exactly
   one entry in `formula_patterns` with `count` equal to the number of formula
   cells.
10. A column of 40 formulas containing 1 hardcoded constant produces one
    formula pattern with `count: 39` and `cell_type_counts.numeric >= 1`.
11. Two descriptors of the same file are byte-identical except for
    `source.profiled_at`.
12. Descriptor key ordering is stable, so a diff between two template versions
    shows only genuine structural differences.
13. **Redaction.** Given a workbook whose every data cell contains the canary
    string `ZZCANARYZZ` and whose headers and formulas do not, the serialized
    descriptor does not contain `ZZCANARYZZ` anywhere. This test runs in both
    YAML and JSON output modes and in both strict and non-strict modes.
14. **Redaction, numeric.** Given a workbook whose data cells contain the
    distinctive value `987654321.12`, that literal does not appear in the
    descriptor.
15. `unprotect` output opens in `openpyxl` with no protection on any sheet.
16. `unprotect` preserves every zip entry present in the source except for
    modifications to sheet and workbook XML — entry names in and out are
    identical as sets.
17. `unprotect` on an `.xlsm` preserves the VBA project part byte for byte.
18. `unprotect --unhide` sets every hidden sheet to visible and clears hidden
    flags on columns and rows, and the report lists what changed.
19. `unprotect` never modifies its input: the source file's sha256 is identical
    before and after.
20. `profile` on a file that is not a zip raises `UnsupportedWorkbookError`
    with a message naming the file, and exits non-zero without a traceback.
21. `profile` on a workbook with zero rows of data below the header succeeds and
    reports `nonempty_row_count: 0` rather than failing.

## Out of scope

- Reading cell values into a data model. That is the extractor, SPEC-0003.
- Any interpretation of what a column *means*. The profiler describes; the
  mapping interprets.
- Downloading templates from CMS or MACFin.
- Legacy `.xls`.
- Cracking or reading protection passwords.
- Writing to or repairing a workbook, beyond `unprotect`'s copy.

## Open questions

1. ~~CMS templates may use defined names for the demonstration data ranges. If
   they do, defined names are a more stable anchor than header text and the
   mapping format in SPEC-0003 should prefer them. Flag what you find in the
   real descriptor; do not design for it speculatively.~~ **Resolved
   2026-09-17:** the real inpatient hospital template has 18 defined names
   (`_OwnershipType`, `_DemoType`, `Cost_Count`, `DV_Rule_1`, etc.), all
   pointing at dropdown validation lists and row-count controls on the
   hidden `LKUP`/`_Controls` sheets. None anchor the demonstration data range
   itself — there is no defined name for "the provider rows on IP Cost."
   Header-text matching stays the only viable anchor for locating data; there
   is nothing more stable to prefer.
2. ~~Whether the inpatient template's demonstration tab has a single header
   row or a two-row header is unknown until phase 0. Both are handled; which
   one occurs should be recorded.~~ **Resolved 2026-09-17:** neither, cleanly
   — each of the four methodology tabs (`IP Cost`, `IP Payment`, `IP DRG`,
   `IP Per Diem`) carries three superimposed header-like row bands: row 6 is
   a single row of rich, multi-line cells combining a category label,
   requirement tag, field name and CMS variable number in one string per
   cell (e.g. `"Provider Info: (Required) Provider Name [108]"`); rows 8–9
   are a genuine two-row block (variable number, then a clean one-line
   variable description — e.g. `"Provider Name"`); row 11 is an unrelated
   single row of data-entry instructions (e.g. `"Obtain from Medicare Cost
   Reports"`) that superficially resembles a header. Rows 8–9's description
   row (row 9 alone, once joined) is the one a mapping should target — it is
   the only clean, unambiguous field name. The header-detection heuristic
   currently picks row 11 by default (a real false positive: instructions
   score as highly as a header because they are fully populated, similarly
   shaped text), so a real mapping for this template must pin
   `header.rows` explicitly rather than rely on auto-detection.
3. ~~Very large workbooks — if a state's template runs to tens of thousands of
   rows, per-cell iteration may be slow enough to need `read_only=True`,
   which costs access to some structure. Do not optimize for this until a
   real file proves it necessary.~~ **Resolved 2026-09-17:** measured against
   the real inpatient hospital template (15 MB, 26 sheets, ~5,000 data rows,
   workbook-protected) — `read_only=False` (what the profiler uses) takes
   about 8 seconds to load; `read_only=True` loads near-instantly (~0.03s)
   but its `ReadOnlyWorksheet` has no `merged_cells`, `data_validations`, or
   `protection` attributes at all (`AttributeError`, not empty values) —
   confirmed directly against openpyxl, not from documentation. Since the
   descriptor's schema requires exactly those three (`merged_ranges`,
   `data_validations`, `conditional_formatting_ranges`, `protection`),
   `read_only=True` cannot produce a complete descriptor as currently
   specified; that is the concrete cost the original question anticipated.
   8 seconds on a real, sizeable template is not yet a problem worth trading
   that structural fidelity away for, so this stays unoptimized.
