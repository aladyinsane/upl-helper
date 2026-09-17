# SPEC-0004: Check engine, findings and the first check families

Implements ADR-0001, phase 2, plus the parts of phase 3 that need no external
data.

## Goal

A registry of independent checks that run against the canonical model and emit
findings as data, with severities, stable fingerprints, waivers and reports.
Plus a first real catalog: arithmetic, plausibility, identifiers and the
aggregate policy test.

## Context & constraints

- Depends on SPEC-0003. Checks read the canonical frame, its provenance frame
  and the extraction report. Nothing reads a workbook directly.
- No network. No reference data. Everything here runs offline against one
  extraction.
- `STR` (template conformance) is deliberately **not** in this spec: it reads a
  SPEC-0002 descriptor rather than the canonical frame, and needs a real
  template to be worth writing.

## Design

### Findings are data

A check never prints. It yields `Finding` records, which the reporting layer
renders. This is what makes waivers, JSON output and annotated workbooks
possible without every check knowing about them.

```python
Finding(
    check_id="ARI004",
    severity=Severity.ERROR,
    scope=Scope.PROVIDER,      # RUN | SHEET | PROVIDER | CELL
    subject="014001",          # the provider key, or "" for run-scoped
    field="upl_gap",
    message="...",
    observed=1234.0,
    expected=1200.0,
    cell="Cost Based Demonstration!R12",
)
```

### Fingerprints

`fingerprint = sha256(check_id | subject | field)[:16]`

Deliberately **not** including the observed value. A waiver should survive next
year's slightly different number for the same known-acceptable provider;
otherwise every waiver expires the moment the data moves and the feature is
useless.

### Waivers

```yaml
waivers:
  - fingerprint: "a1b2c3d4e5f60718"    # or: check_id + subject
    reason: "Provider closed mid-year; CMS was notified in the SFY23 filing."
    expires: 2027-06-30
```

- `reason` is **required and non-empty**. A waiver with no reason is a
  validation error, not a quiet suppression.
- `expires` is **required**. A waiver file is where real problems go to be
  forgotten; a date forces the question to come back.
- An expired waiver does not suppress. It surfaces the finding *and* adds a
  `WAIVER_EXPIRED` finding naming it.
- Waived findings are counted and listed separately, never silently dropped.

### Severity and exit codes

`ERROR` — wrong, or would be rejected. `WARN` — needs an explanation.
`INFO` — context. `SKIPPED` is a check outcome, not a severity: a check that
cannot run says so with a reason and never passes silently.

`upl check` exits 1 if any unwaived `ERROR`, else 0.

### Thresholds are configuration

Every bound — CCR range, outlier sensitivity, variance tolerance — lives in a
YAML thresholds file, not in code. States differ, and a threshold nobody can
tune gets ignored instead of fixed.

## Check catalog

Tolerance for all money comparisons: `abs_tol` from thresholds, default `0.01`.

### ARI — arithmetic

| id | severity | checks |
|---|---|---|
| `ARI004` | ERROR | `upl_gap == upl_amount - medicaid_payments_total` |
| `ARI005` | ERROR | `medicaid_payments_total == supplemental + (base * medicaid_trend_factor * medicaid_other_adjustment_factor)` |
| `ARI006` | WARN | `medicaid_cost == medicaid_charges * cost_to_charge_ratio` |

Each skips a row where any input is null, and reports how many rows it could
not evaluate.

### PLA — plausibility

| id | severity | checks |
|---|---|---|
| `PLA001` | WARN | `cost_to_charge_ratio` outside `[ccr_min, ccr_max]` |
| `PLA005` | ERROR | negative value in a field that cannot be negative |
| `PLA008` | WARN | provider payments exceed that provider's UPL |
| `PLA009` | WARN | per-unit outlier by modified z-score (MAD) |
| `PLA010` | INFO | leading-digit distribution departs from Benford |
| `PLA011` | ERROR | the same provider key appears on more than one row |

`PLA009` uses the modified z-score (`0.6745 * (x - median) / MAD`) rather than
a standard z-score, because a mean and standard deviation are dragged around by
the very outliers being looked for. MAD of zero means no spread; the check
skips rather than dividing by zero.

`PLA010` needs enough rows to mean anything and skips below
`benford_min_rows` (default 50). It is `INFO` on purpose — a Benford departure
is a reason to look, never a finding on its own.

### IDN — identifiers

| id | severity | checks |
|---|---|---|
| `IDN001` | ERROR | CCN is 6 characters, and its last 4 are digits |
| `IDN002` | WARN | CCN state prefix matches the state being filed |
| `IDN003` | WARN | CCN facility-type range fits the provider type |
| `IDN004` | ERROR | NPI is 10 digits and passes the Luhn check with prefix 80840 |

