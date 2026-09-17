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
