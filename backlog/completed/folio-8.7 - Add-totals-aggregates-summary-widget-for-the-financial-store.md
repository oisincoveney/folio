---
id: FOLIO-8.7
title: Add totals/aggregates summary widget for the financial store
status: Done
assignee: []
created_date: '2026-05-25 10:42'
updated_date: '2026-05-25 11:40'
labels:
  - ui
  - data
dependencies: []
parent_task_id: FOLIO-8
priority: medium
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`InvoiceRecord.eur_usd_totals(year)` already exists but is never displayed. Once the `/data` page is up (FOLIO-8.6), add a small summary widget at the top of the page (or as a separate `/dashboard` route) that surfaces high-signal aggregates: invoice totals by currency for the selected year, count of outstanding records per doc type, and number of distinct months represented in the bucket.

This gives an at-a-glance answer to "is folio actually capturing what I'm sending it?" which today requires reading the table row-by-row.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Summary widget renders on the /data page (or dedicated /dashboard route) showing invoice totals by currency for the active year
- [x] #2 Outstanding counts shown per doc type
- [x] #3 Widget reuses existing classmethods (`eur_usd_totals`, `outstanding`) — no new SQL
- [x] #4 Widget updates when the year filter changes
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Totals tile strip lives at the top of `/data`: EUR invoiced for the active year, USD invoiced for the active year, outstanding count for the current doc-type tab, and records-shown count. All values come from `services.store.query()` so a single call backs the page; tiles update whenever the year filter changes. No new SQL — reuses `InvoiceRecord.eur_usd_totals` and per-class `outstanding()`.
<!-- SECTION:FINAL_SUMMARY:END -->
