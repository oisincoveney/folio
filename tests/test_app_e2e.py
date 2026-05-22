"""App-level end-to-end test.

Exercises the full upload → parse → save chain through real `AppState`, with the
opencode subprocess mocked at the `parse.start_parse_job` boundary. All
downstream effects (S3 upload, payments.csv append, Postgres upsert) hit the
real testcontainers from conftest.py.
"""

from __future__ import annotations

import datetime
import io
import os
import queue
from pathlib import Path

import polars as pl
import pytest
import reflex as rx
from sqlmodel import select

from folio import parse as parse_mod
from folio.state import AppState


def _month_prefix() -> str:
    return datetime.datetime.now(tz=datetime.UTC).date().strftime("%Y-%m")


def _upload_file(name: str, data: bytes) -> rx.UploadFile:
    return rx.UploadFile(file=io.BytesIO(data), path=Path(name))


async def _drain_queue(state: AppState, q: queue.Queue) -> None:
    """Pull events off the parse queue and apply them to state.

    Replaces stream_parse's @rx.event(background=True) loop so tests don't have
    to drive Reflex's background-event machinery.
    """
    while True:
        try:
            event = q.get(block=True, timeout=2)
        except queue.Empty:
            break
        state._apply_event(event)  # noqa: SLF001
        if event.get("type") == "done":
            break


@pytest.mark.asyncio
async def test_upload_parse_save_end_to_end(s3, clean_db, clean_bucket, monkeypatch):
    """Drag a PDF onto the app → mocked opencode parse → save to S3 + Postgres."""
    from folio.db_models import InvoiceRecord  # noqa: PLC0415

    pdf_bytes = b"%PDF-1.4 e2e test invoice"
    file_id = "e2e-fake-fid"

    # The seam: mock the subprocess boundary. start_parse_job normally shells out
    # to opencode; here we hand back a queue of canned events that mimic a real
    # invoice extraction result.
    def fake_start_parse_job(temp_files, _model):
        q: queue.Queue = queue.Queue()
        for name, tmp_path, file_key, source_id in temp_files:
            # Register the temp PDF in the pending dict so claim_pending finds it.
            parse_mod._pending[file_id] = tmp_path  # noqa: SLF001
            q.put({
                "type": "start",
                "file_key": file_key,
                "source_id": source_id,
                "filename": name,
            })
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

    # state.py does `from folio.parse import start_parse_job`, so the binding to
    # patch is on `folio.state`, not on `folio.parse`.
    monkeypatch.setattr("folio.state.start_parse_job", fake_start_parse_job)

    # 1. Drive the upload handler.
    state = AppState()
    state.model = "test-model"  # bypass parse.get_default_model()
    upload_gen = state.handle_upload([_upload_file("invoice.pdf", pdf_bytes)])
    async for _ in upload_gen:
        # handle_upload yields the stream_parse event spec; nothing to assert here.
        pass

    # 2. Pull the parse events off the queue and apply them to state (stand-in
    # for the background stream_parse handler).
    from folio.state import _active_jobs  # noqa: PLC0415

    job_id, q = next(iter(_active_jobs.items()))
    await _drain_queue(state, q)
    _active_jobs.pop(job_id, None)

    # 3. State should reflect a successfully-parsed invoice.
    assert len(state.rows) == 1
    row = state.rows[0]
    assert row.file_key == "invoice.pdf"
    assert row.status == "done"
    assert row.amount == "199.00"
    assert row.target_currency == "EUR"
    assert row.company == "E2E Corp"
    assert row.invoice_number == "INV-E2E-1"
    assert row.payment_reference.startswith("E2E Corp")

    # 4. Save: this should land bytes in S3, append the payments.csv, and upsert
    # an InvoiceRecord into Postgres.
    state.save_row("invoice.pdf")

    assert state.rows[0].status_ok is True
    assert state.rows[0].error == ""

    # S3: PDF object
    bucket = os.environ["FOLIO_BUCKET_NAME"]
    prefix = f"{_month_prefix()}/invoices/"
    keys = [
        obj["Key"]
        for obj in s3.list_objects_v2(Bucket=bucket).get("Contents", [])
    ]
    invoice_keys = [k for k in keys if k.startswith(prefix)]
    assert len(invoice_keys) == 1
    body = s3.get_object(Bucket=bucket, Key=invoice_keys[0])["Body"].read()
    assert body == pdf_bytes

    # S3: payments.csv
    csv_obj = s3.get_object(Bucket=bucket, Key=f"{_month_prefix()}/payments.csv")
    df = pl.read_csv(io.BytesIO(csv_obj["Body"].read()), infer_schema_length=0)
    assert len(df) == 1
    assert df["targetCurrency"][0] == "EUR"
    assert df["amount"][0] == "199.00"
    assert df["paymentReference"][0].startswith("E2E Corp")

    # Postgres: record
    with rx.session() as session:
        records = list(session.exec(select(InvoiceRecord)).all())
    assert len(records) == 1
    assert records[0].company == "E2E Corp"
    assert records[0].invoice_number == "INV-E2E-1"
    assert records[0].file_key == invoice_keys[0]


@pytest.mark.asyncio
async def test_upload_with_parse_error_marks_row_error_and_blocks_save(
    s3, clean_db, clean_bucket, monkeypatch,
):
    """Parse fails → row goes to error status; save_row is a no-op (no claim)."""

    def fake_start_parse_job(temp_files, _model):
        q: queue.Queue = queue.Queue()
        for name, _tmp, file_key, source_id in temp_files:
            q.put({
                "type": "start", "file_key": file_key, "source_id": source_id,
                "filename": name,
            })
            q.put({
                "type": "result",
                "file_key": file_key,
                "source_id": source_id,
                "error": "opencode failed to extract JSON",
                "doc_type": "invoice",
                "raw_data": {},
            })
        q.put({"type": "done"})
        return q

    # state.py does `from folio.parse import start_parse_job`, so the binding to
    # patch is on `folio.state`, not on `folio.parse`.
    monkeypatch.setattr("folio.state.start_parse_job", fake_start_parse_job)

    state = AppState()
    state.model = "test-model"
    upload_gen = state.handle_upload([_upload_file("bad.pdf", b"%PDF-1.4 bad")])
    async for _ in upload_gen:
        pass

    from folio.state import _active_jobs  # noqa: PLC0415

    job_id, q = next(iter(_active_jobs.items()))
    await _drain_queue(state, q)
    _active_jobs.pop(job_id, None)

    assert state.rows[0].status == "error"
    assert "opencode failed" in state.rows[0].error

    # save_all_done should skip error rows entirely.
    state.save_all_done()

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    assert s3.list_objects_v2(Bucket=bucket).get("Contents") in (None, [])
