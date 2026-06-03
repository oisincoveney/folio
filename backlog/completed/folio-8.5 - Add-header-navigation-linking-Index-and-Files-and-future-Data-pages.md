---
id: FOLIO-8.5
title: Add header navigation linking Index and Files (and future Data) pages
status: Done
assignee: []
created_date: '2026-05-25 10:41'
updated_date: '2026-05-25 11:40'
labels:
  - ui
  - navigation
dependencies: []
parent_task_id: FOLIO-8
priority: high
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Reflex app already serves `/` (index/upload) and `/files` (S3 file browser), but the header in `folio/components/header.py` has no link to either. The only way to reach `/files` is to type the URL by hand, so users cannot discover that documents are actually being stored.

Add primary navigation in the header for the existing pages, with the active page highlighted. Leave a slot for the forthcoming Data/records page (FOLIO-8.6) so adding it later is a one-line change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Header exposes navigation links for Index (`/`) and Files (`/files`) on every page
- [x] #2 Active page link is visually distinguished from inactive links
- [x] #3 Navigation is keyboard-focusable and uses Reflex's client-side routing (no full reload)
- [x] #4 Layout still works on the existing pages without breaking the model dropdown / refresh button
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Header now exposes Parse / Files / Data nav links with active-page highlight via `rx.State.router.page.path`. Client-side routing via `rx.link`, no full reloads. Implemented in `folio/components/header.py` only; the `Data` link 404s until FOLIO-8.6 ships (intentional, called out in plan).
<!-- SECTION:FINAL_SUMMARY:END -->
