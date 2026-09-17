# upl-helper: overview

Stable context. Things that change every session go in `index.md`.

## Purpose

A check and validation suite for Medicaid UPL demonstrations and the
supplemental payment amounts calculated from them. Existing "legacy" programs
at Lauren's work already do the data processing and the UPL calculations. This
project does not replace them. It independently checks their output before
submission to CMS.

## Domain background

- States must submit annual UPL demonstrations (SMDL 13-003). The UPL is a
  reasonable estimate of what Medicare would have paid for the same services.
- Aggregate UPL is demonstrated separately by ownership category: state
  government, non-state government, and private.
- Provider types have separate CMS templates and separate guidance:
  inpatient hospital, outpatient hospital, nursing facility, ICF/IID, IMD,
  PRTF, qualified practitioner services.
- CMS allows more than one methodology for some provider types (for example
  cost-based vs. payment-based). The state's chosen methodology is written
  into its State Plan and approved by CMS via SPA.
- Supplemental payment amounts are the gap between the demonstrated UPL and
  actual Medicaid payments, by provider.
- CMS templates are distributed as protected Excel workbooks with locked
  cells, hidden sheets and hidden columns. Newer templates are distributed
  through MACFin rather than the public medicaid.gov page.

## Hard constraints

- **Network reachability is per-environment, not a fixed property of "this
  assistant."** The original Claude Code web session that drafted ADR-0001
  found `medicaid.gov`, all `*.cms.gov`, `healthdata.gov`, `api.census.gov`
  and `bls.gov` blocked by egress policy, with GitHub and PyPI reachable.
  A later Claude Code desktop app session (2026-09-17) reached
  `medicaid.gov` directly, from both its browser and its shell — see phase 0
  results in `docs/project/index.md`. Check reachability per session rather
  than assuming either result.
- Consequence: the real CMS templates and the real reference datasets may or
  may not be inspectable or downloadable in a given session. Anything that
  depends on their exact layout has to be discovered at runtime in an
  environment that has them,
  not hardcoded from inspection.
- Lauren cannot reach Claude from her work environment, so files cannot be
  handed over from there either.
- Later development is expected to continue on a work laptop, possibly with a
  different agent or by hand. The repo has to be readable and runnable
  without this session's context.

## Decisions locked in

None yet. First decision is ADR-0001.

## Out of bounds

- No real submission data, provider-level payment data, or PHI in the repo.
- This project does not calculate the UPL as the system of record. It checks.
