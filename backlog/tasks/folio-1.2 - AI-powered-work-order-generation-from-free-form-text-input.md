---
id: FOLIO-1.2
title: AI-powered work order generation from free-form text input
status: To Do
assignee: []
created_date: '2026-05-20 22:41'
updated_date: '2026-05-22 22:02'
labels:
  - ai
  - ui
dependencies:
  - FOLIO-1.1
parent_task_id: FOLIO-1
priority: medium
ordinal: 1200
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build the UI and AI integration that lets the user describe work in plain language and get a structured work order back. The user types a description like "Set up CI/CD pipeline for client Acme OÜ, 8 hours at €90/hr" and the AI (via Claude API) extracts and structures the relevant fields to populate the work order data model defined in FOLIO-1.1.

The UI should be a simple text area with a "Generate" button. The output is a preview of the populated work order fields, editable before PDF export.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Text input UI exists with a textarea and Generate button
- [ ] #2 AI call uses Claude API to parse free-form description and return structured work order fields (JSON matching the data model from FOLIO-1.1)
- [ ] #3 Generated fields are displayed in an editable preview before export
- [ ] #4 Handles ambiguous input gracefully — prompts user for missing required fields rather than silently omitting them
- [ ] #5 Works for common contractor scenarios: time-based billing, fixed-price work, multi-line items
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Grooming note: Keep blocked behind FOLIO-1.1 so the AI output contract matches the finalized work-order data model.
<!-- SECTION:NOTES:END -->
