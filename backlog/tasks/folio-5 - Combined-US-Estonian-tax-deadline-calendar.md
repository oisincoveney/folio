---
id: FOLIO-5
title: Combined US + Estonian tax deadline calendar
status: To Do
assignee: []
created_date: '2026-05-20 22:47'
labels:
  - feature
  - us-tax
  - estonia
  - tax
  - calendar
dependencies:
  - FOLIO-3
references:
  - 'https://github.com/ics-py/ics-py'
  - 'https://github.com/collective/icalendar'
  - >-
    https://www.irs.gov/individuals/international-taxpayers/us-citizens-and-resident-aliens-abroad-tax-filing-dates
priority: medium
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A single unified deadline calendar that merges Estonian EMTA deadlines (from FOLIO-3) with US federal deadlines relevant to an American self-employed contractor with a foreign corporation. The goal is one place to see everything due across both tax systems so nothing slips.

Key US deadlines to include:
- April 15: Federal return (Form 1040) + FBAR (FinCEN 114)
- June 15: Automatic extension for Americans residing abroad
- Quarterly estimated taxes: April 15, June 15, Sept 15, Jan 15
- October 15: Extended return deadline + extended FBAR deadline
- Form 5471 is due with the annual return (no separate deadline but must be flagged)

The calendar should be exportable as an .ics file so it can be imported into any calendar app. Use `ics.py` (https://github.com/ics-py/ics-py) or the `icalendar` library (https://github.com/collective/icalendar) for iCal generation — do not build calendar serialisation from scratch.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All US federal deadlines listed above are included with correct dates, auto-adjusted when they fall on weekends/holidays
- [ ] #2 Estonian EMTA deadlines from FOLIO-3 are also present in the same view
- [ ] #3 Each deadline entry includes: name, due date, short description, and link to relevant IRS or EMTA page
- [ ] #4 Deadlines within 7 days are highlighted as urgent; within 30 days as upcoming
- [ ] #5 Calendar is exportable as a .ics file using ics.py or icalendar library
- [ ] #6 User can filter by country (US only, Estonia only, or both)
- [ ] #7 Form 5471 obligation is flagged alongside the annual return deadline
<!-- AC:END -->
