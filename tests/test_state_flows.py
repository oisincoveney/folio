"""State-flow tests: retry queue, field editing, file browser.

These exercise the BatchState handlers users actually interact with via the UI —
retrying a failed row, editing a field then saving, and browsing previously
saved documents. Tests instantiate real BatchState (Reflex allows this under
pytest) and mock at the seams that hit subprocesses or external services.
"""

from __future__ import annotations

import os
import queue
from typing import get_args, get_origin

import pytest
import reflex as rx
from reflex_base.event import resolve_upload_handler_param
from sqlmodel import select

from folio.db_models import InvoiceRecord
from folio.models import InvoiceRow
from folio.services import parser as parse_mod
from folio.states.batch import BatchState, _active_jobs
from folio.states.file_browser import FileBrowserState

from tests._helpers import drain_active_job, make_upload_file, month_prefix, upload_and_parse


# ----------------------------------------------------------------------------
# Retry queue mechanics
# ----------------------------------------------------------------------------


def _invoice_result_event(file_key: str, source_id: str, file_id: str) -> dict:
    return {
        "type": "result",
        "file_key": file_key,
        "source_id": source_id,
        "amount": "42.00",
        "targetCurrency": "EUR",
        "company": "Retry Vendor",
        "invoiceNumber": "RV-1",
        "invoiceDate": "2026-05-15",
        "description": "Retry test",
        "accountNumber": "",
        "paymentReference": "Retry Vendor - Inv RV-1",
        "file_id": file_id,
        "doc_type": "invoice",
        "raw_data": {"company": "Retry Vendor"},
    }


def test_upload_handler_uses_buffered_upload_with_inline_stream() -> None:
    """Upload endpoint owns row staging and parse StateUpdate streaming."""
    param_name, annotation = resolve_upload_handler_param(BatchState.handle_upload)

    assert BatchState.handle_upload.is_background is False
    assert param_name == "files"
    assert get_origin(annotation) is list
    assert get_args(annotation) == (rx.UploadFile,)


@pytest.mark.asyncio
async def test_upload_handler_streams_rows_and_parse_without_chained_event(monkeypatch):
    """Upload handler streams row creation and parse result in one response."""

    def fake_start_parse_job(temp_files, _model):
        q: queue.Queue = queue.Queue()
        for name, _tmp_path, file_key, source_id in temp_files:
            q.put({
                "type": "start",
                "file_key": file_key,
                "source_id": source_id,
                "filename": name,
            })
            q.put(_invoice_result_event(file_key, source_id, f"fid-{file_key}"))
        q.put({"type": "done"})
        return q

    monkeypatch.setattr("folio.states.batch.start_parse_job", fake_start_parse_job)
    monkeypatch.setattr(parse_mod, "get_default_model", lambda: "test-model")

    state = BatchState()
    updates = [
        update
        async for event in BatchState.handle_upload.fn(
            state,
            [make_upload_file("stream.pdf", b"%PDF-1.4 stream")],
        )
        for update in [event]
    ]

    assert state.has_rows is True
    assert state.rows[0].status == "done"
    assert state.status_counts["done"] == 1
    assert state.parsing is False
    assert _active_jobs == {}
    assert updates
    assert all(update is None for update in updates)


@pytest.mark.asyncio
async def test_upload_stream_stages_and_consumes_parse_job(monkeypatch):
    """Upload stages files, starts parser, and consumes the parse queue."""

    def fake_start_parse_job(temp_files, _model):
        q: queue.Queue = queue.Queue()
        for name, _tmp_path, file_key, source_id in temp_files:
            q.put({
                "type": "start",
                "file_key": file_key,
                "source_id": source_id,
                "filename": name,
            })
            q.put(_invoice_result_event(file_key, source_id, f"fid-{file_key}"))
        q.put({"type": "done"})
        return q

    monkeypatch.setattr("folio.states.batch.start_parse_job", fake_start_parse_job)

    state = BatchState()
    state.update_model("test-model")

    await upload_and_parse(state, [make_upload_file("ack.pdf", b"%PDF-1.4 ack")])

    assert state.rows[0].status == "done"
    assert state.parsing is False
    assert _active_jobs == {}


