"""App-level end-to-end tests.

Two tiers:

1. Queue-level: mock `parse.start_parse_job` with a canned event queue. Tests
   the upload → state-streaming → save path without running opencode.
2. Subprocess-level: monkeypatch `folio.parse.OPENCODE` to a tiny fake binary
   that prints the JSON opencode would have produced. Exercises the real
   classify + extract subprocess flow (argv, JSON line parsing, retry logic)
   without needing a real LLM. Plus a download-roundtrip via presigned URL.

The Wise CSV format is verified at column-order + static-field level in the
subprocess test, since that's the produced artifact users will hand to Wise.
"""

from __future__ import annotations

import datetime
import io
import json
import os
import queue
import stat
import urllib.request
from pathlib import Path

import polars as pl
import pytest
import reflex as rx
from sqlmodel import select

from folio import parse as parse_mod
from folio.config import CSV_COLUMNS, STATIC_FIELDS
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
            event = q.get(block=True, timeout=10)
        except queue.Empty:
            break
        state._apply_event(event)  # noqa: SLF001
        if event.get("type") == "done":
            break


async def _drain_active_job(state: AppState) -> None:
    """Find the queue from handle_upload's _active_jobs and drain it."""
    from folio.state import _active_jobs  # noqa: PLC0415

    job_id, q = next(iter(_active_jobs.items()))
    await _drain_queue(state, q)
    _active_jobs.pop(job_id, None)


# ----------------------------------------------------------------------------
# Tier 1: queue-level e2e (mock at start_parse_job)
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_parse_save_end_to_end(s3, clean_db, clean_bucket, monkeypatch):
    """Drag a PDF onto the app → mocked parse queue → save to S3 + Postgres."""
    from folio.db_models import InvoiceRecord  # noqa: PLC0415

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

    monkeypatch.setattr("folio.state.start_parse_job", fake_start_parse_job)

    state = AppState()
    state.model = "test-model"
    async for _ in state.handle_upload([_upload_file("invoice.pdf", pdf_bytes)]):
        pass
    await _drain_active_job(state)

    row = state.rows[0]
    assert row.status == "done"
    assert row.amount == "199.00"
    assert row.company == "E2E Corp"

    state.save_row("invoice.pdf")
    assert state.rows[0].status_ok is True

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    keys = [
        o["Key"]
        for o in s3.list_objects_v2(Bucket=bucket).get("Contents", [])
    ]
    invoice_keys = [k for k in keys if k.startswith(f"{_month_prefix()}/invoices/")]
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
    """Parse fails → row goes to error status; save_row is a no-op (no claim)."""

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

    monkeypatch.setattr("folio.state.start_parse_job", fake_start_parse_job)

    state = AppState()
    state.model = "test-model"
    async for _ in state.handle_upload([_upload_file("bad.pdf", b"%PDF-1.4 bad")]):
        pass
    await _drain_active_job(state)

    assert state.rows[0].status == "error"
    state.save_all_done()
    assert s3.list_objects_v2(Bucket=os.environ["FOLIO_BUCKET_NAME"]).get("Contents") in (
        None, [],
    )


# ----------------------------------------------------------------------------
# Tier 2: subprocess-level e2e (fake opencode binary)
# ----------------------------------------------------------------------------


# A tiny standalone Python script that we drop on disk and point OPENCODE at.
# parse.py invokes `[OPENCODE, "run", "--format", "json", "--file", PDF, "-m",
# MODEL, PROMPT]`. The prompt is the last argv; we branch on its content and
# print one JSON line of opencode's stream format containing the canned text
# the upstream code would extract.
_FAKE_OPENCODE = '''\
#!/usr/bin/env python3
"""Fake opencode binary for E2E testing. Prints canned JSON to stdout."""
import json
import sys

argv = sys.argv
# opencode subcommand: argv[1] is "run" or "models"
if len(argv) < 2 or argv[1] != "run":
    sys.exit(0)

prompt = argv[-1]

if "Classify the document type" in prompt:
    payload = {"doc_type": "invoice"}
elif "PDF invoice" in prompt:
    payload = {
        "amount": "199.00",
        "targetCurrency": "EUR",
        "company": "Acme Test Vendor",
        "invoiceNumber": "INV-100",
        "invoiceDate": "2026-05-20",
        "description": "Cloud Hosting May 2026",
        "accountNumber": "ACC-42",
    }
elif "PDF bank statement" in prompt:
    payload = {
        "transaction_date": "2026-05-15", "amount": "500.00", "currency": "EUR",
        "counterparty": "Wise", "description": "Transfer",
        "running_balance": "1500.00",
    }
else:
    payload = {}

print(json.dumps({"type": "text", "part": {"text": json.dumps(payload)}}))
'''


@pytest.fixture
def fake_opencode(tmp_path, monkeypatch):
    """Drop a fake opencode binary on disk and point parse.OPENCODE at it.

    parse.py imports `OPENCODE` from config at load time, so we monkeypatch the
    *parse module's* binding — patching `folio.config.OPENCODE` is too late.
    """
    script = tmp_path / "fake_opencode"
    script.write_text(_FAKE_OPENCODE)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setattr("folio.parse.OPENCODE", str(script))
    return script


