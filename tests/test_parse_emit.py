"""Tests for parse._emit_result: the parse → UI event contract.

The state event reducer reads camelCase keys for invoice fields, so the dumped
model must use by_alias=True. Bank statement / tax receipt / payslip models use
snake_case fields throughout and serialise as-is.
"""

import queue

from folio import parse
from folio.doc_models import (
    BankTransactionData,
    InvoiceData,
    PayslipData,
    TaxReceiptData,
)


def _task(**overrides: object) -> parse._ParseTask:  # noqa: SLF001
    defaults: dict[str, object] = {
        "orig_name": "in.pdf",
        "pdf_path": "/tmp/in.pdf",  # noqa: S108
        "file_key": "in.pdf",
        "source_id": "src-1",
        "model": "anthropic/claude-opus-4-7",
        "index": 0,
        "total": 1,
        "is_temp": True,
    }
    defaults.update(overrides)
    return parse._ParseTask(**defaults)  # type: ignore[arg-type]  # noqa: SLF001


def _drain(q: queue.Queue) -> dict:
    return q.get_nowait()


# --- failure path ---


def test_emit_result_none_emits_error_event_with_default_doc_type_and_empty_fields():
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(), None, "boom", q)  # noqa: SLF001

    ev = _drain(q)
    assert ev["type"] == "result"
    assert ev["doc_type"] == "invoice"
    assert ev["raw_data"] == {}
    assert ev["amount"] == ""
    assert ev["targetCurrency"] == "EUR"
    assert ev["file_id"] is None
    assert ev["error"] == "boom"


def test_emit_result_none_with_empty_error_falls_back_to_default_message():
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(), None, "", q)  # noqa: SLF001
    assert _drain(q)["error"] == "No parseable JSON found in opencode output"


# --- invoice success path ---


def test_emit_result_invoice_uses_camelcase_keys_at_event_boundary():
    """state.py's _on_result reads ev['targetCurrency'], ev['invoiceNumber'], etc."""
    data = InvoiceData(
        amount="42.00",
        target_currency="USD",
        company="Acme",
        invoice_number="INV-9",
        invoice_date="2026-05-01",
        description="thing",
        account_number="A1",
        payment_reference="Acme - Inv INV-9",
    )
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(), data, "", q)  # noqa: SLF001

    ev = _drain(q)
    assert ev["targetCurrency"] == "USD"
    assert ev["invoiceNumber"] == "INV-9"
    assert ev["invoiceDate"] == "2026-05-01"
    assert ev["accountNumber"] == "A1"
    assert ev["paymentReference"] == "Acme - Inv INV-9"
    # snake_case keys must NOT leak — they'd silently shadow the camelCase ones.
    assert "target_currency" not in ev
    assert "invoice_number" not in ev


def test_emit_result_success_registers_file_id_in_pending():
    data = InvoiceData(amount="1.00", target_currency="USD")
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(pdf_path="/tmp/foo.pdf", is_temp=True), data, "", q)  # noqa: S108, SLF001

    ev = _drain(q)
    assert ev["file_id"] is not None
    # claim_pending should resolve the file_id to the path we registered.
    claimed = parse.claim_pending(ev["file_id"])
    assert claimed == ("/tmp/foo.pdf", True)


def test_emit_result_non_temp_path_registers_in_source_pending():
    data = InvoiceData(amount="1.00", target_currency="USD")
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(pdf_path="/orig/foo.pdf", is_temp=False), data, "", q)  # noqa: SLF001

    ev = _drain(q)
    claimed = parse.claim_pending(ev["file_id"])
    assert claimed == ("/orig/foo.pdf", False)


def test_emit_result_raw_data_mirrors_event_fields():
    data = InvoiceData(amount="5.00", target_currency="EUR", company="X")
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(), data, "", q)  # noqa: SLF001

    ev = _drain(q)
    assert ev["raw_data"]["company"] == "X"
    assert ev["raw_data"]["targetCurrency"] == "EUR"


# --- non-invoice doc types ---


def test_emit_result_bank_statement_serialises_snake_case_fields():
    data = BankTransactionData(
        transaction_date="2026-05-01",
        amount="100.00",
        currency="EUR",
        counterparty="Wise",
        description="Transfer",
        running_balance="500.00",
    )
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(), data, "", q)  # noqa: SLF001

    ev = _drain(q)
    assert ev["doc_type"] == "bank_statement"
    assert ev["raw_data"]["transaction_date"] == "2026-05-01"
    assert ev["raw_data"]["counterparty"] == "Wise"
    assert ev["raw_data"]["running_balance"] == "500.00"


def test_emit_result_tax_receipt_includes_jurisdiction():
    data = TaxReceiptData(
        tax_type="income_tax",
        period="2025",
        amount_paid="3200.00",
        jurisdiction="EE",
    )
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(), data, "", q)  # noqa: SLF001

    ev = _drain(q)
    assert ev["doc_type"] == "tax_receipt"
    assert ev["raw_data"]["jurisdiction"] == "EE"
    assert ev["raw_data"]["amount_paid"] == "3200.00"


def test_emit_result_payslip_includes_all_pay_fields():
    data = PayslipData(
        period="2026-04",
        gross_salary="4500.00",
        income_tax="900.00",
        social_tax="450.00",
        net_pay="3150.00",
    )
    q: queue.Queue = queue.Queue()
    parse._emit_result(_task(), data, "", q)  # noqa: SLF001

    ev = _drain(q)
    assert ev["doc_type"] == "payslip"
    assert ev["raw_data"]["gross_salary"] == "4500.00"
    assert ev["raw_data"]["net_pay"] == "3150.00"


# --- task identity propagation ---


def test_emit_result_preserves_task_metadata_on_event():
    data = InvoiceData(amount="1.00", target_currency="USD")
    q: queue.Queue = queue.Queue()
    task = _task(orig_name="orig.pdf", file_key="orig.pdf", source_id="abc", index=2, total=5)
    parse._emit_result(task, data, "", q)  # noqa: SLF001

    ev = _drain(q)
    assert ev["filename_original"] == "orig.pdf"
    assert ev["file_key"] == "orig.pdf"
    assert ev["source_id"] == "abc"
    assert ev["index"] == 2  # noqa: PLR2004
    assert ev["total"] == 5  # noqa: PLR2004
