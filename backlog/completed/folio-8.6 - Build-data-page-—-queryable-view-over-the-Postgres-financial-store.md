---
id: FOLIO-8.6
title: Build /data page — queryable view over the Postgres financial store
status: Done
assignee: []
created_date: '2026-05-25 10:42'
updated_date: '2026-05-25 11:40'
labels:
  - ui
  - data
  - feature
dependencies: []
parent_task_id: FOLIO-8
priority: high
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
FOLIO-8 persists extracted records into Postgres via `InvoiceRecord`, `BankTransactionRecord`, `TaxReceiptRecord`, `PayslipRecord` in `folio/db_models.py`, but nothing in `folio/components/` reads them back out. The existing `results_table.py` only shows the **current session's in-memory batch** — once you refresh the page, the data store is invisible.

Add a `/data` route (or extend `/files`) that surfaces the DB records. The doc-type tabs map directly to the four `*Record` classes, and the year/quarter/outstanding filters map to the existing classmethods (`by_year`, `outstanding`, `by_jurisdiction`).

This is the read surface that FOLIO-8's "queryable financial data store" acceptance criterion implied but didn't deliver, and it's a prerequisite for FOLIO-8.4 (calculator auto-population) — those calculators need a visible store to point at.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 New `/data` route registered in `folio/folio.py` with header navigation link
- [x] #2 Tabs (or equivalent) for Invoices, Bank Transactions, Tax Receipts, Payslips, each backed by the matching `*Record` query method
- [x] #3 Year filter wired to `_RecordBase.by_year`; default to current year
- [x] #4 Optional quarter filter that passes through to `by_year(year, quarter)`
- [x] #5 Outstanding-only filter wired to `_RecordBase.outstanding`
- [x] #6 Each record row links back to the source S3 object (re-using `download_file` from `AppState`)
- [x] #7 Empty state explains how to ingest documents when a tab has no records
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
`/data` route registered in `folio/folio.py` with `on_load=DataViewState.load`. New `folio/components/data_view.py` renders a segmented control (Invoices / Bank / Tax / Payslips), year + quarter selects, and a `rx.match`-dispatched table with per-doc-type columns. State and query logic split cleanly: `folio/states/data_view.py` is presentation-only; `folio/services/store.py` owns the query composition (wraps existing `by_year`, `outstanding`, `eur_usd_totals` entity methods). Download buttons re-use `FileBrowserState.download_file`.
<!-- SECTION:FINAL_SUMMARY:END -->
