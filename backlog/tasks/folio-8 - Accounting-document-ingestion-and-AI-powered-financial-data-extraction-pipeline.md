---
id: FOLIO-8
title: >-
  Evolve folio into a self-contained app with managed storage and a queryable
  financial data store
status: Done
assignee: []
created_date: '2026-05-20 22:50'
updated_date: '2026-05-25 11:40'
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Documents are stored in app-managed S3-compatible bucket storage using month/document-type object keys instead of user-selected folders
- [x] #2 The extraction pipeline supports invoices, bank statements, tax receipts, and payslips with document-type-specific structured records
- [x] #3 Extracted records are persisted to a queryable Postgres data store via Reflex/SQLModel models with deduplicating upserts
- [x] #4 The legacy payments.csv append flow remains available for invoice rows while the database becomes the primary query surface
- [x] #5 The app can run as a self-contained local stack with managed Postgres and MinIO dependencies
- [x] #6 The stored documents and persisted records are reachable and queryable from the UI (header navigation + /data page) without requiring URL knowledge or direct DB access
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
FOLIO-8 was completed as three foundation slices: switch document persistence to app-managed bucket storage, broaden the extraction schema for the financial document types needed by calculators, and persist extracted records to Postgres through Reflex model classes. The local runtime was then made self-contained with Postgres and MinIO manifests plus the Tilt workflow.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Grooming note: FOLIO-8.1, FOLIO-8.2, FOLIO-8.3, FOLIO-9, and FOLIO-11 indicate the self-contained ingestion/storage foundation is now in place. FOLIO-8.4 remains open as downstream calculator integration, not foundation work.

2026-05-25 review: storage and DB persistence layers are in place, but the read surface is missing — `/files` exists but has no header link, and there is no UI at all over the Postgres records (`InvoiceRecord` etc.). Reopened with a new acceptance criterion (#6) and four subtasks: FOLIO-8.5 (header nav), FOLIO-8.6 (/data page), FOLIO-8.7 (totals widget), FOLIO-8.8 (ingestion confirmation in the batch view).

2026-05-25: subtasks 8.5/8.6/8.7/8.8/8.9 landed. AppState god-class refactored into services/ + thin state slices (BatchState, FileBrowserState, DataViewState, HeaderState). 111 tests pass, lint+typecheck clean. AC #6 satisfied: documents reachable via /files (with month zip export) and records queryable via /data (tabs per doc type, year/quarter filters, totals tiles). 8.4 (calculator auto-populate) stays open since the calculators it would feed do not yet exist.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Self-contained ingestion and storage foundation is complete. Documents now save to app-managed S3-compatible storage, the parser handles invoices, bank statements, tax receipts, and payslips, extracted records persist to Postgres via Reflex/SQLModel models with upsert/query helpers, and the app has local Postgres/MinIO runtime support through Docker/Kubernetes/Tilt. Remaining work is downstream calculator auto-population in FOLIO-8.4.

Closed via the refactor + read-surface drain. The services/ layer (parser, ingestion, store, exports) decouples domain operations from Reflex state, and the state slices (batch, file_browser, data_view, header) hold only presentation state. Records flow upload → parse → S3 + DB upsert → visible in /data tabs; files browseable in /files with per-month zip export; batch rows show DB-persistence confirmation. 9 new tests across the four feature branches. 8.4 left open for downstream calculator work.
<!-- SECTION:FINAL_SUMMARY:END -->
