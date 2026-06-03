---
id: FOLIO-1
title: Estonian work order generation with AI assistance
status: To Do
assignee: []
created_date: '2026-05-20 22:41'
updated_date: '2026-05-22 22:02'
labels:
  - feature
  - ai
  - documents
dependencies: []
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Enable the user to generate compliant PDF work orders for their Estonian company by typing a free-form description of the work. An AI layer (Claude Code / LLM) interprets the description and populates a structured work order template, which is then exported as a PDF ready to send to clients.

This is a self-employed contractor workflow: the user describes what they did or will do, and gets a professional, correctly formatted work order document without manual data entry.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A reusable Estonian work-order data model and visual template exist
- [ ] #2 Free-form work descriptions can be parsed into structured editable work-order fields
- [ ] #3 Generated work orders can be exported as print-ready PDFs
- [ ] #4 The flow supports common contractor billing cases, including hourly, fixed-price, and multiple line items
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Grooming note: With self-contained storage complete, this is the next coherent feature stream. Execute through FOLIO-1.1, then FOLIO-1.2, then FOLIO-1.3.
<!-- SECTION:NOTES:END -->
