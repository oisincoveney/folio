---
id: FOLIO-8.8
title: Show ingestion confirmation — link from batch row to stored file and DB record
status: Done
assignee: []
created_date: '2026-05-25 10:42'
updated_date: '2026-05-25 11:40'
labels:
  - ui
  - feedback
dependencies: []
parent_task_id: FOLIO-8
priority: medium
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After parsing+saving a document, the only feedback in `results_table.py` is a green check icon. The user cannot tell where the file landed in the S3 bucket or whether a DB record was actually upserted. Add explicit confirmation so the "save" step is verifiable from the UI without leaving the batch view.

Concretely: when a row finishes saving, show the resulting S3 object key (clickable, downloads via `AppState.download_file`) and a small badge indicating the record was persisted (or surface the row id). When `_RecordBase.upsert` fails, surface the failure inline instead of silently leaving status='done'.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Saved rows display the final S3 object key with a download affordance
- [x] #2 Saved rows display an indicator that the DB upsert succeeded (e.g., persisted badge)
- [x] #3 Upsert failures surface as a row-level error rather than reading as success
- [x] #4 No regression to the existing status icon / Retry button flow
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
`db_persisted: bool` added to `InvoiceRow`. `services.ingestion.save_record` raises `IngestionError(stage="s3"|"db", message=...)`; `BatchState.save_row` patches `db_persisted=True / status_ok=True / saved_as=key` on success and explicitly `status_ok=False / db_persisted=False` on either failure stage (fixing the prior bug where a DB-stage failure left the green check showing). `_save_cell` in `results_table.py` renders the green check, a "DB" badge when persisted, and an `rx.icon_button` whose `title=row.saved_as` exposes the S3 key and `on_click=FileBrowserState.download_file(row.saved_as)` opens the stored object. Two new tests in `tests/test_state_save.py`.
<!-- SECTION:FINAL_SUMMARY:END -->
