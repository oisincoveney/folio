---
id: FOLIO-9
title: Private git repository for ~/.folio storage with auto-commit on save
status: To Do
assignee: []
created_date: '2026-05-21 09:55'
labels:
  - feature
  - storage
  - backup
dependencies:
  - FOLIO-8.1
priority: medium
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The ~/.folio directory should be a private git repository so every document, work order, and export is automatically versioned and backed up to a remote. After each successful save the app commits the new files and pushes to the configured remote.

PDFs are binary files and will bloat git history — Git LFS should be used for all PDF files. The remote URL is configured once (env var or config.py) and the app handles the rest: init on first run, commit after each save, push in the background without blocking the UI.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ~/.folio is initialised as a git repo on first run if it is not already one
- [ ] #2 Git LFS is configured for *.pdf files to avoid binary bloat in git history
- [ ] #3 A .gitignore is created covering any temp files or OS artifacts (.DS_Store etc)
- [ ] #4 After each successful /save, the new files are staged and committed with a meaningful message (e.g. 'Add invoice stripe_2025-001 — 2025-01')
- [ ] #5 The remote URL is configurable via env var or config.py
- [ ] #6 Push happens in the background after commit and does not block the UI response
- [ ] #7 Push failures are logged and surfaced in the UI but do not fail the save operation
- [ ] #8 If no remote is configured the app commits locally but skips the push
<!-- AC:END -->
