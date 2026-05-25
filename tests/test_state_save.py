"""Integration tests for BatchState.save_row.

Drives the real save pipeline: claim a staged PDF from `parse._pending`, upload
to S3 (real boto3 → minio testcontainer), append payments.csv (invoice only),
upsert a record into Postgres (real testcontainer). No moto, no monkeypatching
of `rx.session`.

Note on time: we don't freeze time here. `time_machine` would skew the timestamps
boto3 sends to minio enough to trigger RequestTimeTooSkewed. Tests instead compute
the expected month prefix dynamically from real `datetime.now()`.
"""

from __future__ import annotations

import datetime
import io
import os
import tempfile
import uuid
from pathlib import Path

import polars as pl
from sqlmodel import select

from folio.services import parser as parse_mod
from folio.models import InvoiceRow
from folio.states.batch import BatchState


def _month_prefix() -> str:
    return datetime.datetime.now(tz=datetime.UTC).date().strftime("%Y-%m")


def _state_with_done_invoice(file_id: str, **row_overrides: object) -> BatchState:
    fields: dict[str, object] = {
        "filename_original": "acme.pdf",
        "file_key": "acme.pdf",
        "source_id": "src-1",
        "status": "done",
        "file_id": file_id,
        "amount": "42.00",
        "target_currency": "USD",
        "company": "Acme",
        "invoice_number": "INV-9",
        "invoice_date": "2026-05-01",
        "description": "thing",
        "payment_reference": "Acme - Inv INV-9",
        "doc_type": "invoice",
    }
    fields.update(row_overrides)
    state = BatchState()
    state.rows = [InvoiceRow(**fields)]  # type: ignore[arg-type]
    return state


