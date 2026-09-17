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

**Development happens across environments with different reach.** There is no
single environment that has everything. At minimum there are three:

| | Reaches CMS | Has real filled workbooks | Reaches this assistant |
|---|---|---|---|
| Claude Code web (this one) | No — `medicaid.gov`, all `*.cms.gov`, `healthdata.gov`, Census and BLS are blocked by egress policy | No | Yes |
| Other development environments | Varies — some can | No | Varies |
| Work environment | Yes | Yes | No |

Nothing can be assumed reachable at any given moment, and the real filled
workbooks never leave the work environment at all. So **acquisition and
checking have to be separable**: acquiring a template, a reference dataset or
a prior-year workbook may require network and may have to happen somewhere
else, while running checks must never require either.

This is a weaker constraint than "nothing can be inspected", which is what an
earlier draft assumed. Where an environment can reach CMS, it should be used
to retire unknowns early rather than working around them. See *Sequencing*
below.

**CMS revises the templates.** Columns have moved between versions and a PDPM
tab was added to the nursing facility template. Newer templates are
distributed through MACFin rather than the public download page. Anything
bound to fixed cell addresses breaks on the next revision.

**The workbooks are protected.** Locked cells, hidden sheets, hidden columns.
Reading them is possible but the reader has to expect protection rather than
fail on it.

**Development continues elsewhere.** Later passes happen in other environments,
possibly with a different agent or by hand. Whatever is built has to be
legible and runnable without this session's context, and has to record what it
learned about the real templates and datasets rather than leaving that
knowledge in a conversation.

Scope for the first pass, decided with Lauren:

- Input is the completed CMS workbook, the artifact that actually gets
  submitted. Upstream source data adapters are possible later.
- Inpatient hospital is the first provider type end to end.
- Python with pandas and openpyxl. Normal `pip install` is available.
- The work environment can reach CMS sites, so reference data can be fetched
  there even though it cannot be fetched here.
- One state per run. Multi-state is running the tool more than once.
- Checking the supplemental payment calculation is in scope, but as a
  separate opt-in family rather than part of the default run.

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
it is safe to commit even when the workbook it came from is not.

Commit policy follows from that:

- A **blank official CMS template** downloaded from a public CMS source is not
  sensitive. Commit the workbook itself, under `templates/`, and the mapping
  built from it.
- A **filled workbook** — a real submission, current or prior year — never
  leaves its environment. Run the profiler against it and commit only the
  descriptor.

The profiler earns its place for three reasons, not one:

1. It is the only way to work against a template that exists solely in an
   environment this assistant cannot reach — including the MACFin-distributed
   versions that may not be publicly downloadable at all.
2. It diffs a workbook against the template version a mapping was built for,
   which is how a CMS revision gets detected rather than silently mis-mapped.
3. It is the input to authoring a new mapping, wherever that happens.

Only the first of those depended on the old "nothing can be inspected"
assumption. The other two hold regardless.

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

### 4. Run scope: one state, one demonstration

A run takes one state, one provider type and one demonstration year. The state
is a run-level parameter, not a column in the canonical model, so nothing has
to carry a state dimension and no check has to reason about cross-state
aggregation. The state parameter is what drives CCN prefix validation, the
provider universe filter, and CMS-64 lookup.

Checking several states means several runs and several reports. If a rollup
across states is ever wanted, it consumes the JSON findings output rather than
being built into the engine.

### 5. Supplemental payments as a separate opt-in family

The supplemental payment calculation — the gap between the demonstrated UPL
and actual Medicaid payments, distributed to providers — is checked by its own
`SUP` family, and that family is **off by default**. Three reasons it stays
separate rather than folded into the main run:

- The demonstration and the payment calculation are different artifacts with
  different review audiences. A UPL demonstration can be correct while the
  payment allocation built on it is wrong, and the reverse.
- The payment calculation often lives in a different file than the CMS
  template. `SUP` checks take an optional second input and report `SKIPPED`
  when it is not supplied.
- `SUP` results are only meaningful if the UPL underneath them is sound. When
  the run has unresolved `ARI` or `PLA` errors, `SUP` findings are reported
  with an explicit note that the inputs they depend on are themselves
  suspect — otherwise a single upstream error produces a cascade of downstream
  noise that buries it.

Enabled with `--include sup` or by configuration.

### 6. Check engine

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

### 7. Reference data cache

Source adapters fetch published federal datasets into a dated local snapshot
under `data/refdata/<source>/<snapshot-date>/`, with a manifest recording
source URL, retrieval time and checksum. Adapters support both direct fetch
and sideloading a manually downloaded file, since one environment can reach
CMS and the other cannot.

