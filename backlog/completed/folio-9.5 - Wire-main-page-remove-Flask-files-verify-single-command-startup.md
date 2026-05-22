---
id: FOLIO-9.5
title: 'Wire main page, remove Flask files, verify single-command startup'
status: Done
assignee: []
created_date: '2026-05-21 10:24'
updated_date: '2026-05-22 13:29'
labels:
  - frontend
  - reflex
  - migration
dependencies:
  - FOLIO-9.1
  - FOLIO-9.2
  - FOLIO-9.3
  - FOLIO-9.4
parent_task_id: FOLIO-9
priority: high
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Compose the finished components into the main Reflex page and remove all Flask artifacts. This is the final integration and cleanup subtask for FOLIO-9.

What to do:
- Update folio/folio.py to import and compose header, file_picker, results_table, and log_panel into a single rx.vstack (or equivalent layout) that matches the existing full-height flex-column layout.
- Add an on_load event on the index page that calls AppState.load_models so the model list is populated on first visit.
- Delete app.py, templates/, and static/ from the project root — they are fully replaced by the Reflex app.
- Confirm pyproject.toml has no remaining Flask references.
- Confirm `reflex run` is the single startup command (no separate flask run needed).
- Manually verify the full user flow: drag-and-drop PDFs → parse starts → results stream in → editable fields → save to folder → payments.csv appended → retry a failed row.

This subtask depends on FOLIO-9.1 through FOLIO-9.4 being complete.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 folio/folio.py composes all four components and registers the index page with on_load=AppState.load_models
- [x] #2 app.py, templates/, and static/ are deleted
- [x] #3 pyproject.toml contains no reference to flask
- [x] #4 `reflex run` is the only command needed to start the app
- [x] #5 Drag-and-drop upload triggers parse and streams results to the UI (FOLIO-9 AC #2)
- [x] #6 Save flow writes the PDF and appends to payments.csv (FOLIO-9 AC #3)
- [x] #7 Retry flow re-parses a failed file from the UI (FOLIO-9 AC #4)
- [x] #8 parse.py, storage.py, normalization.py, config.py are unmodified (FOLIO-9 AC #6)
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Shipped in commit ba2bddd. folio/folio.py composes the components and registers the index page with on_load=AppState.load_models. Flask artifacts (app.py, templates/, static/) were removed; `reflex run` is the single startup command.
<!-- SECTION:FINAL_SUMMARY:END -->
