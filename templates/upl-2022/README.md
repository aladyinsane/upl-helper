# UPL reference documents — 2022 revision

Downloaded 2026-09-17 from
https://www.medicaid.gov/medicaid/financial-management/payment-limit-demonstrations

These are CMS's public reference copies. Per that page, the current UPL
templates and guidance are distributed through MACFin for actual submission;
the files here are reference-only, not fillable, and cannot be uploaded to
MACFin. They are sufficient for building the profiler and template mapping
against real CMS structure. See ADR-0001's commit policy: blank official CMS
templates are not sensitive and are committed outright.

| File | Source URL |
|---|---|
| `SMD-13-003-02.pdf` | [State Medicaid Director Letter 13-003](https://www.medicaid.gov/sites/default/files/Federal-Policy-Guidance/Downloads/SMD-13-003-02.pdf) — the letter that requires annual UPL demonstrations |
| `upl-formula-calculation.pdf` | [UPL Methodology summary](https://www.medicaid.gov/sites/default/files/2020-01/upl-formula-calculation.pdf) |
| `revised-upl-template-faqs.pdf` | [FAQs on the revised (2022) templates](https://www.medicaid.gov/medicaid/financial-management/downloads/revised-upl-template-faqs.pdf) |
| `inpatient-hospital-upl-guidance-2022.pdf` / `inpatient-hospital-upl-template-2022.xlsx` | [Guidance](https://www.medicaid.gov/medicaid/financial-management/downloads/inpatient-hospital-upl-guidnce-2022.pdf) / [Template](https://www.medicaid.gov/medicaid/financial-management/downloads/inpatient-upl-template-2022.xlsx) |
| `outpatient-hospital-upl-guidance-2022.pdf` / `outpatient-hospital-upl-template-2022.xlsx` | [Guidance](https://www.medicaid.gov/medicaid/financial-management/downloads/outpatient-hospital-upl-guidnce-2022.pdf) / [Template](https://www.medicaid.gov/medicaid/financial-management/downloads/outpatient-upl-template-2022.xlsx) |
| `nursing-facility-upl-guidance-2022.pdf` / `nursing-facility-upl-template-2022.xlsx` | [Guidance](https://www.medicaid.gov/medicaid/financial-management/downloads/nursing-facility-upl-guidnce-2022.pdf) / [Template](https://www.medicaid.gov/medicaid/financial-management/downloads/nursing-facility-upl-template-2022.xlsx) |
| `imd-upl-guidance-2022.pdf` / `imd-upl-template-2022.xlsx` | [Guidance](https://www.medicaid.gov/medicaid/financial-management/downloads/upl-guidnce-imd-services-2022.pdf) / [Template](https://www.medicaid.gov/medicaid/financial-management/downloads/mental-disease-upl-template-2022.xlsx) |
| `clinic-services-upl-guidance-2022.pdf` / `clinic-services-upl-template-2022.xlsx` | [Guidance](https://www.medicaid.gov/medicaid/financial-management/downloads/upl-guidnce-clinic-service-2022.pdf) / [Template](https://www.medicaid.gov/medicaid/financial-management/downloads/clinic-services-template-2022.xlsx) |
| `icf-iid-upl-guidance-2022.pdf` / `icf-iid-upl-template-2022.xlsx` | [Guidance](https://www.medicaid.gov/medicaid/financial-management/downloads/upl-guidnce-icfdd-services-2022.pdf) / [Template](https://www.medicaid.gov/medicaid/financial-management/downloads/intermediate-care-upl-template-2022.xlsx) |
| `prtf-upl-guidance-2022.pdf` / `prtf-upl-template-2022.xlsx` | [Guidance](https://www.medicaid.gov/medicaid/financial-management/downloads/upl-guidnce-prtf-services-2022.pdf) / [Template](https://www.medicaid.gov/medicaid/financial-management/downloads/prtf-upl-template-2022.xlsx) |
| `qualified-practitioner-upl-guidance-2022.pdf` / `qualified-practitioner-upl-template-2022.xlsx` | [Guidance](https://www.medicaid.gov/medicaid/financial-management/downloads/upl-guidnce-qualified-practitioner-services-2022.pdf) / [Template](https://www.medicaid.gov/medicaid/financial-management/downloads/physician-upl-template-2022.xlsx) |

All templates carry workbook structure protection and at least two hidden
sheets (`_Controls`, `LKUP` in the inpatient hospital template). None of
these files have been filled in — no provider data, no real values.

If CMS revises these again, re-download rather than editing in place, and
note the revision in `docs/project/index.md`.
