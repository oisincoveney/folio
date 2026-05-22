---
id: FOLIO-8.3
title: Add SQLite database with SQLModel for the financial data store
status: To Do
assignee: []
created_date: '2026-05-20 22:51'
updated_date: '2026-05-21 21:48'
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
- [ ] #1 DATABASE_URL env var configures the PostgreSQL connection; rxconfig.py reads it
- [ ] #2 rx.Model table classes exist for all four document types from FOLIO-8.2
- [ ] #3 Each table has a composite unique constraint on (file_key, content_hash) for upsert deduplication
- [ ] #4 Extracted records are persisted after each successful save via on_conflict_do_update
- [ ] #5 Query classmethods exist on the model classes: income by year/quarter, tax by jurisdiction, outstanding invoices, EUR/USD totals
- [ ] #6 The existing payments.csv append flow is unchanged
- [ ] #7 Schema is managed with reflex db makemigrations / reflex db upgrade
<!-- AC:END -->
