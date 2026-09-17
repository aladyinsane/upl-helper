# SPEC-0003: Canonical model, template mapping and extractor

Implements ADR-0001, phase 1 (second half).

## Goal

Turn any mapped CMS UPL workbook into the same tidy table, so that every check
is written once against a stable schema rather than once per template version
and provider type.

## Context & constraints

- Python 3.11+, `pandas`, `pyyaml`, `openpyxl`. `pandas` becomes a hard
  dependency here; it was optional before.
- Depends on SPEC-0002 for reading workbook structure.
- **The real inpatient template has not been seen.** The mapping shipped with
  this spec is provisional and is marked as such in the file itself. The
  machinery is what is being built; the mapping is data that phase 0 replaces.
- One state, one provider type, one demonstration year per extraction, per
  ADR-0001.

## The central idea

A mapping file names the fields the canonical model wants and lists the header
strings that have meant each field. The extractor resolves columns by
**normalized header text**, never by position. A CMS revision that moves
columns needs no code change; a CMS revision that renames a header needs one
line added to an alias list.

## Pipeline / stages

### Stage 1 — load the mapping
`upl_helper.mapping.loader.load_mapping(path) -> TemplateMapping`

Parses and validates the YAML. Validation failures raise `MappingError` naming
the offending key. An alias that appears under two fields on the same sheet is
a validation error, not a runtime surprise.

### Stage 2 — resolve sheets
`upl_helper.mapping.resolve.resolve_sheets(workbook, mapping) -> list[ResolvedSheet]`

Each sheet rule matches by exact name or by regex. A rule matching no sheet is
an error if `required`, otherwise a warning in the report. A sheet matching no
rule is reported as unmapped — that is how a new tab in a revised template
becomes visible instead of being silently ignored.

### Stage 3 — resolve columns
`upl_helper.mapping.resolve.resolve_columns(sheet_headers, sheet_rule) -> ColumnResolution`

For each field, normalize every alias and every header and match exactly.

- No match and `required: true` -> error
- No match and `required: false` -> the field is absent, recorded in the report
- **More than one match -> error.** Never guess between two candidate columns;
  an ambiguous mapping is a mapping bug and silently picking the leftmost is
  how a check ends up validating the wrong column.

Headers that match no field are collected as `unmapped_columns`. A template
revision that adds a column shows up here.

### Stage 4 — extract rows
`upl_helper.extract.extractor.extract(workbook, mapping) -> Extraction`

Walks data rows beneath the header. A row is skipped when:

- every mapped cell is empty, or
- its key field is empty and `stop_on_blank_key` is set (extraction of that
  sheet stops there), or
- the normalized value of any field listed in `total_row_markers` matches one
  of `exclude_if_normalized_in` — this is how `Total` and `Grand Total` rows
  are kept out of the provider table.

Skipped rows are counted by reason in the report. A large skip count is itself
a signal worth seeing.

### Stage 5 — coerce values
`upl_helper.extract.coerce.coerce_value(raw, dtype) -> tuple[value, CoercionIssue | None]`

`string`, `integer`, `number`, `date`, `ratio`, `money`.

Numeric coercion accepts what people actually put in spreadsheets: thousands
separators, a leading currency symbol, a trailing `%` for `ratio`, and
parenthesized negatives `(1,234.56)` -> `-1234.56`. A blank becomes null.

**Anything else records a `CoercionIssue` rather than silently becoming null.**
A number stored as text that fails to parse is a real defect and the check
suite needs to see it, with its cell reference.

### Stage 6 — assemble
Produces an `Extraction`:

- `frame` — a `pandas.DataFrame`, one row per provider-period, canonical
  columns only, missing optional fields present and all-null
- `provenance` — a `DataFrame` of the same shape holding `"Sheet!E12"` strings
- `report` — an `ExtractionReport`

Provenance is not optional decoration. A finding that cannot point at a cell is
much less useful to whoever has to fix the workbook.

## Data contracts

### Canonical fields

Grain: **one row per provider per demonstration period.**

| field | dtype | required | notes |
|---|---|---|---|
| `provider_name` | string | yes | as written in the workbook |
| `ccn` | string | yes | Medicare provider number, kept as text to preserve leading zeros |
| `npi` | string | no | |
| `medicaid_provider_id` | string | no | |
| `ownership_category` | string | yes | `state`, `non_state_government`, `private`, `unknown` |
| `cost_report_period_start` | date | no | |
| `cost_report_period_end` | date | no | |
| `medicaid_days` | number | no | |
| `medicaid_discharges` | number | no | |
| `medicaid_charges` | money | no | |
| `cost_to_charge_ratio` | ratio | no | |
| `trend_factor` | ratio | no | |
| `medicaid_cost` | money | no | the UPL basis |
| `upl_amount` | money | yes | |
| `medicaid_payments_base` | money | no | |
| `medicaid_payments_supplemental` | money | no | |
| `medicaid_payments_total` | money | yes | |
| `upl_gap` | money | no | `upl_amount - medicaid_payments_total` where present |

