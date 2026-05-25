"""Tests for BatchState's streaming-event reducer (`_apply_event`).

Real `BatchState()` instances — Reflex allows this under pytest via the
`is_testing_env()` hook in `reflex/state.py`. No duck-typing.
"""

from folio.models import InvoiceRow
from folio.states.batch import BatchState


def _row(file_key: str = "a.pdf", **overrides: object) -> InvoiceRow:
    return InvoiceRow(file_key=file_key, source_id=f"src-{file_key}", **overrides)


def _state(rows: list[InvoiceRow] | None = None) -> BatchState:
    s = BatchState()
    s.rows = rows or []
    return s


# --- start event ---


def test_start_marks_row_active_and_sets_parsing():
    s = _state([_row("a.pdf")])
    s._apply_event({"type": "start", "file_key": "a.pdf", "source_id": "src-1"})
    assert s.rows[0].status == "active"
    assert s.rows[0].parsing is True


def test_start_auto_selects_when_no_row_selected():
    s = _state([_row("a.pdf"), _row("b.pdf")])
    s._apply_event({"type": "start", "file_key": "a.pdf"})
    assert s.selected_file_key == "a.pdf"


def test_start_does_not_override_existing_selection():
    s = _state([_row("a.pdf"), _row("b.pdf")])
    s.selected_file_key = "b.pdf"
    s._apply_event({"type": "start", "file_key": "a.pdf"})
    assert s.selected_file_key == "b.pdf"


def test_start_with_unknown_file_key_is_a_noop():
    s = _state([_row("a.pdf")])
    s._apply_event({"type": "start", "file_key": "ghost.pdf"})
    assert s.rows[0].status == "pending"


# --- batch_start event ---


def test_batch_start_logs_parallelism_against_first_active_row():
    s = _state([_row("a.pdf", status="pending"), _row("b.pdf", status="active")])
    s._apply_event({"type": "batch_start", "parallelism": 3})
    assert any("Running up to 3" in e.body for e in s.rows[1].logs)


def test_batch_start_falls_back_to_first_row_when_none_active():
    s = _state([_row("a.pdf"), _row("b.pdf")])
    s._apply_event({"type": "batch_start", "parallelism": 2})
    assert any("Running up to 2" in e.body for e in s.rows[0].logs)


def test_batch_start_with_no_rows_is_safe():
    s = _state([])
    s._apply_event({"type": "batch_start", "parallelism": 4})  # must not raise


# --- attempt event ---


def test_attempt_logs_attempt_number_and_marks_active():
    s = _state([_row("a.pdf")])
    s._apply_event(
        {"type": "attempt", "file_key": "a.pdf", "attempt": 2, "max_attempts": 3},
    )
    assert s.rows[0].status == "active"
    assert any("Attempt 2 of 3" in e.body for e in s.rows[0].logs)


# --- raw_log event ---


def test_raw_log_appends_parsed_log_entry():
    s = _state([_row("a.pdf")])
    s._apply_event({
        "type": "raw_log",
        "file_key": "a.pdf",
        "stream": "stdout",
        "text": "hello",
    })
    assert len(s.rows[0].logs) == 1
    assert s.rows[0].logs[0].body == "hello"


# --- retrying event ---


def test_retrying_logs_previous_attempt_and_error():
    s = _state([_row("a.pdf")])
    s._apply_event(
        {"type": "retrying", "file_key": "a.pdf", "attempt": 3, "error": "timeout"},
    )
    msg = s.rows[0].logs[0].body
    assert "Retrying after attempt 2" in msg  # attempt - 1
    assert "timeout" in msg


# --- result event ---


def test_result_marks_done_and_populates_fields():
    s = _state([_row("a.pdf")])
    s._apply_event({
        "type": "result",
        "file_key": "a.pdf",
        "amount": "100.00",
        "targetCurrency": "USD",
        "company": "Acme",
        "invoiceNumber": "INV-1",
        "invoiceDate": "2026-05-01",
        "description": "thing",
        "accountNumber": "A1",
        "paymentReference": "Acme - Inv INV-1",
        "file_id": "fid-1",
        "doc_type": "invoice",
        "raw_data": {"company": "Acme"},
    })
    row = s.rows[0]
    assert row.status == "done"
    assert row.parsing is False
    assert row.amount == "100.00"
    assert row.target_currency == "USD"
    assert row.invoice_number == "INV-1"
    assert row.payment_reference == "Acme - Inv INV-1"
    assert row.file_id == "fid-1"
    assert row.doc_type == "invoice"
    assert row.raw_data == {"company": "Acme"}
    assert s.completed == 1


def test_result_with_error_marks_error_status():
    s = _state([_row("a.pdf")])
    s._apply_event({"type": "result", "file_key": "a.pdf", "error": "parse failed"})
    assert s.rows[0].status == "error"
    assert s.rows[0].error == "parse failed"
    assert s.completed == 1  # error results still increment completed


def test_result_defaults_doc_type_to_invoice():
    s = _state([_row("a.pdf")])
    s._apply_event({"type": "result", "file_key": "a.pdf", "amount": "1.00"})
    assert s.rows[0].doc_type == "invoice"


# --- error event (no file_key, falls back to active row) ---


def test_error_event_attaches_to_active_row():
    s = _state([_row("a.pdf", status="active"), _row("b.pdf")])
    s._apply_event({"type": "error", "error": "stream broke"})
    assert s.rows[0].status == "error"
    assert s.rows[0].error == "stream broke"
    assert s.rows[0].parsing is False
    assert any("stream broke" in e.body for e in s.rows[0].logs)


def test_error_event_falls_back_to_selected_when_no_active():
    s = _state([_row("a.pdf"), _row("b.pdf")])
    s.selected_file_key = "b.pdf"
    s._apply_event({"type": "error", "error": "oops"})
    assert s.rows[1].status == "error"
    assert s.rows[0].status == "pending"  # untouched


def test_error_event_with_no_target_is_safe():
    s = _state([])
    s._apply_event({"type": "error", "error": "no rows yet"})  # must not raise


# --- unknown event type ---


def test_unknown_event_type_is_silently_ignored():
    s = _state([_row("a.pdf")])
    s._apply_event({"type": "mystery", "file_key": "a.pdf"})
    assert s.rows[0].status == "pending"  # untouched
    assert s.completed == 0
