"""App-level end-to-end tests.

Two tiers:

1. Queue-level: mock `parse.start_parse_job` with a canned event queue. Tests
   the upload → state-streaming → save path without running opencode.
2. Subprocess-level: monkeypatch `folio.parse.OPENCODE` to a fake binary
   (see `fake_opencode` fixture in conftest.py) that prints the JSON opencode
   would have produced. Exercises the real classify + extract subprocess flow.

The Wise CSV format and download roundtrip are verified at the subprocess level
since those are the artifacts users hand to Wise / fetch from the browser.
"""

from __future__ import annotations

import io
import os
import queue
import urllib.request

import polars as pl
import pytest
import reflex as rx
from sqlmodel import select

from folio.services import parser as parse_mod
from folio.config import CSV_COLUMNS, STATIC_FIELDS
from folio.db_models import (
    BankTransactionRecord,
    InvoiceRecord,
    PayslipRecord,
    TaxReceiptRecord,
)
from folio.states.batch import BatchState

from tests._helpers import drain_active_job, make_upload_file, month_prefix

# ----------------------------------------------------------------------------
# Tier 1: queue-level e2e (mock at start_parse_job)
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_parse_save_end_to_end(s3, clean_db, clean_bucket, monkeypatch):
    """Drag a PDF onto the app → mocked parse queue → save to S3 + Postgres."""
    pdf_bytes = b"%PDF-1.4 e2e test invoice"
    file_id = "e2e-fake-fid"

    def fake_start_parse_job(temp_files, _model):
        q: queue.Queue = queue.Queue()
        for name, tmp_path, file_key, source_id in temp_files:
            parse_mod._pending[file_id] = tmp_path  # noqa: SLF001
            q.put({"type": "start", "file_key": file_key, "source_id": source_id,
                   "filename": name})
            q.put({
                "type": "result",
                "file_key": file_key,
                "source_id": source_id,
                "amount": "199.00",
                "targetCurrency": "EUR",
                "company": "E2E Corp",
                "invoiceNumber": "INV-E2E-1",
                "invoiceDate": "2026-05-15",
                "description": "End to end widget",
                "accountNumber": "",
                "paymentReference": "E2E Corp - Inv INV-E2E-1 - End To End Widget",
                "file_id": file_id,
                "doc_type": "invoice",
                "raw_data": {"company": "E2E Corp"},
            })
        q.put({"type": "done"})
        return q

    monkeypatch.setattr("folio.states.batch.start_parse_job", fake_start_parse_job)

    state = BatchState()
    state.model = "test-model"
    async for _ in state.handle_upload([make_upload_file("invoice.pdf", pdf_bytes)]):
        pass
    await drain_active_job(state)

    assert state.rows[0].status == "done"
    state.save_row("invoice.pdf")
    assert state.rows[0].status_ok is True

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=bucket).get("Contents", [])]
    invoice_keys = [k for k in keys if k.startswith(f"{month_prefix()}/invoices/")]
    assert len(invoice_keys) == 1
    assert s3.get_object(Bucket=bucket, Key=invoice_keys[0])["Body"].read() == pdf_bytes

    with rx.session() as session:
        records = list(session.exec(select(InvoiceRecord)).all())
    assert len(records) == 1
    assert records[0].file_key == invoice_keys[0]


@pytest.mark.asyncio
async def test_upload_with_parse_error_marks_row_error_and_blocks_save(
    s3, clean_db, clean_bucket, monkeypatch,
):
    """Parse fails → row goes to error status; save_all_done skips error rows."""

    def fake_start_parse_job(temp_files, _model):
        q: queue.Queue = queue.Queue()
        for name, _tmp, file_key, source_id in temp_files:
            q.put({"type": "start", "file_key": file_key, "source_id": source_id,
                   "filename": name})
            q.put({"type": "result", "file_key": file_key, "source_id": source_id,
                   "error": "opencode failed to extract JSON",
                   "doc_type": "invoice", "raw_data": {}})
        q.put({"type": "done"})
        return q

    monkeypatch.setattr("folio.states.batch.start_parse_job", fake_start_parse_job)

    state = BatchState()
    state.model = "test-model"
    async for _ in state.handle_upload([make_upload_file("bad.pdf", b"%PDF-1.4 bad")]):
        pass
    await drain_active_job(state)

    assert state.rows[0].status == "error"
    state.save_all_done()
    bucket = os.environ["FOLIO_BUCKET_NAME"]
    assert s3.list_objects_v2(Bucket=bucket).get("Contents") in (None, [])


