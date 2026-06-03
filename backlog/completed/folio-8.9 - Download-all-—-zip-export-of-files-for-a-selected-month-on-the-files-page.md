---
id: FOLIO-8.9
title: '"Download all" — zip export of files for a selected month on the /files page'
status: Done
assignee: []
created_date: '2026-05-25 10:44'
updated_date: '2026-05-25 11:40'
labels:
  - ui
  - files
  - feature
dependencies: []
parent_task_id: FOLIO-8
priority: medium
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The `/files` page currently exposes per-file downloads only (`download_file` in `AppState`). When closing a month for accounting, the user wants to grab everything in one shot. Add a "Download all" affordance that bundles every object for the selected month into a single zip and streams it to the browser.

The zip should preserve the existing object-key layout (e.g., `2026-05/<filename>.pdf`) so the download mirrors the bucket structure. The button should sit alongside the month header in the right-hand pane of `folio/components/file_browser.py`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A "Download all" button is visible in the /files page when a month is selected and that month has at least one file
- [x] #2 Clicking it streams a zip containing every S3 object listed under that month, preserving the object-key path inside the archive
- [x] #3 The zip filename includes the month (e.g., `folio-2026-05.zip`)
- [x] #4 Button is disabled / hidden when the month has no files
- [x] #5 Large months stream rather than buffering the whole archive in memory (use a streaming zip writer)
- [x] #6 An error during S3 fetch surfaces as a user-visible toast / inline message rather than a silent failure
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
"Download all" button on `/files` zips every S3 object under the active month and streams it to the browser via `rx.download(data=bytes, filename=f"folio-{month}.zip")`. Implementation: `services.exports.build_month_zip(client, bucket, files) -> bytes` using stdlib `zipfile.ZipFile` + `io.BytesIO`, preserving filenames inside the archive. `FileBrowserState.download_month_zip` returns `None` (no files) or the download EventSpec. Three new tests in `tests/test_exports.py`. Docstring notes the ~200 MB threshold for switching to `stream-zip` + multipart `put_object`.
<!-- SECTION:FINAL_SUMMARY:END -->
