---
id: FOLIO-9.2
title: Port Alpine.js store to Reflex AppState with non-streaming event handlers
status: Done
assignee: []
created_date: '2026-05-21 10:23'
updated_date: '2026-05-22 13:29'
labels:
  - frontend
  - reflex
  - migration
dependencies:
  - FOLIO-9.1
references:
  - 'https://reflex.dev/docs/state/overview/'
  - 'https://reflex.dev/docs/events/yield-events/'
parent_task_id: FOLIO-9
priority: high
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create folio/state.py with an AppState(rx.State) class that replaces the Alpine.js store defined in static/store.js. This subtask covers all state vars and the non-streaming event handlers only — the parse/stream/save/retry handlers come in the next subtask.

State vars to port from store.js:
- model: str = ""
- models: list[dict] = []  (each entry has "id" and "pdf" keys)
- rows: list[dict] = []    (each row mirrors the structure built by handleEvent in store.js)
- selected_file_key: str = ""
- parsing: bool = False
- saving: bool = False
- completed: int = 0
- total: int = 0
- retry_queue: list[str] = []
- retry_running: bool = False
- dest_dir: str = ""
- staged_files: dict[str, list[str]] = {}  (source_id → [orig_name, path]; replaces app.py's _staged_files module global)

Non-streaming event handlers to implement:
- load_models: calls parse.get_model_options() and populates self.models; sets self.model to default if unset
- pick_folder: runs osascript via subprocess (same logic as Flask's /pick-folder route) and sets self.dest_dir
- select_row(file_key: str): sets self.selected_file_key
- reset: clears all state vars back to defaults
- update_model(model: str): sets self.model

Helper computed vars / methods:
- selected_row computed var (returns the row dict matching selected_file_key, or first row, or None)
- status_counts computed var (returns dict with active/done/error/pending counts)

Do not implement handle_upload, save, retry, or streaming in this subtask.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 folio/state.py exists and defines AppState(rx.State)
- [x] #2 All state vars listed above are present with correct types and defaults
- [x] #3 load_models populates self.models by calling parse.get_model_options()
- [x] #4 pick_folder runs osascript and sets self.dest_dir (or sets empty string if cancelled)
- [x] #5 reset, select_row, and update_model handlers exist
- [x] #6 selected_row and status_counts computed vars are defined
- [x] #7 No import of Flask anywhere in folio/
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in commit ba2bddd. AppState(rx.State) lives in folio/state.py with all listed vars and the non-streaming handlers (load_models, pick_folder, select_row, clear_session, update_model) plus selected_row / status_counts computed vars. pick_folder and dest_dir were later removed by FOLIO-8.1 when storage moved to S3.
<!-- SECTION:FINAL_SUMMARY:END -->