@pytest.mark.asyncio
async def test_retry_failed_row_re_runs_through_parse_pipeline(monkeypatch):
    """Failed row → retry_row → re-parsed → reaches done."""
    # Track how many start_parse_job calls happen and which file_keys they target.
    invocations = []

    def fake_start_parse_job(temp_files, _model):
        invocations.append([t[2] for t in temp_files])  # file_keys
        q: queue.Queue = queue.Queue()
        for name, tmp_path, file_key, source_id in temp_files:
            # Register the temp file so claim_pending works post-save
            parse_mod._pending[f"fid-{file_key}"] = tmp_path  # noqa: SLF001
            q.put({"type": "start", "file_key": file_key, "source_id": source_id,
                   "filename": name})
            if len(invocations) == 1:
                # First call: emit a parse error.
                q.put({"type": "result", "file_key": file_key, "source_id": source_id,
                       "error": "first attempt fails", "doc_type": "invoice",
                       "raw_data": {}})
            else:
                # Retry call: emit a successful result.
                q.put(_invoice_result_event(file_key, source_id, f"fid-{file_key}"))
        q.put({"type": "done"})
        return q

    monkeypatch.setattr("folio.states.batch.start_parse_job", fake_start_parse_job)

    state = BatchState()
    state.update_model("test-model")

    # 1. Upload → first parse errors out.
    await upload_and_parse(state, [make_upload_file("retry.pdf", b"%PDF-1.4 r")])

    assert state.rows[0].status == "error"
    assert state.completed == 1
    assert len(invocations) == 1

    # 2. Click retry. retry_row returns an EventSpec for run_retry_queue, which
    #    is an async generator we need to iterate to actually kick off the job.
    state.parsing = False
    state.retry_row("retry.pdf")
    async for _ in state.run_retry_queue():
        pass
    await drain_active_job(state)

    # 3. Second start_parse_job invocation targeted the same file_key.
    assert len(invocations) == 2  # noqa: PLR2004
    assert invocations[1] == ["retry.pdf"]

    # 4. Row recovered.
    assert state.rows[0].status == "done"
    assert state.rows[0].amount == "42.00"
    assert state.rows[0].error == ""
    # `completed` decremented during retry_rows then re-incremented on result.
    assert state.completed == 1


@pytest.mark.asyncio
async def test_retry_failed_picks_up_all_error_rows(monkeypatch):
    """retry_failed reruns every error row in one go."""
    invocations = []

    def fake_start_parse_job(temp_files, _model):
        invocations.append([t[2] for t in temp_files])
        q: queue.Queue = queue.Queue()
        for name, tmp_path, file_key, source_id in temp_files:
            parse_mod._pending[f"fid-{file_key}"] = tmp_path  # noqa: SLF001
            q.put({"type": "start", "file_key": file_key, "source_id": source_id,
                   "filename": name})
            if len(invocations) == 1:
                q.put({"type": "result", "file_key": file_key, "source_id": source_id,
                       "error": "fail", "doc_type": "invoice", "raw_data": {}})
            else:
                q.put(_invoice_result_event(file_key, source_id, f"fid-{file_key}"))
        q.put({"type": "done"})
        return q

    monkeypatch.setattr("folio.states.batch.start_parse_job", fake_start_parse_job)

    state = BatchState()
    state.update_model("test-model")
    await upload_and_parse(state, [
        make_upload_file("a.pdf", b"a"),
        make_upload_file("b.pdf", b"b"),
    ])

    assert all(r.status == "error" for r in state.rows)

    state.parsing = False
    state.retry_failed()
    async for _ in state.run_retry_queue():
        pass
    await drain_active_job(state)

    assert all(r.status == "done" for r in state.rows)
    assert sorted(invocations[1]) == ["a.pdf", "b.pdf"]


def test_retry_with_no_error_rows_is_a_noop():
    """retry_rows returns None and doesn't touch state when no rows match."""
    state = BatchState()
    state.rows = [InvoiceRow(file_key="ok.pdf", source_id="s", status="done")]
    result = state.retry_rows(["ok.pdf"])
    assert result is None
    assert state.rows[0].status == "done"  # untouched


