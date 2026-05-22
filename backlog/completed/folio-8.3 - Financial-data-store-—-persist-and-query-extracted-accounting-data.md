---
id: FOLIO-8.3
title: Add Postgres financial data store via rx.Model
status: Done
assignee: []
created_date: '2026-05-20 22:51'
updated_date: '2026-05-22 13:35'
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
Add PostgreSQL as the financial data store using Reflex's built-in rx.Model (SQLModel wrapper). The database URL is configured via DATABASE_URL env var. Schema is managed with reflex db makemigrations / reflex db upgrade. No custom DB module — all operations use rx.session() and SQLModel select() directly, with PostgreSQL-native upsert via sqlalchemy.dialects.postgresql.insert.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 DATABASE_URL env var configures the PostgreSQL connection; rxconfig.py reads it
- [x] #2 rx.Model table classes exist for all four document types from FOLIO-8.2
- [x] #3 Each table has a composite unique constraint on (file_key, content_hash) for upsert deduplication
- [x] #4 Extracted records are persisted after each successful save via on_conflict_do_update
- [x] #5 Query classmethods exist on the model classes: income by year/quarter, tax by jurisdiction, outstanding invoices, EUR/USD totals
- [x] #6 The existing payments.csv append flow is unchanged
- [x] #7 Schema is managed with reflex db makemigrations / reflex db upgrade
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
folio/db_models.py shipped in commit cfabeb7 with InvoiceRecord, BankTransactionRecord, TaxReceiptRecord, PayslipRecord — all extending a shared _RecordBase with the upsert() helper (pg_insert + on_conflict_do_update on the file_key/content_hash unique constraint). Query classmethods: by_year(year, quarter), outstanding(), InvoiceRecord.eur_usd_totals(year), TaxReceiptRecord.by_jurisdiction(j). AC #7 still open: no alembic migrations have been generated — needs `reflex db makemigrations` + committing the generated versions/ file before this can ship to prod.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped across commits cfabeb7 (rx.Model classes + upsert/query helpers) and 0093d8c (alembic initial migration). All four tables (InvoiceRecord, BankTransactionRecord, TaxReceiptRecord, PayslipRecord) have the composite (file_key, content_hash) unique constraint and a file_key index, verified by applying the migration to a fresh local Postgres. Schema changes are managed via `reflex db makemigrations` / `reflex db migrate`.
<!-- SECTION:FINAL_SUMMARY:END -->
