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

Early. Nothing is implemented yet. See `docs/adr/` for decisions and
`docs/project/index.md` for current state.

## Workflow

See `DEV_WORKFLOW.md`. ADR -> spec -> implement -> test -> PR.

## Data handling

No real state submissions, provider-level payment data, or anything derived
from them belongs in this repository. Test fixtures are synthetic. See
`.gitignore`.