# ----------------------------------------------------------------------------
# Tier 2: subprocess-level e2e (fake opencode binary)
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_subprocess_e2e_uploads_parses_saves_and_downloads(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """Full chain through the real subprocess invocation, with download verify."""
    pdf_bytes = b"%PDF-1.4 real subprocess flow test " + os.urandom(32)

    state = BatchState()
    state.model = "test-model"
    async for _ in state.handle_upload([make_upload_file("invoice.pdf", pdf_bytes)]):
        pass
    await drain_active_job(state)

    row = state.rows[0]
    assert row.status == "done", f"error={row.error!r}"
    assert row.amount == "199.00"
    assert row.target_currency == "EUR"
    assert row.invoice_number == "INV-100"
    assert row.invoice_date == "2026-05-20"
    assert row.account_number == "ACC-42"
    assert "Acme" in row.company
    assert "Inv INV-100" in row.payment_reference

    state.save_row("invoice.pdf")
    assert state.rows[0].status_ok is True

    saved_key = state.rows[0].saved_as
    assert saved_key.startswith(f"{month_prefix()}/invoices/")
    filename = saved_key.split("/")[-1]
    assert "inv-100" in filename
    assert "199-00" in filename
    assert "eur" in filename

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    assert s3.get_object(Bucket=bucket, Key=saved_key)["Body"].read() == pdf_bytes

    with rx.session() as session:
        records = list(session.exec(select(InvoiceRecord)).all())
    assert len(records) == 1
    assert records[0].file_key == saved_key

    # Download via presigned URL → real HTTP GET → bytes match.
    url = s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": saved_key}, ExpiresIn=300,
    )
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        assert resp.read() == pdf_bytes


@pytest.mark.asyncio
async def test_payments_csv_matches_wise_bulk_upload_schema(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """payments.csv columns + static fields match Wise's bulk-payment format."""
    state = BatchState()
    state.model = "test-model"
    async for _ in state.handle_upload(
        [make_upload_file("wise.pdf", b"%PDF-1.4 wise csv schema test")],
    ):
        pass
    await drain_active_job(state)
    state.save_row("wise.pdf")
    assert state.rows[0].status_ok is True

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    csv_obj = s3.get_object(Bucket=bucket, Key=f"{month_prefix()}/payments.csv")
    df = pl.read_csv(io.BytesIO(csv_obj["Body"].read()), infer_schema_length=0)

    assert df.columns == CSV_COLUMNS
    row = df.row(0, named=True)
    assert row["recipientDetail"] == STATIC_FIELDS["recipientDetail"] == "Wise account"
    assert row["sourceCurrency"] == STATIC_FIELDS["sourceCurrency"] == "EUR"
    assert row["amountCurrency"] == STATIC_FIELDS["amountCurrency"] == "source"
    assert row["receiverType"] == STATIC_FIELDS["receiverType"] == "PERSON"
    assert row["targetCurrency"] == "EUR"
    assert row["amount"] == "199.00"
    assert "Inv INV-100" in row["paymentReference"]
    assert row["referenceNumber"] == "1"


@pytest.mark.asyncio
async def test_payments_csv_increments_reference_across_saves(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """Two saves → referenceNumber 1, 2."""
    state = BatchState()
    state.model = "test-model"
    for name in ("first.pdf", "second.pdf"):
        async for _ in state.handle_upload(
            [make_upload_file(name, b"%PDF-1.4 " + name.encode())],
        ):
            pass
        await drain_active_job(state)

    state.save_row("first.pdf")
    state.save_row("second.pdf")

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    csv_obj = s3.get_object(Bucket=bucket, Key=f"{month_prefix()}/payments.csv")
    df = pl.read_csv(io.BytesIO(csv_obj["Body"].read()), infer_schema_length=0)
    assert df["referenceNumber"].to_list() == ["1", "2"]


# ----------------------------------------------------------------------------
# Multi-doc-type subprocess flows
# ----------------------------------------------------------------------------


_DOC_TYPE_PARAMS = [
    ("invoice", "invoices", InvoiceRecord, True),
    ("bank_statement", "bank-statements", BankTransactionRecord, False),
    ("tax_receipt", "tax-receipts", TaxReceiptRecord, False),
    ("payslip", "payslips", PayslipRecord, False),
]


@pytest.mark.parametrize(("doc_type", "prefix", "record_cls", "csv_expected"), _DOC_TYPE_PARAMS)
@pytest.mark.asyncio
async def test_multi_doc_type_e2e_through_subprocess(
    doc_type, prefix, record_cls, csv_expected,
    s3, clean_db, clean_bucket, fake_opencode, monkeypatch,
):
    """Each doc type takes its own subprocess path and persists to the right table.

    Classify returns the doc_type we set; extract uses the matching prompt; save
    lands the PDF under the type-specific S3 prefix and inserts a row in the
    correct table. Only invoice produces payments.csv.
    """
    monkeypatch.setenv("FAKE_DOC_TYPE", doc_type)

    state = BatchState()
    state.model = "test-model"
    name = f"{doc_type}.pdf"
    async for _ in state.handle_upload([make_upload_file(name, b"%PDF-1.4 " + name.encode())]):
        pass
    await drain_active_job(state)

    row = state.rows[0]
    assert row.status == "done", f"error={row.error!r}"
    assert row.doc_type == doc_type

    state.save_row(name)
    assert state.rows[0].status_ok is True, f"err={state.rows[0].error!r}"

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=bucket).get("Contents", [])]
    type_keys = [k for k in keys if k.startswith(f"{month_prefix()}/{prefix}/")]
    assert len(type_keys) == 1

    has_csv = any(k.endswith("payments.csv") for k in keys)
    assert has_csv is csv_expected

    with rx.session() as session:
        records = list(session.exec(select(record_cls)).all())
    assert len(records) == 1
    assert records[0].file_key == type_keys[0]


