---
id: FOLIO-9.3
title: >-
  Implement upload handler, parse streaming bridge, save, and retry event
  handlers
status: Done
assignee: []
created_date: '2026-05-21 10:24'
updated_date: '2026-05-22 13:29'
labels:
  - frontend
  - reflex
  - migration
dependencies:
  - FOLIO-9.2
references:
  - 'https://reflex.dev/docs/events/background-events/'
  - 'https://reflex.dev/docs/library/forms/upload/'
parent_task_id: FOLIO-9
priority: high
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add the streaming and data-mutation event handlers to AppState (folio/state.py). These are the trickiest handlers because parse.py's start_parse_job returns a queue.Queue that must be bridged into Reflex's state-update model.

**Upload handler (handle_upload)**
- Receives list[rx.UploadFile] from the rx.upload component.
- For each file: read bytes, write to a temp file in .folio_uploads/ (same dir as before), build a source_id (uuid4), record in self.staged_files.
- Build the temp_files list expected by start_parse_job and call it, getting back a queue.Queue.
- Store the queue in a module-level dict (e.g., _active_jobs: dict[str, queue.Queue]) keyed by a new job_id.
- Set self.total, self.parsing = True, append skeleton row dicts to self.rows.
- Yield to send the initial state to the frontend, then call the background streaming task.

**Background streaming task (_stream_parse)**
- Decorated @rx.background.
- Takes job_id as argument; looks up queue from _active_jobs.
- Loop: use asyncio.to_thread(q.get, timeout=130) to fetch each event without blocking the event loop.
- For each event, acquire async with self: and update state exactly as handleEvent in store.js does (map event types start/batch_start/raw_log/attempt/retrying/result/error onto self.rows, self.completed, etc.).
- When event type is "done", break and clean up _active_jobs[job_id].

**Save handler (save_rows)**
- Takes a list of confirmed row dicts (or operates on self.rows filtered to done+unsaved status).
- Requires self.dest_dir to be set; if not, set an error flag and return.
- For each row: call parse.claim_pending(row["file_id"]), then storage.build_invoice_filename, shutil.move/copy2, storage.append_csv_row. Mirror the logic in Flask's /save route exactly.
- Updates each row's savedAs field and marks it as saved.

**Retry handlers (retry_row, retry_failed)**
- Mirror the retryRows / retryFailed logic from store.js.
- Reset row status to "pending", add file_key to retry_queue.
- If not currently parsing, call start_parse_job with the staged files for those rows, store queue, start _stream_parse.

Key constraint: parse.py, storage.py, normalization.py, config.py must not be modified.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 handle_upload accepts files, saves to .folio_uploads/, calls start_parse_job, and starts _stream_parse background task
- [x] #2 _stream_parse consumes the queue.Queue via asyncio.to_thread and updates self.rows/self.completed matching the handleEvent logic in store.js
- [x] #3 save_rows calls claim_pending + build_invoice_filename + shutil.move + append_csv_row for each confirmed row
- [x] #4 retry_row and retry_failed reset row status and trigger a new parse job for staged files
- [x] #5 No HTTP routes or Flask imports anywhere in folio/
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in commit ba2bddd. handle_upload, stream_parse (background task consuming parse.start_parse_job's queue via asyncio.to_thread), save_row/save_all_done, and retry_row/retry_failed/run_retry_queue all live in folio/state.py. No Flask imports remain.
<!-- SECTION:FINAL_SUMMARY:END -->