def _stage_pdf(content: bytes = b"%PDF-1.4 fake invoice") -> tuple[str, str]:
    """Write a temp PDF and register it in parse._pending. Returns (file_id, path)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(content)
    tmp.close()
    file_id = str(uuid.uuid4())
    parse_mod._pending[file_id] = tmp.name  # noqa: SLF001
    return file_id, tmp.name


def _list_keys(s3) -> list[str]:
    page = s3.list_objects_v2(Bucket=os.environ["FOLIO_BUCKET_NAME"])
    return [obj["Key"] for obj in page.get("Contents", [])]


# --- tests ---


def test_save_row_uploads_pdf_to_monthly_s3_key(s3, clean_db, clean_bucket):
    file_id, _ = _stage_pdf()
    state = _state_with_done_invoice(file_id)

    state.save_row("acme.pdf")

    prefix = f"{_month_prefix()}/invoices/"
    invoice_keys = [k for k in _list_keys(s3) if k.startswith(prefix)]
    assert len(invoice_keys) == 1
    obj = s3.get_object(Bucket=os.environ["FOLIO_BUCKET_NAME"], Key=invoice_keys[0])
    assert obj["Body"].read() == b"%PDF-1.4 fake invoice"


def test_save_row_appends_payments_csv_in_s3(s3, clean_db, clean_bucket):
    file_id, _ = _stage_pdf()
    state = _state_with_done_invoice(file_id)

    state.save_row("acme.pdf")

    csv_obj = s3.get_object(
        Bucket=os.environ["FOLIO_BUCKET_NAME"],
        Key=f"{_month_prefix()}/payments.csv",
    )
    df = pl.read_csv(io.BytesIO(csv_obj["Body"].read()), infer_schema_length=0)
    assert len(df) == 1
    assert df["targetCurrency"][0] == "USD"
    assert df["amount"][0] == "42.00"
    assert df["paymentReference"][0] == "Acme - Inv INV-9"
    assert df["referenceNumber"][0] == "1"


def test_save_row_upserts_invoice_record_in_db(s3, clean_db, clean_bucket):
    import reflex as rx  # noqa: PLC0415

    from folio.db_models import InvoiceRecord  # noqa: PLC0415

    file_id, _ = _stage_pdf()
    state = _state_with_done_invoice(file_id)

    state.save_row("acme.pdf")

    with rx.session() as session:
        records = list(session.exec(select(InvoiceRecord)).all())
    assert len(records) == 1
    rec = records[0]
    assert rec.company == "Acme"
    assert rec.amount == "42.00"
    assert rec.invoice_number == "INV-9"
    assert rec.file_key.startswith(f"{_month_prefix()}/invoices/")


def test_save_row_marks_row_status_ok_and_saved_as(s3, clean_db, clean_bucket):
    file_id, _ = _stage_pdf()
    state = _state_with_done_invoice(file_id)

    state.save_row("acme.pdf")

    assert state.rows[0].status_ok is True
    assert state.rows[0].saved_as.startswith(f"{_month_prefix()}/invoices/")
    assert state.rows[0].error == ""


def test_save_row_with_unknown_file_id_sets_error_and_does_not_upload(
    s3, clean_db, clean_bucket,
):
    state = _state_with_done_invoice("nonexistent-file-id")

    state.save_row("acme.pdf")

    assert "already saved or session expired" in state.rows[0].error
    assert state.rows[0].status_ok is False
    assert _list_keys(s3) == []


def test_save_row_with_unknown_file_key_is_a_noop(s3, clean_db, clean_bucket):
    file_id, _ = _stage_pdf()
    state = _state_with_done_invoice(file_id)

    state.save_row("ghost.pdf")

    assert state.rows[0].status_ok is False
    assert _list_keys(s3) == []


def test_save_row_increments_payments_csv_reference_number(s3, clean_db, clean_bucket):
    fid1, _ = _stage_pdf(b"%PDF-1.4 invoice 1")
    fid2, _ = _stage_pdf(b"%PDF-1.4 invoice 2")

    state = BatchState()
    state.rows = [
        InvoiceRow(file_key="a.pdf", source_id="src-a", status="done", file_id=fid1,
                   amount="1.00", target_currency="EUR", company="A",
                   invoice_number="INV-1", payment_reference="A - Inv INV-1",
                   doc_type="invoice"),
        InvoiceRow(file_key="b.pdf", source_id="src-b", status="done", file_id=fid2,
                   amount="2.00", target_currency="USD", company="B",
                   invoice_number="INV-2", payment_reference="B - Inv INV-2",
                   doc_type="invoice"),
    ]

    state.save_row("a.pdf")
    state.save_row("b.pdf")

    csv_obj = s3.get_object(
        Bucket=os.environ["FOLIO_BUCKET_NAME"],
        Key=f"{_month_prefix()}/payments.csv",
    )
    df = pl.read_csv(io.BytesIO(csv_obj["Body"].read()), infer_schema_length=0)
    assert df["referenceNumber"].to_list() == ["1", "2"]


def test_save_row_dedupes_db_record_on_repeat_save_same_content(
    s3, clean_db, clean_bucket,
):
    """The unique key is (file_key, content_hash). Same row saved twice → one record."""
    import reflex as rx  # noqa: PLC0415

    from folio.db_models import InvoiceRecord  # noqa: PLC0415

    file_id, pdf_path = _stage_pdf(b"%PDF-1.4 same bytes")
    state = _state_with_done_invoice(file_id)
    state.save_row("acme.pdf")

    # Re-save the SAME row (same company/amount/… → same filename → same file_key,
    # same bytes → same content_hash). upsert should update in place, not insert.
    file_id2 = str(uuid.uuid4())
    Path(pdf_path).write_bytes(b"%PDF-1.4 same bytes")  # recreate (first save unlinked it)
    parse_mod._pending[file_id2] = pdf_path  # noqa: SLF001
    state.rows[0] = state.rows[0].model_copy(update={
        "file_id": file_id2, "status_ok": False, "saved_as": "",
    })
    state.save_row("acme.pdf")

    with rx.session() as session:
        records = list(session.exec(select(InvoiceRecord)).all())
    assert len(records) == 1
    assert records[0].company == "Acme"


def test_save_row_bank_statement_skips_payments_csv_and_uses_correct_prefix(
    s3, clean_db, clean_bucket,
):
    import reflex as rx  # noqa: PLC0415

    from folio.db_models import BankTransactionRecord  # noqa: PLC0415

    file_id, _ = _stage_pdf()
    state = _state_with_done_invoice(
        file_id,
        doc_type="bank_statement",
        raw_data={
            "transaction_date": "2026-05-01", "amount": "100.00", "currency": "EUR",
            "counterparty": "Wise", "description": "Transfer",
            "running_balance": "500.00",
        },
    )

    state.save_row("acme.pdf")

    keys = _list_keys(s3)
    assert any(k.startswith(f"{_month_prefix()}/bank-statements/") for k in keys)
    assert not any(k == f"{_month_prefix()}/payments.csv" for k in keys)

    with rx.session() as session:
        records = list(session.exec(select(BankTransactionRecord)).all())
    assert len(records) == 1
    assert records[0].counterparty == "Wise"
    assert records[0].running_balance == "500.00"


def test_save_all_done_only_saves_done_rows(s3, clean_db, clean_bucket):
    fid1, _ = _stage_pdf()
    fid2, _ = _stage_pdf()
    fid3, _ = _stage_pdf()

    state = BatchState()
    state.rows = [
        InvoiceRow(file_key="ok.pdf", source_id="s1", status="done", file_id=fid1,
                   amount="1.00", target_currency="EUR", company="A",
                   invoice_number="I1", payment_reference="r1", doc_type="invoice"),
        InvoiceRow(file_key="err.pdf", source_id="s2", status="error", file_id=fid2,
                   amount="1.00", target_currency="EUR", company="B",
                   invoice_number="I2", payment_reference="r2", doc_type="invoice"),
        InvoiceRow(file_key="saved.pdf", source_id="s3", status="done",
                   status_ok=True, file_id=fid3,
                   amount="1.00", target_currency="EUR", company="C",
                   invoice_number="I3", payment_reference="r3", doc_type="invoice"),
    ]

    state.save_all_done()

    invoice_keys = [k for k in _list_keys(s3) if "/invoices/" in k]
    assert len(invoice_keys) == 1  # only the done+unsaved row
    assert state.rows[0].status_ok is True
    assert state.rows[1].status_ok is False  # error row untouched
    assert state.rows[2].status_ok is True   # already saved
