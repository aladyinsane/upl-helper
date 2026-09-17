# upl-helper

Validation and check suite for Medicaid Upper Payment Limit (UPL)
demonstrations and the supplemental payment calculations derived from them.

## What this is for

State Medicaid agencies submit annual UPL demonstrations to CMS on standard
Excel templates, by provider type (inpatient hospital, outpatient hospital,
nursing facility, ICF/IID, IMD, PRTF, qualified practitioner). Existing
processes produce the numbers. This project checks them before they go to CMS:

- internal consistency and arithmetic
- conformance to the CMS template structure and to the methodology in the
  approved State Plan
- year-over-year continuity
- completeness of the provider universe
- provider identifier integrity (CCN, NPI) including identifier changes
- reasonableness against independent public data sources

## Status

Early but runnable. See `docs/adr/` for decisions, `docs/specs/` for what each
piece does, and `docs/project/index.md` for current state.

```
upl profile   WORKBOOK                  describe a template's structure, no cell data
upl unprotect WORKBOOK                  write an unprotected working copy
upl extract   WORKBOOK -m MAPPING       read it into the canonical model
upl check     WORKBOOK -m MAPPING       run the check suite
```

**The shipped inpatient mapping and the CCN reference tables are unverified.**
They were written without access to a real CMS template or to any CMS data
source. Phase 0 of ADR-0001 replaces them; until then `upl extract` and
`upl check` say so on every run, and the checks that depend on the unverified
tables refuse to run rather than invent findings.

## Workflow

See `DEV_WORKFLOW.md`. ADR -> spec -> implement -> test -> PR.

## Data handling

No real state submissions, provider-level payment data, or anything derived
from them belongs in this repository. Test fixtures are synthetic. See
`.gitignore`.