`IDN004` is the cheapest real check in the suite: it needs no reference data at
all and catches transposed digits outright.

`IDN002` and `IDN003` depend on reference tables (SSA state codes, CCN facility
ranges) that **could not be verified from the environment this was written
in**. Both tables ship marked `verified: false`, and while unverified **the
checks do not run** — they report `SKIPPED` with the reason. A check that
invents findings from a table nobody has checked is worse than no check.

### POL — policy

| id | severity | checks |
|---|---|---|
| `POL002` | ERROR | within each ownership category, aggregate payments must not exceed aggregate UPL |

This is the actual legal test, and it is aggregate, not per provider. A single
provider over its own UPL is `PLA008` at `WARN`; the category being over is
`POL002` at `ERROR`.

## Data contracts

### `CheckContext`
```python
frame: pd.DataFrame          # canonical, from SPEC-0003
provenance: pd.DataFrame
extraction_report: ExtractionReport
context: ExtractionContext | None
thresholds: Thresholds
reference: ReferenceTables
```

### `CheckResult`
```python
check_id: str
status: "ran" | "skipped"
skip_reason: str | None
findings: list[Finding]
rows_evaluated: int
rows_not_evaluated: int
```

### `RunResult`
```python
results: list[CheckResult]
findings: list[Finding]          # unwaived
waived: list[WaivedFinding]
expired_waivers: list[Finding]
counts: {error: int, warn: int, info: int, waived: int, skipped: int}
```

## CLI

```
upl check WORKBOOK -m MAPPING [--state XX] [--year YYYY]
                   [--thresholds PATH] [--waivers PATH]
                   [--include FAMILY]... [--format text|json] [-o PATH]
```

## Validation / acceptance criteria

1. A check that raises is reported as a failed check, not a crashed run; other
   checks still run.
2. `ARI004` flags a row whose stated gap disagrees with `upl - payments` by
   more than the tolerance, and passes one that agrees within it.
3. `ARI004` does not evaluate rows where either input is null, and reports the
   count under `rows_not_evaluated`.
4. `ARI005` flags inflated base + supplemental not summing to total; the
   trend and adjustment factors default to `1.0` (CMS's own "no change"
   convention) when a mapping does not supply them, which collapses the
   check to a plain footing sum.
5. `PLA005` flags a negative `medicaid_days` and a negative `upl_amount`.
6. `PLA008` flags a provider whose payments exceed its UPL, at `WARN`.
7. `POL002` flags an ownership category whose aggregate payments exceed its
   aggregate UPL, at `ERROR`, and is silent when one provider is over but the
   category is not.
8. `PLA011` flags a duplicated provider key and names both rows.
9. `PLA009` flags a provider whose cost per day is far from the median, and
   skips entirely when MAD is zero.
10. `PLA010` skips below `benford_min_rows`.
11. `IDN004` accepts a valid NPI and rejects one with two digits transposed.
12. `IDN001` rejects a 5-character CCN and one whose last four are not digits.
13. `IDN002` and `IDN003` report `SKIPPED` while their reference tables are
    unverified, and run when given a verified table.
14. The same finding has the same fingerprint across two runs, **including when
    the observed value changes**.
15. A waiver with a matching fingerprint suppresses the finding, and it appears
    in `waived`.
16. A waiver with no `reason` fails to load, naming the waiver.
17. A waiver with no `expires` fails to load.
18. An expired waiver does not suppress, and produces a `WAIVER_EXPIRED`
    finding.
19. A waiver by `check_id` + `subject` matches without a fingerprint.
20. `upl check` exits 1 when there is an unwaived `ERROR` and 0 otherwise; a
    waived `ERROR` does not cause exit 1.
21. Thresholds load from YAML and change behavior: widening `ccr_max` silences
    a `PLA001` finding.
22. JSON output round-trips every finding with its fingerprint.
23. A check needing a field that the workbook did not supply reports `SKIPPED`
    naming the field, rather than flagging every row.

## Out of scope

- `STR`, which needs a descriptor and a real template.
- `YOY`, `UNI`, `EXT` — prior-year and reference data.
- `SUP` — its own spec.
- The annotated-workbook report. Text and JSON only here.

## Open questions

1. ~~The CCR plausible range is guessed (`0.05`–`1.20`). Real state data should
   set it.~~ **Resolved 2026-09-17:** `ccr_min` (`0.05`) is still a guess.
   `ccr_max` is raised to `3.00` on Lauren's domain knowledge of real state
   data — `1.20` was too tight.
2. Whether `POL002` should test each ownership category separately or also in
   total depends on how the state's SPA words it. Category-level is the
   conservative reading.
