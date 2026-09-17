# upl-helper: status

Newest first.

## 2026-09-17 — ADR-0001 drafted

- Scope decided: input is the completed CMS workbook; inpatient hospital
  first; Python with pandas/openpyxl; work environment can reach CMS for
  reference data pulls.
- ADR-0001 proposed — five-layer architecture, checks bound to a canonical
  model rather than cell addresses, template layout supplied as YAML data,
  findings as data with waivers, dated reference data snapshots, synthetic
  fixtures with injected defects for testing.
- Open questions from project start are resolved except: single vs
  multi-state, and whether supplemental payment allocation logic is in scope.
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
- Single state or multi-state.
- Is checking the supplemental payment allocation in scope, or only the UPL?
