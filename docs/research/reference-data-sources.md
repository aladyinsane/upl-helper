# Candidate external reference sources

Working inventory for the external-validation checks. None of these were
reachable from the environment this was drafted in, so the specifics
(file names, column layouts, URLs) need confirming from a machine that can
reach CMS before any adapter is written. Treat the "what it gives us" column
as the design intent, not as verified fact.

| Source | What it gives us | Checks it feeds |
|---|---|---|
| Provider of Services (POS) / Provider Enrollment public file | Universe of Medicare-certified facilities by CCN: state, facility type, ownership type, bed count, certification date, termination date | Provider universe completeness, ownership category, terminated providers still in the demo, CCN validity |
| HCRIS cost report public use files (HOSP10, SNF, etc.) | As-filed and settled Medicare cost reports by CCN and fiscal period: costs, charges, Medicaid days (Wkst S-3), cost-to-charge ratios (Wkst C) | Independent recomputation of the CCR, cost report period match, Medicaid days cross-check |
| NPPES NPI registry (full monthly download) | NPI to legal name, address, taxonomy, deactivation date | NPI validity, CCN/NPI pairing, name mismatches, deactivated NPIs |
| POS + HCRIS across multiple years | Same facility appearing under a new CCN | Change-of-ownership detection, CCN reassignment |
| CMS Provider Data Catalog / Care Compare provider info | Facility name, ownership type, bed count, chain affiliation | Ownership category cross-check, name normalization |
| IPPS / OPPS final rule impact files and addenda | Base rates, wage index by CBSA, DRG weights, outlier thresholds | Spot-repricing a sample of claims under a payment-based methodology |
| CMS market basket and IHS Global Insight update factors | Published inflation/update factors by period | Validating the trend factor and that it was applied midpoint to midpoint |
| CMS-64 expenditure reports | State expenditures by service category and quarter | Macro reasonableness: do total FFS payments in the demo tie to what the state reported spending |
| Medicaid SPA / State Plan approval records | Approved methodology and effective dates by state and service | Asserting the workbook's methodology matches what CMS actually approved |

## Notes

- Newer UPL templates and guidance are distributed through MACFin rather than
  the public medicaid.gov page, so template acquisition may not be scriptable.
- CMS has revised template column positions between versions. Anything that
  binds to a fixed cell address will break.
