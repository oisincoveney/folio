---
id: FOLIO-1.3
title: PDF export for generated work orders
status: To Do
assignee: []
created_date: '2026-05-20 22:42'
labels:
  - pdf
  - export
dependencies:
  - FOLIO-1.1
  - FOLIO-1.2
parent_task_id: FOLIO-1
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement PDF generation from a populated work order, using the template designed in FOLIO-1.1. The user reviews the AI-generated work order (from FOLIO-1.2), then clicks Export/Download to get a print-ready PDF.

The PDF should look professional and be suitable for sending directly to clients. Consider using a headless browser (Puppeteer/Playwright) or a PDF library (pdf-lib, pdfmake, React-PDF) to render the HTML template to PDF.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Clicking an Export button downloads a PDF of the current work order
- [ ] #2 PDF matches the visual template from FOLIO-1.1 faithfully (fonts, layout, fields)
- [ ] #3 PDF is print-ready: A4 size, correct margins, no clipped content
- [ ] #4 Work order number is included and auto-incremented or user-settable
- [ ] #5 PDF filename is meaningful, e.g. work-order-FOLIO-2024-001-ClientName.pdf
<!-- AC:END -->