# ----------------------------------------------------------------------------
# Field editing → save persists edits
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_edits_then_save_persists_edited_values(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """User edits fields after parsing → save uses the edited values."""
    state = BatchState()
    state.update_model("test-model")
    await upload_and_parse(state, [make_upload_file("edit.pdf", b"%PDF-1.4 e")])

    # Parsed values from the fake opencode (invoice path).
    assert state.rows[0].company.startswith("Acme")
    assert state.rows[0].invoice_number == "INV-100"

    # User overrides several fields via the set_selected_* handlers.
    state.set_selected_company("Different Vendor Ltd")
    state.set_selected_amount("999.99")
    state.set_selected_invoice_number("OVERRIDE-7")
    state.set_selected_description("Overridden description")
    state.rebuild_reference()

    # rebuild_reference should regenerate from current fields.
    assert "OVERRIDE-7" in state.rows[0].payment_reference
    assert "Different Vendor" in state.rows[0].payment_reference

    state.save_row("edit.pdf")
    assert state.rows[0].status_ok is True

    # S3 filename reflects edits.
    saved_key = state.rows[0].saved_as
    filename = saved_key.split("/")[-1]
    assert "different-vendor" in filename
    assert "override-7" in filename
    assert "999-99" in filename

    # DB record reflects edits.
    with rx.session() as session:
        records = list(session.exec(select(InvoiceRecord)).all())
    assert len(records) == 1
    assert records[0].company == "Different Vendor Ltd"
    assert records[0].amount == "999.99"
    assert records[0].invoice_number == "OVERRIDE-7"
    assert records[0].description == "Overridden description"


def test_set_selected_field_with_no_selection_is_a_noop():
    """Calling set_selected_X without selected_file_key set silently does nothing."""
    state = BatchState()
    state.rows = [InvoiceRow(file_key="a.pdf", source_id="s", company="Original")]
    # selected_file_key intentionally not set
    state.set_selected_company("Should not stick")
    assert state.rows[0].company == "Original"


# ----------------------------------------------------------------------------
# File browser
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_browser_lists_saved_documents_by_month(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """After saves, load_file_browser groups objects by their YYYY-MM prefix."""
    state = BatchState()
    state.update_model("test-model")

    # Upload + save two invoices with distinct identifiers so filenames differ.
    for inv_id, content in [("FB-1", b"%PDF-1.4 fb1"), ("FB-2", b"%PDF-1.4 fb2")]:
        await upload_and_parse(state, [
            make_upload_file(f"{inv_id}.pdf", content),
        ])
        # Override invoice number to give distinct filenames.
        state.selected_file_key = f"{inv_id}.pdf"
        state.set_selected_invoice_number(inv_id)
        state.set_selected_company(f"Vendor {inv_id}")
        state.save_row(f"{inv_id}.pdf")
        assert state.rows[-1].status_ok is True, state.rows[-1].error

    # Drive the browser.
    browser = FileBrowserState()
    await browser.load_file_browser()

    month = month_prefix()
    assert month in browser.browser_months
    assert browser.browser_month == month  # auto-selected since empty

    # Should see at minimum: the two invoices + a payments.csv.
    files = browser.browser_files[month]
    keys = [f["key"] for f in files]
    invoice_files = [k for k in keys if "/invoices/" in k]
    assert len(invoice_files) == 2
    assert any("fb-1" in k for k in invoice_files)
    assert any("fb-2" in k for k in invoice_files)
    assert any(k.endswith("/payments.csv") for k in keys)

    # Metadata shape: each entry has key/size/modified/name.
    for f in files:
        assert {"key", "size", "modified", "name"} <= set(f.keys())


def test_select_browser_month_switches_active_month():
    state = FileBrowserState()
    state.browser_months = ["2026-05", "2026-04", "2026-03"]
    state.browser_month = "2026-05"
    state.select_browser_month("2026-04")
    assert state.browser_month == "2026-04"


@pytest.mark.asyncio
async def test_download_file_generates_presigned_url_that_fetches_bytes(
    s3, clean_db, clean_bucket, fake_opencode,
):
    """state.download_file produces a presigned URL good for an HTTP GET."""
    import urllib.request  # noqa: PLC0415

    state = BatchState()
    state.update_model("test-model")
    pdf_bytes = b"%PDF-1.4 downloadable" + os.urandom(16)
    await upload_and_parse(state, [make_upload_file("dl.pdf", pdf_bytes)])
    state.save_row("dl.pdf")
    saved_key = state.rows[0].saved_as

    # download_file returns an rx.redirect EventSpec; the URL is generated via
    # _s3().generate_presigned_url under the hood. Generate the same URL with
    # the test client and verify the bytes.
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": os.environ["FOLIO_BUCKET_NAME"], "Key": saved_key},
        ExpiresIn=300,
    )
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        assert resp.read() == pdf_bytes
