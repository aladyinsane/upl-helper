# Using upl-helper

Practical notes for running this against a real workbook. For what the
project is and why, see `README.md` and `docs/adr/0001-architecture-and-scope.md`.
For what's built vs. not, see `docs/HANDOFF.md`.

## Setup

Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate    # if not Windows: source .venv/Scripts/activate
pip install -e ".[dev]"
```

Sanity check:

```bash
pytest -q
ruff check .
```

Both should be clean. If they aren't, something is wrong with the checkout,
not with your workbook — fix that first.

## What's usable today

- **Provider type: inpatient hospital only.** The other seven templates are
  downloaded (`templates/upl-2022/`) but have no mapping yet.
- **Check families that run: `ARI`, `PLA`, `IDN`, `POL`.** `STR`, `YOY`,
  `UNI`, `EXT`, `SUP` aren't implemented — see `docs/HANDOFF.md`.
- **`IDN002` and `IDN003` don't run yet even though they're implemented** —
  they depend on CCN reference tables (`config/reference/ccn-tables.yaml`)
  written from memory and marked `verified: false`. Both report `SKIPPED`
  until someone confirms the tables against a real CMS source and flips that
  flag. Your work environment can reach CMS; this is a good first task there
  — see the file's own header for exactly what to check.

## The three commands you'll actually use

### `upl profile` — look at a workbook's structure, no values

```bash
upl profile path/to/real_submission.xlsx -o descriptor.yaml
```

Reads sheet names, headers, formulas, protection state, data validation —
never cell values. Safe to commit even when the workbook it came from isn't
(see the ADR's commit policy). Use `--sheet "IP Cost"` to scope it to one
tab when you just want to sanity-check that sheet.

Use this if you suspect a workbook doesn't match the shipped mapping — a new
CMS template revision, a state that customized a tab, etc. Compare the
descriptor's `header_normalized` values for the sheet against the aliases in
`config/templates/inpatient-hospital-2022.yaml`.

### `upl extract` — read a workbook into the canonical table, no checks

```bash
upl extract path/to/real_submission.xlsx \
  -m config/templates/inpatient-hospital-2022.yaml \
  --state IL --year 2026 \
  -o extracted.csv
```

Useful on its own when you want to eyeball what got read before trusting any
check result. Prints a summary to stderr: rows extracted per sheet, sheets
the mapping didn't cover, columns on a mapped sheet the mapping didn't claim,
required-adjacent fields that came up empty. Read that summary before the
CSV — it tells you whether the extraction itself is trustworthy.

Against the *blank* reference template in `templates/upl-2022/`, this
correctly extracts **zero rows** — there's no data in it. Point it at an
actual filled submission to see real rows.

### `upl check` — extract, then run the check suite

```bash
upl check path/to/real_submission.xlsx \
  -m config/templates/inpatient-hospital-2022.yaml \
  --state IL --year 2026
```

```
SKIP  ARI004: no data for: upl_gap, upl_amount, medicaid_payments_total
...
1 check(s) ran, 13 skipped, 0 broke | 0 error, 0 warn, 0 info, 0 waived
```

That's the output against the blank template — everything with a required
field skips, because there's nothing to check. Against a real filled
submission you should see checks actually run and either pass silently or
emit findings.

Useful flags:

- `--thresholds path.yaml` — override `ccr_min`/`ccr_max`/outlier
  sensitivity/etc. Copy `config/thresholds/default.yaml` and edit; unknown
  keys are a hard error, so a typo doesn't get silently ignored.
- `--waivers path.yaml` — suppress a specific known-acceptable finding.
  Copy `config/waivers.example.yaml`. Every entry needs a `reason` and an
  `expires` date, both enforced at load. An expired waiver stops suppressing
  and surfaces the finding again, plus a note that it lapsed.
- `--reference config/reference/ccn-tables.yaml` — wires up `IDN002`/`IDN003`.
  They still won't run until the file's `verified: false` is flipped — see
  above.
- `--include ari` (repeatable) — limit to one family. Case-insensitive.
- `--format json -o report.json` — machine-readable output instead of the
  text summary. Same information, one JSON object per check with its
  findings.

Exit code is `1` if any unwaived `ERROR` finding exists, `0` otherwise —
wire this into a script if you want a hard gate.

## `upl unprotect` — optional, for looking at a workbook by eye

```bash
upl unprotect path/to/real_submission.xlsx -o unprotected.xlsx --unhide
```

`extract` and `check` read protected workbooks directly — Excel's sheet/
workbook protection restricts UI editing, not programmatic reads, so you
never need this for the pipeline to work. Use it only when you want to open
the workbook yourself in Excel and look at hidden sheets or locked cells
(`_Controls`, `LKUP`, the `Optional_Sheet_N` tabs) without fighting the
protection.

## Data handling — this matters

**Never commit a real submission, or anything derived from provider-level
payment data, to this repository.** `.gitignore` blocks `*.xlsx` outside
`templates/` and `tests/fixtures/`, and blocks `data/real/` and
`data/incoming/` outright — that's deliberate, not a bug to work around. If
you need to keep extracted CSVs or check reports for your own records, put
them outside this repo.

The blank CMS reference templates under `templates/upl-2022/` are fine to
use as workbook arguments for testing the tool itself (structure only, no
provider data) but will never produce a meaningful check result — they exist
for exactly the kind of structural sanity-checking `upl profile` does, not
for validating a demonstration.