# ----------------------------------------------------------------------------
# Concurrent uploads
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_uploads_all_parse_successfully(
    clean_db, clean_bucket, fake_opencode,
):
    """Three PDFs uploaded together all reach 'done' via the parallel ThreadPool."""
    state = BatchState()
    state.model = "test-model"

    files = [
        make_upload_file(f"f{i}.pdf", f"%PDF-1.4 file {i}".encode())
        for i in range(3)
    ]
    async for _ in state.handle_upload(files):
        pass
    await drain_active_job(state)

    assert len(state.rows) == 3
    statuses = [r.status for r in state.rows]
    assert statuses == ["done"] * 3, f"statuses={statuses} errors={[r.error for r in state.rows]}"

    # First-arrived start event should have auto-selected; selection is one of ours.
    assert state.selected_file_key in {"f0.pdf", "f1.pdf", "f2.pdf"}


# ----------------------------------------------------------------------------
# Retry after real subprocess failure
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_after_subprocess_failure_eventually_succeeds(
    clean_db, clean_bucket, fake_opencode, tmp_path, monkeypatch,
):
    """First extract subprocess call exits 1; second attempt succeeds.

    Exercises parse.py's MAX_PARSE_ATTEMPTS=2 retry loop. The fake opencode
    increments a counter file and exits non-zero until the counter reaches
    FAKE_FAIL_UNTIL. Classify calls are never failed (separate code path).
    """
    counter = tmp_path / "fake_fail_counter"
    counter.write_text("0")
    monkeypatch.setenv("FAKE_FAILURE_COUNTER", str(counter))
    monkeypatch.setenv("FAKE_FAIL_UNTIL", "1")  # one extract attempt fails, then succeed

    state = BatchState()
    state.model = "test-model"
    async for _ in state.handle_upload([make_upload_file("retry.pdf", b"%PDF-1.4 retry")]):
        pass
    await drain_active_job(state)

    row = state.rows[0]
    assert row.status == "done", f"error={row.error!r}"
    assert row.amount == "199.00"

    # Log trail records the first attempt's failure + the retry kickoff.
    log_bodies = [log.body for log in row.logs]
    assert any("Attempt 1 of 2" in body for body in log_bodies)
    assert any("Retrying after attempt 1" in body for body in log_bodies)
    assert any("Attempt 2 of 2" in body for body in log_bodies)

    # Counter advanced past the failure threshold.
    assert int(counter.read_text()) >= 2  # noqa: PLR2004
