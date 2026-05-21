---
id: FOLIO-8
title: >-
  Evolve folio into a self-contained app with managed storage and a queryable
  financial data store
status: To Do
assignee: []
created_date: '2026-05-20 22:50'
updated_date: '2026-05-21 06:32'
labels:
  - feature
  - ai
  - pipeline
  - foundation
dependencies: []
priority: high
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The app already has the core pipeline: upload PDF → opencode parses it → structured filename → saved to user-selected folder + row appended to payments.csv. The next step is to make the app own its storage entirely — no user picking a destination folder each time — and to evolve the CSV into a queryable store that can feed the tax calculators and analytics features.

The three concrete changes:
1. App-managed storage: a fixed internal directory the app controls, with the existing filename scheme (`build_invoice_filename`) applied on ingest
2. Broader extraction schema: the current schema covers invoice/payment fields; it needs to cover bank statements, tax receipts, and payslips too
3. Queryable store: the CSV + polars approach works well and should be extended rather than replaced, or promoted to SQLite if aggregations become awkward

Everything else (GILTI, FEIE/FTC, dividend calculator, deadline calendar) reads from this store rather than asking the user to type numbers.
<!-- SECTION:DESCRIPTION:END -->
