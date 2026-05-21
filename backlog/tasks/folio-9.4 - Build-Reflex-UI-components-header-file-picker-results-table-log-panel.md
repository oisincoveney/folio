---
id: FOLIO-9.4
title: 'Build Reflex UI components: header, file picker, results table, log panel'
status: To Do
assignee: []
created_date: '2026-05-21 10:24'
updated_date: '2026-05-21 10:25'
labels:
  - frontend
  - reflex
  - migration
dependencies:
  - FOLIO-9.2
references:
  - 'https://reflex.dev/docs/library/forms/upload/'
  - 'https://reflex.dev/docs/library/'
parent_task_id: FOLIO-9
priority: high
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the four UI component functions in Python using Reflex's component primitives. These replace the Alpine.js components and Jinja partials currently in static/components/ and templates/partials/.

Create folio/components/ with one file per component. Style with Tailwind classes (Reflex supports the `class_name` prop with Tailwind) to match the existing layout: full-height flex column, gray background, overflow-hidden main area.

**header (folio/components/header.py)**
- Model dropdown: rx.select populated from AppState.models (display model["id"], value model["id"]); on_change → AppState.update_model. Show a "(pdf)" suffix indicator for pdf-capable models.
- Folder picker button: on_click → AppState.pick_folder; display self.dest_dir truncated if set.
- Status pill row: counts from AppState.status_counts (active/done/error/pending).
- Reset button: on_click → AppState.reset; disabled while AppState.parsing.

**file_picker (folio/components/file_picker.py)**
- rx.upload with multiple=True, accept={"application/pdf": [".pdf"]}.
- Drop zone area showing "Drop PDFs here or click to browse" when no upload is in progress.
- on_drop → AppState.handle_upload.
- Show a progress indicator (completed/total) while AppState.parsing is True.
- Hidden when AppState.rows is non-empty (the results table takes over).

**results_table (folio/components/results_table.py)**
- Shown when AppState.rows is non-empty.
- Left column: list of file rows with status indicator (spinner for active, checkmark for done, X for error). Clicking a row calls AppState.select_row.
- Right panel: editable fields for the selected row (company, amount, targetCurrency, invoiceNumber, invoiceDate, description, paymentReference). Fields update self.rows inline.
- Per-row action buttons: Save (calls AppState.save_rows with that row), Retry (calls AppState.retry_row). Save disabled if row is not "done" or dest_dir is empty.
- Bulk "Save all done" and "Retry all failed" buttons in the footer.

**log_panel (folio/components/log_panel.py)**
- Shown below the results table, displays log entries for the selected row.
- Each entry has type (raw/system/tool_use/step_finish etc.), title, body, meta — render as collapsible rows.
- Technical entries (step_start/step_finish) styled more subtly.
- Auto-scroll to bottom as new entries arrive.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 folio/components/ contains header.py, file_picker.py, results_table.py, log_panel.py
- [ ] #2 Each file exports a single component function that accepts no required arguments and reads from AppState
- [ ] #3 Model dropdown renders all models and calls update_model on change
- [ ] #4 rx.upload component is used for file selection with PDF accept filter
- [ ] #5 Results table renders rows from AppState.rows and highlights the selected row
- [ ] #6 Editable fields in the right panel update the corresponding row dict in AppState.rows
- [ ] #7 Log panel displays log entries for AppState.selected_row
- [ ] #8 No JavaScript files are introduced — all interactivity is via Reflex event handlers
<!-- AC:END -->
