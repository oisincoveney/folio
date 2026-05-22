---
id: FOLIO-8.1
title: Switch from user-selected destination to app-managed storage directory
status: To Do
assignee: []
created_date: '2026-05-20 22:50'
updated_date: '2026-05-21 21:48'
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
Replace the per-save osascript folder picker with S3-compatible bucket storage. The app saves all documents to a configured bucket using month-based object key prefixes. Configuration is via env vars (no config file). A file browser UI lets the user browse and download documents by month.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 FOLIO_BUCKET_NAME, FOLIO_BUCKET_ENDPOINT, FOLIO_BUCKET_ACCESS_KEY, FOLIO_BUCKET_SECRET_KEY, FOLIO_BUCKET_REGION env vars configure the bucket
- [ ] #2 Files are saved as s3://bucket/YYYY-MM/invoices|bank-statements|tax-receipts|payslips/filename.pdf
- [ ] #3 payments.csv is per-month at s3://bucket/YYYY-MM/payments.csv (invoice rows only)
- [ ] #4 dest_dir state var, pick_folder(), handle_folder_source(), and osascript calls are removed
- [ ] #5 The configured bucket name is shown in the UI in place of the old folder path
- [ ] #6 A /files page lets the user browse documents by month and download individual files via presigned URLs
<!-- AC:END -->
