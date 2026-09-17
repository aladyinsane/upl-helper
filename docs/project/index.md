# upl-helper: status

Newest first.

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
