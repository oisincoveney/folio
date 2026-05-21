---
id: FOLIO-8.2
title: >-
  Expand opencode extraction schema to cover bank statements, tax receipts, and
  payslips
status: To Do
assignee: []
created_date: '2026-05-20 22:51'
updated_date: '2026-05-21 06:33'
labels:
  - ai
  - extraction
  - opencode
dependencies:
  - FOLIO-8.1
references:
  - 'https://github.com/anthropics/anthropic-sdk-python'
parent_task_id: FOLIO-8
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The current PARSE_PROMPT in config.py extracts invoice/payment fields only (amount, currency, company, invoiceNumber, invoiceDate, description, accountNumber). To feed the tax calculators the app needs to extract data from other document types too.

The AI parsing is done by calling opencode via subprocess (parse.py: _process_one → subprocess.Popen([OPENCODE, "run", ...])) — this is the existing mechanism and should continue to be used. The work here is: detect document type, route to the appropriate extraction prompt, and extend InvoiceData (or add new Pydantic models) to cover the additional schemas.

Additional document types and fields needed:
- Bank statement: transaction date, amount, currency, counterparty, description, running balance
- Tax receipt (EE/US): tax type (income/social/VAT/corporate), period, amount paid, jurisdiction
- Payslip: gross salary, income tax withheld, social tax, net pay, period
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Document type is detected (invoice, bank statement, tax receipt, payslip) — either by a first opencode call or by prompt instruction
- [ ] #2 Separate Pydantic models exist for each document type with appropriate fields
- [ ] #3 PARSE_PROMPT (or equivalent per-type prompts) in config.py are updated to request the correct schema per document type
- [ ] #4 Extracted records include a doc_type field so downstream storage can route them correctly
- [ ] #5 Existing invoice extraction behaviour is unchanged
- [ ] #6 Multi-currency amounts preserve the currency code alongside the value
<!-- AC:END -->
