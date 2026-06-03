---
id: FOLIO-6
title: GILTI exposure calculator for US citizens owning an Estonian OÜ
status: To Do
assignee: []
created_date: '2026-05-20 22:47'
updated_date: '2026-05-22 22:02'
labels:
  - feature
  - us-tax
  - calculator
  - gilti
dependencies: []
references:
  - 'https://github.com/PSLmodels/Tax-Calculator'
  - 'https://www.irs.gov/forms-pubs/about-form-8992'
  - >-
    https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section951A
priority: medium
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
US citizens who own a Controlled Foreign Corporation (CFC) — which includes an Estonian OÜ where the owner holds >50% — are subject to GILTI (Global Intangible Low-Taxed Income) tax on retained profits under IRC §951A, even if no dividend was distributed. This is one of the least-understood US tax obligations for Americans with foreign companies.

This calculator lets the user enter their OÜ's financials and see their estimated US GILTI exposure before they talk to an accountant.

GILTI formula (simplified for a single CFC with no tangible assets):
- Tested income = CFC net income (less certain exclusions)
- QBAI (Qualified Business Asset Investment) = 10% × average adjusted basis of depreciable tangible property
- GILTI inclusion = tested income − QBAI
- US tax on GILTI = GILTI inclusion × (37% individual rate or 21% corporate, less 50% deduction for corporations, less foreign tax credit for Estonian taxes paid)

No open-source Python library exists for GILTI — implement the calculation directly from IRS Form 8992 instructions and IRC §951A. Use `taxcalc` (https://github.com/PSLmodels/Tax-Calculator) to model the effect of the GILTI inclusion on the user's overall US income tax liability.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 User can input: CFC net income (EUR), tangible asset basis (EUR, optional), Estonian corporate tax paid, and personal US marginal rate
- [ ] #2 Calculator outputs: tested income, QBAI deduction, GILTI inclusion amount, estimated US tax owed on GILTI, and net GILTI tax after Estonian tax credit
- [ ] #3 Shows the difference between filing as an individual (no 50% deduction) vs an S-corp election scenario (note only, not full calc)
- [ ] #4 EUR amounts are converted to USD using a user-supplied or fetched annual average IRS exchange rate
- [ ] #5 Explains in plain language what GILTI is and why retained OÜ profits trigger it
- [ ] #6 Includes a clear disclaimer that this is an estimate requiring CPA review
- [ ] #7 Correctly references IRS Form 8992 and IRC §951A in the UI help text
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Grooming note: Build with manual inputs first; FOLIO-8.4 will later pre-fill CFC income and Estonian tax values from stored records.
<!-- SECTION:NOTES:END -->
