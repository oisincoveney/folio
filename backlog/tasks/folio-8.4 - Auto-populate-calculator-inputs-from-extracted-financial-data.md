---
id: FOLIO-8.4
title: Auto-populate calculator inputs from the financial store
status: To Do
assignee: []
created_date: '2026-05-20 22:51'
updated_date: '2026-05-21 06:33'
labels:
  - integration
  - ui
dependencies:
  - FOLIO-8.3
  - FOLIO-4
  - FOLIO-6
  - FOLIO-7
parent_task_id: FOLIO-8
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Wire the store built in FOLIO-8.3 into the calculator UIs (FOLIO-4 dividend/salary, FOLIO-6 GILTI, FOLIO-7 FEIE/FTC) so inputs are pre-filled from real extracted data. The user opens a calculator and sees their actual figures already populated, sourced from the documents they have uploaded. Individual fields remain editable before running the calculation.

Each pre-filled value should show which source file it came from so the user can verify and trace back to the document.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 FOLIO-4 pre-fills OÜ annual profit from extracted income and expense records
- [ ] #2 FOLIO-6 pre-fills CFC net income and Estonian corporate tax paid
- [ ] #3 FOLIO-7 pre-fills gross SE income, Estonian income tax paid, and Estonian social tax paid
- [ ] #4 Each pre-filled field shows a tooltip or label indicating which source file(s) the value came from
- [ ] #5 User can override any pre-filled value without affecting the stored data
- [ ] #6 A refresh button re-aggregates from the store and updates all pre-filled values
- [ ] #7 If a required value is not yet in the store, the field is left blank with a hint about what document type is needed
<!-- AC:END -->