Run-level, not columns: state, provider type, demonstration year, methodology.
These live on `ExtractionContext` because they are constant for the run and
repeating them per row invites disagreement between rows.

Unknown-but-present columns are **not** dropped silently; they land in
`report.unmapped_columns`.

### Mapping file

```yaml
mapping_version: 1
template:
  provider_type: inpatient_hospital
  template_version: str
  verified_against_real_template: bool     # false until phase 0
  notes: str
sheets:
  - role: demonstration | summary | input | ignore
    required: bool
    match: {name_equals: str} | {name_matches: str}
    header: {rows: [int]}                  # optional, else detected
    key_field: str
    data_rows:
      stop_on_blank_key: bool
      total_row_markers: [str]             # canonical field names to inspect
      exclude_if_normalized_in: [str]
    ownership:
      from: column | constant
      column: str                          # canonical field name
      constant: str
      values: {canonical_value: [alias, ...]}
    fields:
      <canonical field name>:
        aliases: [str, ...]
        required: bool
        dtype: string|integer|number|date|ratio|money
```

### `ExtractionReport`

```yaml
sheets_matched: [{rule: str, sheet: str, rows_extracted: int}]
sheets_unmapped: [str]
rules_unmatched: [str]
fields_missing: {sheet_name: [field, ...]}
unmapped_columns: {sheet_name: [header_text, ...]}
rows_skipped: {sheet_name: {blank: int, total_row: int, blank_key: int}}
coercion_issues: [{sheet, cell, field, raw, dtype, message}]
```

## CLI

```
upl extract WORKBOOK -m MAPPING [-o PATH] [--state XX] [--year YYYY]
```

Prints the extraction report. With `-o`, writes the frame as CSV or Parquet by
extension. When the mapping is not marked
`verified_against_real_template`, the command says so on every run — an
unverified mapping producing confident-looking output is worse than no output.

## Validation / acceptance criteria

1. A field is resolved from any of its aliases, case- and punctuation-insensitive:
   `"Medicare Provider Number (CCN)"`, `"medicare provider number"` and
   `"CCN"` all resolve to `ccn` given those aliases.
2. Columns are resolved by header text, not position: moving a column to the
   other end of the sheet changes nothing about the extracted frame.
3. A required field with no matching header raises `MappingError` naming the
   field and the sheet.
4. Two headers matching aliases of the same field raises `MappingError` naming
   both columns. It never picks one.
5. An alias listed under two fields in the same sheet rule fails at
   `load_mapping`, before any workbook is read.
6. Headers matching no field appear in `report.unmapped_columns`.
7. A sheet matching no rule appears in `report.sheets_unmapped`.
8. A required sheet rule matching no sheet raises `MappingError`.
9. `stop_on_blank_key` halts extraction of that sheet at the first row whose
   key field is blank, and rows below it are not extracted.
10. A row whose marker field normalizes to `total` or `grand total` is excluded
    and counted under `rows_skipped.total_row`.
11. `"$1,234.56"` coerces to `1234.56`; `"(1,234.56)"` to `-1234.56`;
    `"45.2%"` to `0.452` as a `ratio`; `""` and `None` to null.
12. `"not a number"` in a `money` field yields null **and** a `CoercionIssue`
    carrying the sheet, cell reference, field, raw value and dtype.
13. A CCN of `"014001"` survives extraction as the string `"014001"`, leading
    zero intact.
14. `ownership_category` maps from its aliases to one of the four canonical
    values, and an unrecognized value becomes `unknown` with a coercion issue.
15. `ownership.from: constant` assigns the same category to every row on that
    sheet.
16. Optional fields absent from the workbook are present in the frame as
    all-null columns of the right dtype, so checks never have to test for
    column existence.
17. `provenance` has the same shape and index as `frame`, and each populated
    cell holds `"<sheet>!<column letter><row>"`.
18. Extracting the same workbook twice produces equal frames.
19. Rows from several demonstration sheets concatenate into one frame with a
    `source_sheet` column preserved.
20. `upl extract` against an unverified mapping prints a warning saying so.
21. `upl_gap` is **not** computed by the extractor when absent from the
    workbook. The extractor reports what the workbook says; recomputation is a
    check's job, and computing it here would make `ARI004` tautological.

## Out of scope

- Any check. This spec produces the data checks run against.
- Writing back to a workbook.
- The supplemental payment second input (SPEC for `SUP`, later).
- A verified inpatient mapping. What ships here is provisional.

## Open questions

1. Whether the real template splits ownership categories across separate tabs
   rather than a column. Both shapes are supported (`ownership.from`), but
   which one occurs should be recorded after phase 0.
2. Whether the demonstration tab carries one row per provider or one row per
   provider-and-cost-report-period. The grain assumed here is the former.
   **Flag it if the real template says otherwise** — it changes the natural key
   and therefore every year-over-year check.
3. Whether `upl_gap` appears in the template at all, or is only in the summary.
