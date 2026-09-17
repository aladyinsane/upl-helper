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

`extract_path` opens the workbook with `data_only=True`, unlike the profiler's
`data_only=False`. Some real templates compute every demonstration cell by
formula from a separate input sheet, so extraction needs the last-calculated
value Excel cached at save time, not the formula string. This only matters
against a real filled workbook; the synthetic fixtures used in tests write
literal values, so it is invisible against them.

The first data row is `data_rows.start_row` if the mapping sets it, else
`max(header_rows) + 1`. Most templates need no override — data starts right
below the header — but some put non-data content (instructions, examples)
between the two, which `start_row` exists to skip past explicitly rather than
guess at.

Walks data rows beneath that point. A row is skipped when:

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
| `cost_to_charge_ratio` | ratio | no | CCR, cost-based methodology |
| `payment_to_charge_ratio` | ratio | no | PTC, payment-based methodology's analog to the CCR |
| `medicaid_cost` | money | no | the UPL basis |
| `upl_trend_factor` | ratio | no | inflates the calculated UPL basis; distinct from `medicaid_trend_factor` |
| `upl_amount` | money | yes | |
| `medicaid_payments_base` | money | no | |
| `medicaid_trend_factor` | ratio | no | inflates base payments only, not supplemental; distinct from `upl_trend_factor` |
| `medicaid_other_adjustment_factor` | ratio | no | non-inflation adjustment (e.g. volume), applied alongside `medicaid_trend_factor` to base payments only |
| `medicaid_payments_supplemental` | money | no | |
| `medicaid_payments_total` | money | yes | not a plain sum where trend/adjustment factors apply — see `ARI005` in SPEC-0004 |
| `upl_gap` | money | no | `upl_amount - medicaid_payments_total` where present |

`trend_factor` (single, ambiguous) from the original table was split into
`medicaid_trend_factor` and `upl_trend_factor` on 2026-09-17, once the real
inpatient hospital template showed CMS tracks two independent inflation
factors per provider row (variables 308 and 405) — one for the Medicaid
payment side, one for the UPL side. Nothing consumed the single field before
the split, so this was a clean rename, not a breaking change.

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
      start_row: int                       # optional, else header_rows.max + 1
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
9a. `data_rows.start_row`, when set, is used as the first data row instead of
    `max(header_rows) + 1` — proven against a workbook with a non-data row
    between the header and the first real row, which the default would
    otherwise treat as the start of data (and, combined with
    `stop_on_blank_key`, silently extract zero rows from a workbook that has
    some).
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

1. ~~Whether the real template splits ownership categories across separate
   tabs rather than a column. Both shapes are supported (`ownership.from`),
   but which one occurs should be recorded after phase 0.~~ **Resolved
   2026-09-17:** ownership is a column (`ownership.from: column` was the
   right guess), with real values `Private` / `NSGO` / `SGO` (confirmed via
   the workbook's hidden `LKUP` sheet, not guessed). What the real template
   *does* split across separate tabs is demonstration methodology, not
   ownership: `IP Cost`, `IP Payment`, `IP DRG`, `IP Per Diem` each hold the
   provider rows using that methodology. A mapping needs one `SheetRule` per
   methodology tab, all `role: demonstration` — the extractor already unions
   every sheet sharing that role, so this needed no code change.
2. ~~Whether the demonstration tab carries one row per provider or one row
   per provider-and-cost-report-period. The grain assumed here is the
   former. Flag it if the real template says otherwise — it changes the
   natural key and therefore every year-over-year check.~~ **Resolved
   2026-09-17:** one row per provider, confirmed. A provider appears on
   exactly one of the four methodology tabs (whichever it uses for the
   demonstration year), so within one run's scope (one state, one provider
   type, one demonstration year, per ADR-0001) the assumed grain holds.
3. ~~Whether `upl_gap` appears in the template at all, or is only in the
   summary.~~ **Resolved 2026-09-17:** it appears at the provider-row level
   on each methodology tab, as "Adjusted UPL Gap" (CMS variable 409). The
   `UPL Demonstration Summary` tab only aggregates it (`SUMIF` by ownership
   category across the four tabs) — it is not the sole source.