@pytest.mark.asyncio
async def test_full_subprocess_e2e_uploads_parses_saves_and_downloads(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """Full chain through the real subprocess invocation, with download verify.

    1. Upload a PDF via real handle_upload.
    2. Real `start_parse_job` runs, which spawns subprocess.Popen calls against
       our fake opencode. The classify pass returns doc_type=invoice; the
       extract pass returns canned invoice fields.
    3. State populates from the result event.
    4. save_row uploads the PDF to minio under YYYY-MM/invoices/ with the
       generated filename, appends payments.csv, upserts the DB record.
    5. Generate a presigned URL for the saved object and HTTP GET it back —
       bytes should match the originally uploaded PDF.
    """
    from folio.db_models import InvoiceRecord  # noqa: PLC0415

    pdf_bytes = b"%PDF-1.4 real subprocess flow test " + os.urandom(32)

    state = AppState()
    state.model = "test-model"  # skip get_default_model (would shell out for models list)

    # Upload (real handle_upload, real subprocess Popen via fake_opencode).
    async for _ in state.handle_upload([_upload_file("invoice.pdf", pdf_bytes)]):
        pass
    await _drain_active_job(state)

    # State reflects the extraction.
    row = state.rows[0]
    assert row.status == "done", f"error={row.error!r}"
    assert row.amount == "199.00"
    assert row.target_currency == "EUR"
    assert row.invoice_number == "INV-100"
    assert row.invoice_date == "2026-05-20"
    assert row.account_number == "ACC-42"
    # company comes from vendor-normalizer + the fake's "Acme Test Vendor"
    assert "Acme" in row.company
    # Reference is synthesized from company/invoice/description; must mention all.
    assert "Inv INV-100" in row.payment_reference

    # Save.
    state.save_row("invoice.pdf")
    assert state.rows[0].status_ok is True
    assert state.rows[0].error == ""

    # S3 key: YYYY-MM/invoices/YYYY-MM-DD_<slug>_<inv>_<amount>-<curr>.pdf
    saved_key = state.rows[0].saved_as
    assert saved_key.startswith(f"{_month_prefix()}/invoices/")
    filename = saved_key.split("/")[-1]
    assert filename.endswith(".pdf")
    assert "inv-100" in filename
    assert "199-00" in filename
    assert "eur" in filename

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    obj = s3.get_object(Bucket=bucket, Key=saved_key)
    assert obj["Body"].read() == pdf_bytes

    # DB record landed and points at the same key.
    with rx.session() as session:
        records = list(session.exec(select(InvoiceRecord)).all())
    assert len(records) == 1
    assert records[0].file_key == saved_key
    assert records[0].amount == "199.00"
    assert records[0].currency == "EUR"

    # Download via presigned URL (what state.download_file would generate).
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": saved_key},
        ExpiresIn=300,
    )
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        downloaded = resp.read()
    assert downloaded == pdf_bytes


@pytest.mark.asyncio
async def test_payments_csv_matches_wise_bulk_upload_schema(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """The payments.csv produced by save_row is Wise's bulk-payment format.

    Columns + their order are Wise's required header. Static fields (recipientDetail,
    sourceCurrency, amountCurrency, receiverType) are set from STATIC_FIELDS;
    dynamic fields (targetCurrency, amount, paymentReference, referenceNumber)
    come from the parsed invoice.
    """
    pdf_bytes = b"%PDF-1.4 wise csv schema test"

    state = AppState()
    state.model = "test-model"
    async for _ in state.handle_upload([_upload_file("wise.pdf", pdf_bytes)]):
        pass
    await _drain_active_job(state)

    state.save_row("wise.pdf")
    assert state.rows[0].status_ok is True

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    csv_obj = s3.get_object(Bucket=bucket, Key=f"{_month_prefix()}/payments.csv")
    raw = csv_obj["Body"].read()
    df = pl.read_csv(io.BytesIO(raw), infer_schema_length=0)

    # 1) Column order matches Wise's required header.
    assert df.columns == CSV_COLUMNS

    row = df.row(0, named=True)

    # 2) Static fields (Wise account routing).
    assert row["recipientDetail"] == STATIC_FIELDS["recipientDetail"] == "Wise account"
    assert row["sourceCurrency"] == STATIC_FIELDS["sourceCurrency"] == "EUR"
    assert row["amountCurrency"] == STATIC_FIELDS["amountCurrency"] == "source"
    assert row["receiverType"] == STATIC_FIELDS["receiverType"] == "PERSON"

    # 3) Dynamic fields come from the parsed invoice.
    assert row["targetCurrency"] == "EUR"
    assert row["amount"] == "199.00"
    assert "Inv INV-100" in row["paymentReference"]
    assert row["referenceNumber"] == "1"


@pytest.mark.asyncio
async def test_payments_csv_increments_reference_across_saves(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """Two successive invoice saves produce referenceNumber 1, 2."""
    state = AppState()
    state.model = "test-model"

    for name in ("first.pdf", "second.pdf"):
        async for _ in state.handle_upload([_upload_file(name, b"%PDF-1.4 " + name.encode())]):
            pass
        await _drain_active_job(state)

    # Two rows parsed; save both.
    state.save_row("first.pdf")
    state.save_row("second.pdf")

    bucket = os.environ["FOLIO_BUCKET_NAME"]
    csv_obj = s3.get_object(Bucket=bucket, Key=f"{_month_prefix()}/payments.csv")
    df = pl.read_csv(io.BytesIO(csv_obj["Body"].read()), infer_schema_length=0)
    assert df["referenceNumber"].to_list() == ["1", "2"]
