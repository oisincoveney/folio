"""DB record persistence tests.

Uses the testcontainer Postgres set up by `tests/conftest.py`. Real `rx.session`,
no monkeypatching, no skip predicate.
"""

import reflex as rx
from sqlmodel import select

from folio.db_models import InvoiceRecord


def _invoice(file_key: str, content_hash: str, **overrides: str) -> dict:
    return {
        "file_key": file_key,
        "content_hash": content_hash,
        "saved_at": "2026-05-22",
        "doc_type": "invoice",
        "amount": "100.00",
        "currency": "EUR",
        "company": "Test Corp",
        "invoice_number": "INV-001",
        "invoice_date": "2026-05-01",
        "description": "Test service",
        "account_number": "",
        "payment_reference": "Test Corp - Inv INV-001",
        "status": "outstanding",
        **overrides,
    }


def test_upsert_inserts_new_invoice(clean_db):
    InvoiceRecord.upsert(_invoice("2026-05/invoices/a.pdf", "hash1"))

    with rx.session() as session:
        rows = list(session.exec(
            select(InvoiceRecord).where(InvoiceRecord.file_key == "2026-05/invoices/a.pdf"),
        ).all())
    assert len(rows) == 1
    assert rows[0].company == "Test Corp"


def test_upsert_deduplicates_on_same_key_and_hash(clean_db):
    data = _invoice("2026-05/invoices/a.pdf", "hash1", company="First Name")
    InvoiceRecord.upsert(data)
    InvoiceRecord.upsert({**data, "company": "Updated Name"})

    with rx.session() as session:
        rows = list(session.exec(
            select(InvoiceRecord).where(InvoiceRecord.file_key == "2026-05/invoices/a.pdf"),
        ).all())
    assert len(rows) == 1
    assert rows[0].company == "Updated Name"


def test_upsert_different_hash_inserts_new_record(clean_db):
    data = _invoice("2026-05/invoices/a.pdf", "hash1")
    InvoiceRecord.upsert(data)
    InvoiceRecord.upsert({**data, "content_hash": "hash2", "company": "Other Corp"})

    with rx.session() as session:
        rows = list(session.exec(
            select(InvoiceRecord).where(InvoiceRecord.file_key == "2026-05/invoices/a.pdf"),
        ).all())
    assert len(rows) == 2  # noqa: PLR2004


def test_outstanding_returns_unsettled_invoices(clean_db):
    InvoiceRecord.upsert(_invoice("2026-05/invoices/a.pdf", "h1", status="outstanding"))
    InvoiceRecord.upsert(_invoice("2026-05/invoices/b.pdf", "h2", status="paid"))

    outstanding = InvoiceRecord.outstanding()
    assert len(outstanding) == 1
    assert outstanding[0].status == "outstanding"


def test_by_year_filters_by_saved_at(clean_db):
    InvoiceRecord.upsert(_invoice("2026-05/invoices/a.pdf", "h1", saved_at="2026-05-22"))
    InvoiceRecord.upsert(_invoice("2025-12/invoices/b.pdf", "h2", saved_at="2025-12-01"))

    rows_2026 = InvoiceRecord.by_year(2026)
    assert len(rows_2026) == 1
    assert rows_2026[0].file_key == "2026-05/invoices/a.pdf"
