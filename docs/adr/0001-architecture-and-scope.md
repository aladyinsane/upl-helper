# ADR-0001: Architecture and scope for the UPL check suite

- **Status:** Proposed
- **Date:** 2026-09-17
- **Deciders:** Lauren

## Context

State Medicaid agencies submit annual UPL demonstrations to CMS on standard
Excel templates, one per provider type. Existing programs already produce the
numbers and the supplemental payment amounts. What is missing is a systematic
way to check that output before it goes to CMS. Today that check is manual
review, which does not scale across provider types, states and years, and does
not catch the class of error that looks reasonable on its face — a provider
quietly missing from the universe, a CCN that changed at a change of
ownership, a cost-to-charge ratio carried forward from a superseded cost
report.

Four constraints shape this more than anything else.

**The template cannot be inspected from here.** `medicaid.gov`, all
`*.cms.gov`, `healthdata.gov`, Census and BLS are blocked by egress policy in
the environment this is being built in. The real CMS workbooks live in a work
environment that has no access to this assistant, and files cannot be handed
across. So nothing can be written against an inspected copy of the template.

**CMS revises the templates.** Columns have moved between versions and a PDPM
tab was added to the nursing facility template. Newer templates are
distributed through MACFin rather than the public download page. Anything
bound to fixed cell addresses breaks on the next revision.

**The workbooks are protected.** Locked cells, hidden sheets, hidden columns.
Reading them is possible but the reader has to expect protection rather than
fail on it.

**Development continues elsewhere.** The next passes happen on a work laptop,
possibly with a different agent or by hand. Whatever is built has to be
legible and runnable without this session's context.

Scope for the first pass, decided with Lauren:

- Input is the completed CMS workbook, the artifact that actually gets
  submitted. Upstream source data adapters are possible later.
- Inpatient hospital is the first provider type end to end.
- Python with pandas and openpyxl. Normal `pip install` is available.
- The work environment can reach CMS sites, so reference data can be fetched
  there even though it cannot be fetched here.

## Decision

Build `upl-helper` as a Python package with a CLI, structured in five layers,
where **checks bind to a canonical data model rather than to spreadsheet cell
addresses**, and **template layout is supplied as data rather than code**.

### 1. Template profiler

A `upl profile <workbook>` command that reads a real CMS workbook and emits a
structural descriptor: sheet names and visibility, used ranges, header rows,
column headers in order, cell formulas as strings, protection state, named
ranges, data validation rules.

The descriptor carries structure and formulas only — **no cell values** — so
it is safe to commit to this repository even though the workbook it came from
is not.

This is what unblocks everything else. Lauren runs it once in the work
environment against the real template, commits the descriptor, and the rest of
the suite can be built and tested anywhere against a faithful description of a
file that was never copied.

### 2. Template mapping, as data

Each template version and provider type gets a YAML mapping in
`config/templates/`: which tabs hold demonstration rows, where the header row
is, and for each canonical field, the set of header strings that have meant
that field across template versions. Columns are located by header text, not
by position.

A new CMS template revision is a new YAML file, not a code change.

### 3. Canonical model

The extractor turns any mapped workbook into the same tidy tables regardless
of template version: one provider-period row per record, with normalized
identifiers, ownership category, units, costs, charges, payments, UPL and gap.
Every check is written against this model.

This is the load-bearing decision. It means a template revision, a second
provider type, or eventually an upstream data source can all feed the same
check catalog.

### 4. Check engine

A registry of independent checks, each with a stable ID, a severity
(`ERROR` / `WARN` / `INFO`), and a declared dependency on reference data if it
needs any. Checks emit `Finding` records — check ID, severity, the provider or
cell it concerns, observed vs expected, and evidence — not printed text.

Findings get a deterministic fingerprint from the check ID plus the subject
key, which makes a `waivers.yaml` possible: a known-acceptable finding can be
suppressed with a written reason and an expiry date. Without waivers a check
suite that emits four hundred rows gets ignored after the first run.

A check whose reference data is unavailable reports `SKIPPED` with the reason.
It does not fail and it does not silently pass.

### 5. Reference data cache

Source adapters fetch published federal datasets into a dated local snapshot
under `data/refdata/<source>/<snapshot-date>/`, with a manifest recording
source URL, retrieval time and checksum. Adapters support both direct fetch
and sideloading a manually downloaded file, since one environment can reach
CMS and the other cannot.

Checks read the cache. **No check requires a live network call.** Reference
data is versioned and dated so a prior year's demonstration can be re-checked
against the data as it stood, not as it stands now.

### Testing: synthetic workbooks with injected defects

Real submissions cannot go in this repository. So the suite is tested against
generated workbooks: a fixture generator builds a synthetic UPL workbook from
the template mapping, and a mutation library injects specific known defects —
a dropped provider, a total that does not foot, a transposed CCN, a CCR
carried over from the wrong cost report period, a stale terminated provider.

Every check ships with at least one fixture that must trigger it and one that
must not. This is how we know the checks work, and it is the only way to prove
it without real data.

### Check catalog

Seven families. Full detail goes in the specs; this is the shape.

