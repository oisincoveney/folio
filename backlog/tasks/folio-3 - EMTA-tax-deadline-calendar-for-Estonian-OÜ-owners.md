---
id: FOLIO-3
title: EMTA tax deadline calendar for Estonian OÜ owners
status: To Do
assignee: []
created_date: '2026-05-20 22:43'
labels:
  - feature
  - estonia
  - tax
dependencies: []
references:
  - 'https://www.emta.ee'
priority: medium
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Self-employed contractors running an Estonian OÜ face a recurring set of filing and payment deadlines with the Estonian Tax and Customs Board (EMTA). Missing these results in interest charges and penalties. This feature surfaces the relevant upcoming deadlines in the app so the user never needs to remember them or check the EMTA website.

Key recurring deadlines for a typical contractor OÜ:
- TSD (income and social tax declaration) — 10th of each month
- VAT declaration (KMD) — 20th of each month (if VAT registered)
- Annual report — 6 months after financial year end (typically 30 June)
- Advance income tax (füüsilise isiku tulumaks) — quarterly (March, June, September, December 15th)

The calendar should show what's due, when, and a brief note on what action is needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A tax calendar view lists all upcoming EMTA deadlines for the next 90 days
- [ ] #2 Deadlines cover at minimum: TSD (10th monthly), KMD VAT declaration (20th monthly), quarterly advance income tax, annual report
- [ ] #3 Each deadline entry shows: deadline name, due date, short description of what to file/pay, and a link to the relevant EMTA page
- [ ] #4 User can mark a deadline as 'handled' for that period
- [ ] #5 Deadlines within 7 days are visually highlighted as urgent
- [ ] #6 User can configure whether they are VAT registered (to show/hide KMD deadlines)
<!-- AC:END -->
