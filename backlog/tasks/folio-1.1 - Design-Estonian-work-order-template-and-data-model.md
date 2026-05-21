---
id: FOLIO-1.1
title: Design Estonian work order template and data model
status: To Do
assignee: []
created_date: '2026-05-20 22:41'
labels:
  - template
  - data-model
dependencies: []
parent_task_id: FOLIO-1
ordinal: 1000
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
