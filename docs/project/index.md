# upl-helper: status

Newest first.

## 2026-09-17 — project start

- Repo initialized. `main` created with workflow scaffolding, ADR and spec
  templates, and project overview.
- Confirmed the Claude Code web environment cannot reach CMS or other federal
  data sources (egress policy). Recorded in `overview.md` as a design
  constraint.
- Next: ADR-0001 on overall architecture and scope, pending answers to the
  open scoping questions.

### Open questions
- Which provider type / template is first?
- Does the tool read the finished CMS Excel workbook, the upstream data that
  feeds it, or both?
- Implementation language and what can be installed in the work environment.
- Does the work environment have internet access for reference data pulls?
- Single state or multi-state.
