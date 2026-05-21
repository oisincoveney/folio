---
id: FOLIO-8.1
title: Switch from user-selected destination to app-managed storage directory
status: To Do
assignee: []
created_date: '2026-05-20 22:50'
updated_date: '2026-05-21 09:56'
labels:
  - ingestion
  - filesystem
dependencies: []
references:
  - 'https://github.com/jsvine/pdfplumber'
  - 'https://github.com/pymupdf/PyMuPDF'
parent_task_id: FOLIO-8
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Currently the /save endpoint requires the user to pick a destination folder (dest_dir) each time via the osascript folder picker. Instead, the user should configure a storage root path once — pointing it at their existing accounting folder — and the app always saves there from that point on.

The file renaming logic (build_invoice_filename in storage.py) and the payments.csv append (append_csv_row) already work correctly and should be kept as-is. This task is about replacing the per-save folder picker with a one-time configurable path and applying the month-based folder structure (e.g. 2025-01/invoices/, 2025-01/bank-statements/) within that root.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The storage root path is configurable once via a settings UI or env var, persisted between sessions
- [ ] #2 The /save endpoint uses the configured root — no dest_dir in the request body, no folder picker on each save
- [ ] #3 The /pick-folder route and osascript folder picker are removed
- [ ] #4 Files are saved into month-based subfolders within the root: <root>/YYYY-MM/invoices/, /bank-statements/, /work-orders/, /exports/
- [ ] #5 Existing build_invoice_filename and append_csv_row logic is unchanged
- [ ] #6 The configured storage path is visible in the UI so the user knows where files are going
- [ ] #7 The storage directory and month subfolders are created automatically if they do not exist
<!-- AC:END -->
