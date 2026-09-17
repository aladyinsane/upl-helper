# upl-helper: status

Newest first.

## 2026-09-17 — Phase 0: templates and guidance acquired

- A Claude Code desktop app session reached `medicaid.gov` directly — both
  the browser pane and shell `curl` — contradicting the egress block recorded
  for the earlier Claude Code web session. Reachability is per-session; see
  `docs/project/overview.md` hard constraints.
- Downloaded the full 2022-revision UPL reference document set from
  `medicaid.gov/medicaid/financial-management/payment-limit-demonstrations`
  for all 8 provider types (guidance PDF + blank `.xlsx` template each),
  plus SMDL 13-003, the UPL methodology summary, and the revised-template
  FAQ. Committed under `templates/upl-2022/` per the ADR-0001 commit policy
  (blank official templates are not sensitive). ~66 MB total.
- These are CMS's public reference copies, not the fillable MACFin versions —
  matches the ADR's expectation that MACFin-distributed templates may not be
  scriptable. Reference copies are enough to build the profiler and mapping
  against.
- Quick look at the inpatient hospital template (`openpyxl`, structure only):
  sheets are `State Attestation`, `Overview & Instructions`, `Data
  Dictionary`, `Required State Input – IPH`, `IP Cost`, `IP Payment`,
  `IP DRG`, `IP Per Diem`, `UPL Demonstration Summary`, 15 `Optional_Sheet_N`
  tabs, and two hidden sheets, `_Controls` and `LKUP`. Workbook structure
  protection is on. Confirms the ADR's hidden-sheet and protected-workbook
  assumptions; sheet names differ from anything guessed in the ADR text.
- Not yet done: phase 0's other half, confirming the real schemas of the
  external reference datasets in `docs/research/reference-data-sources.md`
  (POS, HCRIS, NPPES, etc.) — those still need checking from an environment
  that can reach them.
- Next: SPEC-0002 (profiler) can now be written against a real template
  instead of a guess.

## 2026-09-17 — SPEC-0004 written and implemented

- Check engine, findings, waivers, thresholds, reporting, and 13 checks across
  ARI, PLA, IDN and POL. 159 tests passing.
- Findings are data with stable fingerprints. The fingerprint deliberately
  excludes the observed value, so a waiver survives next year's number moving.
- Waivers require a reason and an expiry, both enforced at load. An expired
  waiver does not suppress; it surfaces the finding plus a note that it lapsed.
- Checks that cannot run report SKIPPED with a reason. They never pass quietly.
- IDN002/IDN003 depend on CCN reference tables written from memory. Those ship
  marked unverified and the checks **do not run** until someone confirms them.
- POL002 is the real legal test and is aggregate by ownership category; PLA008
  is the per-provider warning. Tested that one provider over its own UPL does
  not trip the aggregate check.
- Next: STR checks against a profiler descriptor, then the fixture generator,
  then phase 0 output lands and the provisional mapping gets replaced.

## 2026-09-17 — SPEC-0003 written and implemented

- Canonical model, template mapping format, and extractor. 109 tests passing.
- Checks will be written against 18 canonical fields at one row per provider
  per period. Columns resolve by normalized header text, never by position, so
  a CMS revision that moves columns needs no code change and one that renames
  a header needs one alias added.
- Ambiguity is an error, never a guess: two columns matching one field, or one
  alias under two fields, both fail loudly. Silently picking the leftmost is
  how a check ends up validating the wrong column.
- Every row carries provenance (`"Sheet!F12"`), so a finding can point at a
  cell.
- Found and fixed a real bug in SPEC-0002's header detection while testing
  this: a UPL data row is mostly text, so it scored nearly as well as the
  header above it and got joined as a second header row. Fixed by comparing a
  candidate's per-column shape against the rows below it, plus a scoring term
  for how many consistently shaped rows sit underneath. Two regression tests.
- `config/templates/inpatient-hospital-provisional.yaml` ships **unverified**.
  Phase 0 replaces it. `upl extract` warns on every run until it is verified.
- pandas is now a hard dependency.
- Next: fixture generator, then the check engine.

## 2026-09-17 — SPEC-0002 implemented

- `upl profile` and `upl unprotect` implemented, 72 tests passing.
- Every acceptance criterion in SPEC-0002 has a test. The redaction rule
  (AC-13, AC-14) is covered by canary tests in both output formats and both
  strict modes.
- One spec amendment: stage 3's entry point is `profile_columns` (plural,
  single pass) rather than per-column, which would have been quadratic in
  column count.
- Verified end to end: a 40-row column of formulas containing one hardcoded
  constant profiles as `formula: 39, numeric: 1` with a single formula
  pattern — the signal `STR003` will key on.
- Next: SPEC-0003, canonical model and template mapping.

## 2026-09-17 — ADR-0001 accepted, SPEC-0002 written

- Phase 0 reviewed and approved. ADR-0001 status flipped to **Accepted**.
- SPEC-0002 written: template profiler and unprotect utility.
- Python project scaffolding: `pyproject.toml`, `src/` layout, a CLI with
  decorator-based subcommand registration, ruff + pytest config, GitHub
  Actions CI on 3.11 and 3.12.
- Key design point in SPEC-0002: the descriptor carries no cell values except
  header text and formula strings, and that rule is enforced by a canary test
  rather than by convention, because descriptors get committed publicly while
  the workbooks they describe contain real payment data.
- Next: implement SPEC-0002.

## 2026-09-17 — ADR-0001 revised after review

- Review point: the no-network constraint is specific to the Claude Code web
  environment, not to development generally. Other environments can reach CMS.
- Reworked the ADR's context around an environment matrix instead of a single
  blocked environment. Acquisition and checking are now explicitly separable —
  acquisition may need network and may happen elsewhere; checking never does.
- Added **phase 0, acquisition reconnaissance**, ahead of everything: from a
  networked environment, download the blank inpatient template, and confirm
  the real schemas of the candidate reference datasets. The reference source
  inventory was written blind and is the largest design risk in the ADR.
- Separated justifications that were leaning on the constraint from ones that
  stand on their own. Offline checking and header-based column mapping are
  right regardless of network; only "the profiler is the only way to see the
  template" was constraint-dependent, and the profiler has two other reasons
  to exist.
- Commit policy clarified: blank official CMS templates can be committed
  outright; filled workbooks never leave their environment, descriptor only.

## 2026-09-17 — ADR-0001 drafted

- Scope decided: input is the completed CMS workbook; inpatient hospital
  first; Python with pandas/openpyxl; work environment can reach CMS for
  reference data pulls.
- ADR-0001 proposed — five-layer architecture, checks bound to a canonical
  model rather than cell addresses, template layout supplied as YAML data,
  findings as data with waivers, dated reference data snapshots, synthetic
  fixtures with injected defects for testing.
- Scope closed out: one state per run; supplemental payment checks in scope
  as a separate opt-in `SUP` family, off by default.
- Next: ADR review. Then SPEC-0002 for the profiler and canonical model.

## 2026-09-17 — project start

- Repo initialized. `main` created with workflow scaffolding, ADR and spec
  templates, and project overview.
- Confirmed the Claude Code web environment cannot reach CMS or other federal
  data sources (egress policy). Recorded in `overview.md` as a design
  constraint.
- Next: ADR-0001 on overall architecture and scope, pending answers to the
  open scoping questions.

### Open questions
- None blocking. The `SUP` input format is unknown and gets resolved when its
  spec is written.
