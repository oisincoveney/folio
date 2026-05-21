---
id: FOLIO-4
title: Dividend vs salary calculator for Estonian OÜ tax optimisation
status: To Do
assignee: []
created_date: '2026-05-20 22:43'
labels:
  - feature
  - estonia
  - tax
  - calculator
dependencies: []
priority: medium
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Estonian OÜ owners can take income as salary or as dividends, and the tax treatment differs significantly. Salary is subject to income tax (20%) + social tax (33%) + unemployment insurance, whereas dividends are taxed at 20% corporate tax on the distributed profit (no social tax for regular dividends). The optimal split depends on the owner's total income, desired social benefits (pension, health insurance), and the company's profit.

This calculator lets the user enter their company's annual profit and desired take-home, then shows the effective tax burden and net pay for different salary/dividend combinations — helping them make an informed decision before talking to an accountant.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 User can input: company annual profit, desired personal gross income amount, and split percentage (% as salary vs dividend)
- [ ] #2 Calculator outputs: total tax paid (split by type), net personal take-home, effective tax rate, and company retained profit after distribution
- [ ] #3 Correctly applies current Estonian rates: income tax 20%, social tax 33%, unemployment insurance 1.6% employee / 0.8% employer, corporate income tax 20% on distributed profit
- [ ] #4 Shows the minimum salary threshold (minimum wage) required to maintain full social benefits (health insurance, pension)
- [ ] #5 Results update in real time as inputs change (no submit button needed)
- [ ] #6 Includes a brief plain-language explanation of the trade-offs shown
- [ ] #7 Disclaimer that this is an estimate and the user should consult an accountant for official advice
<!-- AC:END -->
