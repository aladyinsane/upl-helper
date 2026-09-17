# Handoff

Written 2026-09-17 for continuing this project in Lauren's work environment,
likely with a different coding agent. Read this once, then work from
`DEV_WORKFLOW.md` and the docs it points to — this file orients, it doesn't
replace them.

## Read in this order

1. `README.md` — what the project is, for whom.
2. `DEV_WORKFLOW.md` — the ADR → spec → implement → test → PR loop everything
   here follows. Not optional process theater — the check engine's design
   only makes sense in light of it.
3. `docs/adr/0001-architecture-and-scope.md` — the architecture decision.
   Read the whole thing, including *Alternatives considered* and
   *Consequences* — they explain why things are shaped this way, which
   matters when you're deciding whether a change fits or fights the design.
4. `docs/project/overview.md` — stable domain background and constraints.
5. `docs/project/index.md` — newest-first status log. Read top-down until it
   stops telling you anything new; the entries are terse by design.
6. `docs/USAGE.md` — how to actually run the tool, if you're about to.

## Current state

Everything below is true as of 2026-09-17, all merged to `main`, 167 tests
passing, `ruff check .` clean.

**Built:**
- Template profiler (`upl profile`) — structural descriptor of any workbook,
  no cell values. SPEC-0002.
- Canonical model, template mapping format, extractor (`upl extract`).
  SPEC-0003. 21 canonical fields, one row per provider per demonstration
  period.
- Check engine: findings as data, fingerprints, waivers, thresholds, text/
  JSON reporting (`upl check`). SPEC-0004. 14 checks across `ARI` (3), `PLA`
  (6), `IDN` (4), `POL` (1).
- **A real, verified mapping for inpatient hospital**,
  `config/templates/inpatient-hospital-2022.yaml` — the only provider type
  with one. Authored and checked against the actual CMS template, not a
  guess; the file's own header comment is the fullest account of that
  template's real structure (four methodology tabs, not one flat sheet;
  header row quirks; formula-driven cells; etc.) — read it before touching
  this mapping or writing another provider type's.
- Blank reference templates and guidance for **all 8 provider types**,
  downloaded from `medicaid.gov`, under `templates/upl-2022/`. Only
  inpatient hospital has a mapping built against its copy.

**Not built** (see *Roadmap* below): `STR`, `YOY`, `UNI`, `EXT`, `SUP` check
families; the synthetic fixture generator with injected defects; mappings
for the other 7 provider types; verified CCN reference tables (see *Known
gaps*).

## How to work here

Follow `DEV_WORKFLOW.md`. In brief: no code without an accepted ADR behind
it; a spec detailed enough that you never have to guess; one branch per
spec, scoped to it; tests against the spec's acceptance criteria; a PR that
gets reviewed against the ADR and spec, not just "does it run"; an entry in
`docs/project/index.md` when it merges.

A few things specific to this repo, learned the hard way this session:

- **Real CMS templates beat guessing, every time.** The provisional
  inpatient mapping (`config/templates/inpatient-hospital-provisional.yaml`)
  was written blind and got real structural details wrong — not just wrong
  header text, but a wrong assumption about how many sheets hold provider
  data and how the header row itself is laid out. If you're mapping a new
  provider type, get `upl profile` output from the real template in
  `templates/upl-2022/` first and read it before writing a single alias.
  The provisional file stays as a synthetic-fixture test target; don't
  "finish" it into something real — write a new file instead, the way
  `inpatient-hospital-2022.yaml` did.
- **A blank template proves the mapping resolves, nothing about whether the
  values come out right.** Every field in the real inpatient mapping was
  verified to resolve to exactly one column (see
  `test_verified_inpatient_mapping_resolves_against_the_real_template` in
  `tests/test_mapping_loader.py`), but the template has zero data rows. The
  real test is a filled submission, which never leaves your work
  environment and never goes in this repo.
- **Extraction reads formula-cached values (`data_only=True`), the profiler
  reads formula text (`data_only=False`).** This matters because the real
  inpatient template's methodology tabs compute every cell by formula from a
  separate input sheet — there is no literal data entry on those tabs at
  all. If you add a new provider type and its template works the same way,
  this is already handled; if you're touching `extract_path` or
  `load_workbook_structure`, don't collapse this distinction back to one
  mode.
- **Git history gotcha:** if you ever build a branch by merging two other
  branches that *each* later get merged into `main` independently, you get
  a criss-cross merge (two merge-bases against `main`), and GitHub's PR diff
  on that is unreliable — it can show already-merged content as new. Before
  pushing a branch built that way, run
  `git merge-base --all <branch> origin/main`. More than one commit printed
  means rebuild: cherry-pick just the new commits onto a fresh branch off
  current `main`.
