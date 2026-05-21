---
id: FOLIO-8.3
title: Add SQLite database with SQLModel for the financial data store
status: To Do
assignee: []
created_date: '2026-05-20 22:51'
updated_date: '2026-05-21 10:03'
labels:
  - database
  - storage
dependencies:
  - FOLIO-8.2
parent_task_id: FOLIO-8
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a SQLite database (via SQLModel) as the app's internal data store for all extracted financial records. SQLModel integrates naturally with the existing Pydantic models in parse.py and requires no new infrastructure — the database file lives in the configured storage root alongside the documents.

The existing payments.csv output (append_csv_row in storage.py) is kept as-is — it exists solely for Wise bulk payment uploads and is not being replaced.

SQLModel sits on top of SQLAlchemy Core and Pydantic, so the Pydantic models from FOLIO-8.2 (InvoiceData and the new document type models) map directly to SQLModel table definitions with minimal changes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SQLModel and SQLite are added as dependencies
- [ ] #2 SQLModel table definitions exist for all document types from FOLIO-8.2: invoices, bank transactions, tax receipts, payslips
- [ ] #3 The database file is created in the configured storage root on first run
- [ ] #4 Extracted records from FOLIO-8.2 are persisted to the database after each successful parse
- [ ] #5 Duplicate detection: re-processing the same file updates the existing record rather than inserting a duplicate (keyed on file path + content hash)
- [ ] #6 Query functions exist for: income by year/quarter, tax paid by type and jurisdiction (EE/US), outstanding invoices, EUR/USD totals
- [ ] #7 The existing payments.csv append_csv_row flow is unchanged
- [ ] #8 A data review UI lets the user see and correct extracted records before they feed into calculators
<!-- AC:END -->
