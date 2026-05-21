---
id: FOLIO-2
title: >-
  Äriregister client lookup — auto-fill company details from Estonian Business
  Registry
status: To Do
assignee: []
created_date: '2026-05-20 22:43'
labels:
  - feature
  - estonia
  - api-integration
dependencies: []
references:
  - 'https://ariregister.rik.ee'
priority: medium
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When adding a client to a work order, invoice, or the address book, the user should be able to type a company name or registry code and have the app fetch the correct registry code (registrikood), VAT number (KMKR), legal name, and address automatically from the public Estonian Business Registry (Äriregister) API.

This eliminates manual lookups on ariregister.rik.ee and reduces data entry errors on legal documents. The Äriregister exposes a public REST/SOAP API at https://ariregister.rik.ee that returns company data by name or registry code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A search input on the client/work order form queries the Äriregister API as the user types (debounced)
- [ ] #2 Results show company name, registry code, and VAT number in a dropdown
- [ ] #3 Selecting a result auto-fills all relevant fields (name, registry code, VAT, address)
- [ ] #4 Handles companies with no VAT number gracefully (not all Estonian companies are VAT registered)
- [ ] #5 Shows a clear error if the registry is unreachable rather than silently failing
- [ ] #6 Looked-up client data can be saved to a local address book to avoid repeat API calls
<!-- AC:END -->
