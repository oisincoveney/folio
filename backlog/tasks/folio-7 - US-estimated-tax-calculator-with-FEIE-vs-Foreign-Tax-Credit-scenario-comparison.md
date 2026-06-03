---
id: FOLIO-7
title: >-
  US estimated tax calculator with FEIE vs Foreign Tax Credit scenario
  comparison
status: To Do
assignee: []
created_date: '2026-05-20 22:47'
updated_date: '2026-05-22 22:02'
labels:
  - feature
  - us-tax
  - calculator
  - feie
  - ftc
dependencies: []
references:
  - 'https://github.com/PSLmodels/Tax-Calculator'
  - 'https://www.irs.gov/forms-pubs/about-form-2555'
  - 'https://www.irs.gov/forms-pubs/about-form-1116'
  - 'https://github.com/AutonomoDev/ai.autonomo.codes'
priority: medium
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Self-employed US citizens abroad face two mutually exclusive strategies for avoiding double taxation: the Foreign Earned Income Exclusion (FEIE, Form 2555) which excludes up to ~$126,500 of foreign earned income, or the Foreign Tax Credit (FTC, Form 1116) which credits Estonian taxes paid against US liability. The right choice depends on income level, Estonian tax rate, SE tax, and other factors — and the decision must be made consistently year to year.

This tool calculates estimated annual US tax liability under both scenarios side-by-side so the user can see which is more favourable for their situation.

Use `taxcalc` (PSL Tax-Calculator, https://github.com/PSLmodels/Tax-Calculator) as the foundation for US income and payroll tax calculations. Implement FEIE (Form 2555) and FTC (Form 1116) logic directly from IRS instructions — no Python library exists for these. Self-employment tax (Schedule SE, 15.3% up to Social Security wage base) must be calculated separately as taxcalc does not cover Schedule C/SE income.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 User inputs: gross self-employment income (EUR), Estonian income tax paid, Estonian social tax paid, filing status, and any other US income
- [ ] #2 Calculator shows two columns side-by-side: FEIE scenario and FTC scenario
- [ ] #3 Each column shows: excluded/credited amount, taxable income remaining, self-employment tax, US income tax after exclusion/credit, and total US tax owed
- [ ] #4 SE tax (15.3% / 2.9% above wage base) is calculated correctly in both scenarios — FEIE does not eliminate SE tax obligation
- [ ] #5 FEIE physical presence eligibility: user can input days outside the US in the year and the calculator flags whether the 330-day test is met
- [ ] #6 Net take-home comparison is shown as a single summary line: 'Under FEIE you owe $X more/less than FTC'
- [ ] #7 EUR income is converted to USD using annual IRS average exchange rate (user-supplied or fetched)
- [ ] #8 Disclaimer that FEIE and FTC are mutually exclusive and the choice has multi-year implications
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Grooming note: Build with manual inputs first; FOLIO-8.4 will later pre-fill income and Estonian tax values from stored records.
<!-- SECTION:NOTES:END -->