| Family | Covers | Needs external data |
|---|---|---|
| `STR` | Template conformance — tabs, columns, formulas not overwritten with hardcoded values, numbers stored as numbers | No |
| `ARI` | Arithmetic — every derived value independently recomputed, totals foot, summary ties to detail, gap equals UPL minus payments | No |
| `PLA` | Plausibility — CCR and per-unit ranges, days against bed capacity, charges against payments, robust outlier detection, Benford screen, duplicate and near-duplicate providers | No |
| `IDN` | Identifier integrity — CCN format and state prefix, facility-type range, NPI check digit, CCN/NPI pairing, change-of-ownership detection | Some |
| `YOY` | Year over year — aggregate and provider-level variance, CCR drift, ownership mix shift, movement against the applicable update factor | Prior year workbook |
| `UNI` | Provider universe — is every provider that should be in the demonstration actually in it, and is every provider in it real and active | Yes |
| `EXT` | External reasonableness — CCR recomputed from HCRIS, Medicaid days against the cost report, totals against CMS-64, spot-repricing against published Medicare rates, trend factor against published update factors | Yes |
| `POL` | Policy conformance — demonstration present per ownership category, aggregate payments within aggregate UPL, supplemental payments within the gap, methodology consistent with the approved SPA | Some |

`STR`, `ARI` and `PLA` deliver real value with no external data at all, which
is why they come first.

### Phasing

Each phase is its own spec and PR.

1. Profiler, canonical model, template mapping format, fixture generator.
   Deliverable: a command Lauren can run at work immediately.
2. Check engine, findings, waivers, reporting. Families `STR`, `ARI`, `PLA`.
3. Families `IDN` and `YOY`. Needs a prior-year workbook, nothing external.
4. Reference data layer, then `UNI` and `EXT`.
5. `POL`, reporting polish, second provider type to prove the model holds.

## Alternatives considered

### Do nothing — keep manual review
- Pros: no build cost; reviewers have domain judgment a tool does not.
- Cons: does not scale across provider types, states and years; the errors
  that survive manual review are exactly the ones that look reasonable; no
  record of what was checked.
- Why not chosen: this is the problem being solved.

### Checks inside the workbook, as formulas or VBA
- Pros: nothing to install; analysts see results next to the numbers;
  familiar to the people doing the work.
- Cons: the templates are protected, so adding anything fights the protection
  and risks invalidating the submission; not version controlled; not testable;
  has to be rebuilt by hand on every template revision; cannot reach external
  reference data.
- Why not chosen: untestable and unmaintainable, and it touches the artifact
  being submitted.

### Bind checks directly to known cell addresses
- Pros: simplest possible extractor; fastest to write.
- Cons: breaks on every CMS template revision, and CMS has already moved
  columns between versions. Also literally impossible from this environment,
  since the template cannot be inspected.
- Why not chosen: ruled out by both the maintenance cost and the constraint.

### Reimplement the UPL calculation and compare end to end
- Pros: strongest possible check — an independent answer to compare against.
- Cons: a second system of record, with all the upstream data dependencies of
  the first; disagreements become arguments about which implementation is
  right rather than findings; far larger build; would need methodology
  coverage for every provider type before it is useful at all.
- Why not chosen: too large for now, and it changes what this project is.
  Note that `EXT` spot-repricing is a deliberately bounded slice of this —
  reprice a sample, not the whole demonstration.

### Fetch reference data live at check time
- Pros: always current; no cache to manage.
- Cons: checks become non-deterministic and unrunnable offline; re-checking a
  prior year gives different answers than it did at submission; a CMS site
  outage breaks the suite.
- Why not chosen: dated snapshots are strictly better for anything that has to
  be defensible after the fact.

## Consequences

**Makes easy:**
- Adding a provider type: a mapping file and a handful of type-specific checks.
- Surviving a CMS template revision: a new mapping file.
- Building and testing here, without ever touching real data.
- Re-checking a prior year against the reference data as it stood then.
- Handing this off — the profiler output, the mapping files and the fixtures
  document the real template better than prose would.

**Makes hard, or costs:**
- Two layers of indirection between the spreadsheet and the checks. Debugging
  "why did this column not map" is a real category of problem, and the
  profiler output is the tool for it.
- The canonical model has to be right early. Getting it wrong means reworking
  checks later. Inpatient hospital first is partly a hedge: it is the richest
  template, so a model that fits it should stretch to the others.
- Synthetic fixtures test the checks, not the template mapping. Until the
  profiler runs against a real workbook, the mapping is a guess. That gap
  closes the first time Lauren runs `upl profile` at work.
- Reference data adapters depend on file layouts nobody here has seen. The
  inventory in `docs/research/reference-data-sources.md` is design intent and
  needs confirming before phase 4.
- A waiver file is a place for real problems to go and be forgotten. Expiry
  dates are mandatory for that reason.

**Locks us into:**
- Python, pandas, openpyxl.
- Findings as data, which means the reporting layer is separate and swappable
  but also means there is always a reporting layer to maintain.

## Related

- `docs/research/reference-data-sources.md` — candidate external sources
- `DEV_WORKFLOW.md` — the ADR/spec/PR loop this follows
- SMDL 13-003 — annual UPL demonstration requirement
- 42 CFR 447.272 and 447.321 — aggregate UPL for inpatient hospital, and for
  outpatient hospital and clinic services
