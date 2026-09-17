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
piece does, and `docs/project/index.md` for current state. Continuing
development elsewhere, especially with a different agent? Start at
`HANDOFF.md`.

```
upl profile   WORKBOOK                  describe a template's structure, no cell data
upl unprotect WORKBOOK                  write an unprotected working copy
upl extract   WORKBOOK -m MAPPING       read it into the canonical model
upl check     WORKBOOK -m MAPPING       run the check suite
```

See `docs/USAGE.md` for setup and real command examples.

**Inpatient hospital has a real, verified mapping**
(`config/templates/inpatient-hospital-2022.yaml`), checked against the actual
CMS template. The other seven provider types have templates downloaded
(`templates/upl-2022/`) but no mapping yet. **The CCN reference tables**
(`config/reference/ccn-tables.yaml`) are still unverified — written without
access to any CMS data source — so `IDN002`/`IDN003` refuse to run rather
than invent findings until someone confirms them against a real source.

## Workflow

See `DEV_WORKFLOW.md`. ADR -> spec -> implement -> test -> PR.

## Data handling

No real state submissions, provider-level payment data, or anything derived
from them belongs in this repository. Test fixtures are synthetic. See
`.gitignore`.