Checks read the cache. **No check requires a live network call.** That is not a
workaround for a blocked environment — it stands on its own. Live fetching
would make checks non-deterministic, make a re-check of a prior year give a
different answer than it gave at submission, and make a CMS site outage break
the suite. Dated snapshots are the right design even in an environment that
could fetch freely.

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
| `POL` | Policy conformance — demonstration present per ownership category, aggregate payments within aggregate UPL, methodology consistent with the approved SPA | Some |
| `SUP` | Supplemental payments, **opt-in** — payment within each provider's gap, allocation formula independently recomputed, allocation shares foot to one, no payment against a zero or negative gap, sum of payments equals the stated total, non-federal share source identified, year-over-year payment variance | Optional second input |

`STR`, `ARI` and `PLA` deliver real value with no external data at all, which
is why they come first. `SUP` is the only family that is off unless asked for.

### Sequencing

Each phase is its own spec and PR, except phase 0.

**Phase 0 — acquisition reconnaissance.** Runs in whichever environment can
reach CMS. Not a spec; a scripted errand whose output is committed evidence.

- Probe and record what is actually reachable from that environment. The
  answer goes in the repo, because it determines what later phases can assume.
- Download the blank inpatient hospital template and its narrative
  instructions. Commit them.
- Pull one snapshot of each candidate reference dataset in
  `docs/research/reference-data-sources.md` and record its **real** schema —
  actual column names, keys, grain, coverage, update cadence, file size.
- Note which sources turn out to be unusable, and why.

This is deliberately first. The largest design risk in this ADR is that the
external reference sources do not contain what the `UNI` and `EXT` checks
assume they contain — that inventory was written without being able to open
any of them. If that is wrong, it is better to find out before the canonical
model is fixed than after the checks are written against it. Everything else
in the sequence is robust to being wrong; this is not.

**Phase 1 — profiler, canonical model, template mapping format, fixture
generator.** Now authored against the real blank template from phase 0 rather
than against a guess, with the profiler still carrying the filled-workbook and
version-diff cases.

**Phase 2 — check engine, findings, waivers, reporting.** Families `STR`,
`ARI`, `PLA`. Full value with no external data.

**Phase 3 — `IDN` and `YOY`.** Needs a prior-year workbook. Nothing external
beyond what phase 0 confirmed.

**Phase 4 — reference data adapters, then `UNI` and `EXT`.** Written against
the real schemas recorded in phase 0.

**Phase 5 — `POL` and `SUP`.** `SUP` needs its own spec: allocation methods
vary by state and the second input format is not yet known.

**Phase 6 — reporting polish, then a second provider type** to prove the
canonical model stretches.

Phases 1–3 need no network at all and can proceed in parallel with phase 0 if
that is convenient. Phase 4 is the only one that is genuinely blocked on it.

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
  columns between versions. Each break is silent — a shifted column reads a
  plausible number from the wrong field rather than erroring.
- Why not chosen: the maintenance cost alone rules it out. An earlier draft
  also cited the inability to inspect the template from this environment;
  that turns out to be environment-specific and is not the reason.

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
  profiler runs against a real workbook, the mapping is a guess. Phase 0
  closes most of that gap by getting a real blank template; the rest closes
  the first time the profiler runs against a filled one.
- Reference data adapters depend on file layouts nobody here has seen. The
  inventory in `docs/research/reference-data-sources.md` is design intent, not
  verified fact, and phase 0 exists specifically to verify it. If several
  sources turn out not to hold what is assumed, `UNI` and `EXT` shrink and
  this ADR needs revisiting rather than patching.
- Phase 0 has no automated test and produces documentation rather than code,
  which makes it the phase most likely to be skipped or done halfway. Its
  output is committed evidence for exactly that reason.
- A waiver file is a place for real problems to go and be forgotten. Expiry
  dates are mandatory for that reason.

**Multiple environments cost us:**
- A per-environment story for what is reachable, and the discipline to keep it
  recorded in the repo rather than in someone's head.
- Acquisition steps that cannot be run or tested from the environment where
  most of the code gets written. Phase 0 output is the mitigation: once the
  real schemas are written down, the adapters built against them are ordinary
  testable code with fixture inputs.

**Single state per run costs us:**
- Nothing today, and it keeps the canonical model and every check simpler. The
  cost only shows up if a cross-state view is ever wanted, and at that point
  the JSON findings output is the seam to build it on.

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
