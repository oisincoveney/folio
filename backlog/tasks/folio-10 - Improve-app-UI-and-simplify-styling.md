---
id: FOLIO-10
title: Improve app UI and simplify styling
status: In Progress
assignee:
  - Codex
created_date: '2026-05-21 12:58'
updated_date: '2026-05-21 13:02'
labels:
  - frontend
  - ui
  - design
dependencies: []
priority: medium
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Redesign the current app UI so it feels intentional, usable, and cohesive while reducing unnecessary styling complexity. The app appears to be a Reflex-based financial document ingestion interface with header, file picker, results table, and log panel components. Keep the redesign scoped to the visible app shell and existing user workflows; avoid unrelated feature work.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The main app screen has a cohesive visual direction suited to a financial document workflow.
- [ ] #2 Existing workflows for file selection, parsing status, results display, and logs remain available.
- [ ] #3 Styling is consolidated and easier to reason about, with unnecessary duplicated or conflicting style definitions removed where practical.
- [ ] #4 The UI is responsive enough for common desktop and narrow viewport widths without overlapping text or controls.
- [ ] #5 Relevant automated checks or a local run verification are performed and documented.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Revised approved implementation plan:
1. Use Reflex/Radix theming idiomatically: configure only app-level Radix theme knobs in `rx.App(theme=rx.theme(...))`.
2. Improve the visible UI with Reflex/Radix component structure, variants, spacing props, and theme-aware tokens such as `var(--gray-*)` / `var(--accent-*)`, avoiding a custom color palette or standalone style module.
3. Keep behavior unchanged for file upload, model selection, destination folder picking, row selection, field editing, saving, retrying, and log viewing.
4. Remove unnecessary style clutter where practical by making repeated layout intent clearer inside each component.
5. Run formatting/lint/tests or the closest available Reflex verification, then document results.
<!-- SECTION:PLAN:END -->
