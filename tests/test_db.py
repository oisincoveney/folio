"""DB record persistence tests — requires a running Postgres instance."""

import contextlib
import os

import pytest
from sqlalchemy import create_engine, text
from sqlmodel import Session, select

_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://folio:folio@localhost:5432/folio"
)


def _pg_available() -> bool:
    try:
        engine = create_engine(
            _DB_URL, connect_args={"connect_timeout": 2}
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:  # noqa: BLE001, S110
        return False
    else:
        return True


pytestmark = pytest.mark.skipif(
    not _pg_available(),
    reason="Postgres not reachable; start docker-compose postgres to run DB tests",
)


@pytest.fixture(scope="module")
def db_engine():
    from folio.db_models import (
        BankTransactionRecord,
        InvoiceRecord,
        PayslipRecord,
        TaxReceiptRecord,
    )

    engine = create_engine(_DB_URL)
    for tbl in [
        InvoiceRecord.__table__,
        BankTransactionRecord.__table__,
        TaxReceiptRecord.__table__,
        PayslipRecord.__table__,
    ]:
        tbl.create(engine, checkfirst=True)
    yield engine
    for tbl in reversed([
        InvoiceRecord.__table__,
        BankTransactionRecord.__table__,
        TaxReceiptRecord.__table__,
        PayslipRecord.__table__,
    ]):
        tbl.drop(engine, checkfirst=True)
    engine.dispose()


@pytest.fixture(autouse=True)
def clear_tables(db_engine):
    yield
    from folio.db_models import (
        BankTransactionRecord,
        InvoiceRecord,
        PayslipRecord,
        TaxReceiptRecord,
    )
    with Session(db_engine) as session:
        for model_cls in [InvoiceRecord, BankTransactionRecord, TaxReceiptRecord, PayslipRecord]:
            session.execute(model_cls.__table__.delete())
        session.commit()


@pytest.fixture
def db(db_engine, monkeypatch):
    import folio.db_models as db_mod

    @contextlib.contextmanager
    def _mock_rx_session():
        with Session(db_engine) as session:
            yield session

    monkeypatch.setattr(db_mod.rx, "session", _mock_rx_session)
    return db_engine


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


def test_upsert_inserts_new_invoice(db):
    from folio.db_models import InvoiceRecord

    InvoiceRecord.upsert(_invoice("2026-05/invoices/a.pdf", "hash1"))

    with Session(db) as session:
        rows = list(session.exec(
            select(InvoiceRecord).where(InvoiceRecord.file_key == "2026-05/invoices/a.pdf")
        ))
    assert len(rows) == 1
    assert rows[0].company == "Test Corp"


def test_upsert_deduplicates_on_same_hash(db):
    from folio.db_models import InvoiceRecord

    data = _invoice("2026-05/invoices/a.pdf", "hash1", company="First Name")
    InvoiceRecord.upsert(data)
    InvoiceRecord.upsert({**data, "company": "Updated Name"})

    with Session(db) as session:
        rows = list(session.exec(
            select(InvoiceRecord).where(InvoiceRecord.file_key == "2026-05/invoices/a.pdf")
        ))
    assert len(rows) == 1
    assert rows[0].company == "Updated Name"


def test_upsert_different_hash_inserts_new_record(db):
    from folio.db_models import InvoiceRecord

    data = _invoice("2026-05/invoices/a.pdf", "hash1")
    InvoiceRecord.upsert(data)
    InvoiceRecord.upsert({**data, "content_hash": "hash2", "company": "Other Corp"})

    with Session(db) as session:
        rows = list(session.exec(
            select(InvoiceRecord).where(InvoiceRecord.file_key == "2026-05/invoices/a.pdf")
        ))
    assert len(rows) == 2  # noqa: PLR2004


def test_outstanding_returns_unsettled_invoices(db):
    from folio.db_models import InvoiceRecord

    InvoiceRecord.upsert(_invoice("2026-05/invoices/a.pdf", "h1", status="outstanding"))
    InvoiceRecord.upsert(_invoice("2026-05/invoices/b.pdf", "h2", status="paid"))

    outstanding = InvoiceRecord.outstanding()
    assert len(outstanding) == 1
    assert outstanding[0].status == "outstanding"


def test_by_year_filters_by_saved_at(db):
    from folio.db_models import InvoiceRecord

    InvoiceRecord.upsert(_invoice("2026-05/invoices/a.pdf", "h1", saved_at="2026-05-22"))
    InvoiceRecord.upsert(_invoice("2025-12/invoices/b.pdf", "h2", saved_at="2025-12-01"))

    rows_2026 = InvoiceRecord.by_year(2026)
    assert len(rows_2026) == 1
    assert rows_2026[0].file_key == "2026-05/invoices/a.pdf"