- **Never commit anything derived from a real submission.** `.gitignore`
  already blocks the obvious paths; the discipline is not to work around it.
  See `docs/USAGE.md`'s *Data handling* section.

## Roadmap

ADR-0001's phase sequence, annotated with actual status. Numbering is the
ADR's, not a priority order — phases 1-3 need no network and can happen in
any environment; phase 4 is the one phase actually blocked on a networked
environment, i.e. yours.

- **Phase 0 — acquisition reconnaissance: half done.** The template/guidance
  half is done (`templates/upl-2022/`, all 8 provider types). **Not done:**
  confirming the real schemas of the external reference datasets in
  `docs/research/reference-data-sources.md` (POS, HCRIS, NPPES, CMS-64,
  etc.) — written blind, largest unverified assumption in the ADR. This is
  the one piece of phase 0 that specifically needs a networked environment,
  which is most of why it's the natural next thing to do here. For each
  source: real download URL, file format/size/cadence, real column
  names/dtypes, grain and natural key, coverage, and whether the field a
  check actually needs is present. The file itself says exactly what to
  record.
- **Phase 1 — profiler, canonical model, mapping format: done**, plus one
  piece not originally scoped here but done anyway: a real, verified
  inpatient mapping (see *Current state*). **Not done:** the fixture
  generator with injected defects (dropped provider, non-footing total,
  transposed CCN, etc.) — every check should ship with a fixture that must
  trigger it and one that must not, and that doesn't fully exist yet.
- **Phase 2 — check engine, `ARI`/`PLA`: done.**
- **Phase 3 — `IDN` and `YOY`.** `IDN` is implemented but `IDN002`/`IDN003`
  don't run — see *Known gaps*. `YOY` (year-over-year) isn't started; it
  needs a prior-year workbook, which is otherwise available now that phase 0
  is mostly done.
- **Phase 4 — reference data adapters, then `UNI` and `EXT`.** Blocked on
  finishing phase 0's reference-data half. Once that's done, this is
  ordinary testable code against known schemas.
- **Phase 5 — `POL` and `SUP`.** `POL` (partial — `POL002` only) is done.
  `SUP` needs its own spec — allocation methods vary by state and the second
  input format isn't decided.
- **Phase 6 — reporting polish, then a second provider type.** Not started.
  When you get here: outpatient hospital or nursing facility are reasonable
  choices to prove the canonical model stretches, per the ADR's own
  reasoning for picking inpatient hospital first (richest template).

## Known gaps

Flagged explicitly rather than silently patched, per each doc's own
"open questions" convention. Check these before assuming they're solved:

- **`config/reference/ccn-tables.yaml` is unverified** — written from memory
  with no CMS access, `verified: false`. `IDN002`/`IDN003` don't run until
  someone checks it against a real CMS source and flips that flag. The
  file's header says exactly what to verify and against what. This is a
  concrete, scoped, doable task for a networked environment.
- **`ccr_min` (0.05) is still a guess.** `ccr_max` was corrected to `3.00`
  from real domain knowledge this session; `ccr_min` wasn't addressed.
  `config/thresholds/default.yaml` / `src/upl_helper/checks/thresholds.py`.
- **`payment_to_charge_ratio` has no plausibility check.** `PLA001` only
  covers `cost_to_charge_ratio` (the Cost tab's CCR). The Payment tab's
  analogous PTC field exists on the canonical model and in the mapping but
  nothing validates its range.
- **`medicaid_cost` is mapped only on the Cost tab** of the inpatient
  mapping. The other three methodologies (Payment, DRG, Per Diem) compute
  their UPL basis a different way with no equivalent "cost" concept — see
  the mapping file's header comment for why this isn't an oversight.
- **Seven provider types have templates but no mapping.** Downloaded,
  sitting in `templates/upl-2022/`, unmapped.

## Environment notes

Network reachability is a property of the session that happens to be
running, not a fixed constraint of any particular tool — the Claude Code web
session that wrote ADR-0001 couldn't reach `medicaid.gov`; a later desktop
session could, directly, from both its browser and its shell. Whatever
environment or agent picks this up next: check reachability yourself rather
than trusting either past result, and if you can reach a source phase 0 or
`docs/research/reference-data-sources.md` needs, that's useful work
regardless of what this file assumed.

Real filled workbooks never leave the environment that has them — that's a
hard rule, not a default. If your environment has one, run the checks
there; only structural descriptors (`upl profile` output) and check reports
without underlying provider data are safe to move elsewhere.
