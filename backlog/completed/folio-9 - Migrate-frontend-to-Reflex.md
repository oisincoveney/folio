---
id: FOLIO-9
title: Migrate frontend to Reflex
status: Done
assignee: []
created_date: '2026-05-21 10:05'
updated_date: '2026-05-21 16:36'
labels:
  - frontend
  - reflex
  - migration
dependencies: []
references:
  - 'https://reflex.dev'
priority: high
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the current Flask app (single embedded HTML page in app.py) with Reflex, which compiles to React and allows the entire stack to stay in Python. The Flask routes and backend logic (parse.py, storage.py, normalization.py, config.py) should be preserved and ported into Reflex's full-stack model.

This is the foundation for all future UI work — calculators, document review tables, settings, dashboards — so it needs to be done before those features are built out.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Reflex is added as a dependency and the project structure is updated accordingly
- [ ] #2 Existing upload and parse flow is reproduced in Reflex: drag-and-drop upload, parse job triggered, results streamed back to UI
- [ ] #3 Existing save flow is reproduced: confirmed results are saved to the configured storage root with correct filenames and payments.csv append
- [ ] #4 The retry flow is reproduced: failed parse results can be retried from the UI
- [ ] #5 Flask (app.py) and the embedded HTML template are removed
- [ ] #6 All backend logic in parse.py, storage.py, normalization.py, and config.py is retained unchanged
- [ ] #7 The app runs with a single command as before
<!-- AC:END -->
