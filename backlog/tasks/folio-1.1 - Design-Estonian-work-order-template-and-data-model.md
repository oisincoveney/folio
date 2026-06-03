---
id: FOLIO-1.1
title: Design Estonian work order template and data model
status: To Do
assignee: []
created_date: '2026-05-20 22:41'
updated_date: '2026-05-22 22:02'
labels:
  - template
  - data-model
dependencies: []
parent_task_id: FOLIO-1
priority: high
ordinal: 1100
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Define the structure and required fields for a work order that is valid for an Estonian company. Estonian business documents typically require: seller company name, registry code (registrikood), VAT number (KMKR), address, buyer details, work description, quantity/unit, price, VAT rate (20%), total, and date.

Design a template (visual layout + data schema) that will be used as the source of truth for both the AI generation step and the PDF rendering step.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Work order data model covers all fields required under Estonian commercial law (seller, buyer, registry code, VAT number, line items, VAT, totals, date, work order number)
- [ ] #2 A visual template mockup or HTML/CSS layout exists for the work order document
- [ ] #3 Template handles at least multi-line work descriptions and multiple line items
- [ ] #4 Template is localised for Estonian context (EUR currency, 20% VAT, Estonian/English bilingual optional)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Grooming note: Next actionable implementation task. This should define the schema and template that FOLIO-1.2, FOLIO-1.3, and client lookup integration build on.
<!-- SECTION:NOTES:END -->
