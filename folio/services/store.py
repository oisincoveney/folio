"""Composite read queries for the /data page.

Wraps the per-record-class methods on ``folio.db_models`` (``by_year``,
``outstanding``, ``eur_usd_totals``) and serializes each record into a
homogeneous string-keyed dict that the data view component can render
directly. One call to :func:`query` returns everything ``DataViewState.load``
needs: the filtered records, the EUR/USD totals for the year, and the
outstanding count per doc type.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from folio.db_models import (
    BankTransactionRecord,
    InvoiceRecord,
    PayslipRecord,
    TaxReceiptRecord,
    _RecordBase,
)

# Re-imported from ingestion in spirit; kept local to avoid a circular import
# (ingestion imports services.aws + models — store doesn't need any of that).
_RECORD_CLS: dict[str, type[_RecordBase]] = {
    "invoice": InvoiceRecord,
    "bank_statement": BankTransactionRecord,
    "tax_receipt": TaxReceiptRecord,
    "payslip": PayslipRecord,
}


@dataclass(frozen=True)
class StoreQuery:
    """Result of a composite read for the /data page."""

    records: list[dict] = field(default_factory=list)
    totals_eur: str = ""
    totals_usd: str = ""
    outstanding_counts: dict[str, int] = field(default_factory=dict)


def _serialize_invoice(r: InvoiceRecord) -> dict[str, str]:
    return {
        "file_key": r.file_key,
        "company": r.company,
        "invoice_number": r.invoice_number,
        "amount": r.amount,
        "currency": r.currency,
        "invoice_date": r.invoice_date,
    }


def _serialize_bank(r: BankTransactionRecord) -> dict[str, str]:
    return {
        "file_key": r.file_key,
        "transaction_date": r.transaction_date,
        "counterparty": r.counterparty,
        "amount": r.amount,
        "currency": r.currency,
    }


def _serialize_tax(r: TaxReceiptRecord) -> dict[str, str]:
    return {
        "file_key": r.file_key,
        "tax_type": r.tax_type,
        "period": r.period,
        "jurisdiction": r.jurisdiction,
        "amount_paid": r.amount_paid,
    }


def _serialize_payslip(r: PayslipRecord) -> dict[str, str]:
    return {
        "file_key": r.file_key,
        "period": r.period,
        "gross_salary": r.gross_salary,
        "income_tax": r.income_tax,
        "net_pay": r.net_pay,
    }


_SERIALIZERS = {
    "invoice": _serialize_invoice,
    "bank_statement": _serialize_bank,
    "tax_receipt": _serialize_tax,
    "payslip": _serialize_payslip,
}


def query(doc_type: str, year: int, quarter: int | None = None) -> StoreQuery:
    """Return records, totals and outstanding counts for the given filters.

    ``doc_type`` selects which record class to list. ``year`` and ``quarter``
    are forwarded to ``by_year``. EUR/USD totals are always for invoices in
    ``year``. ``outstanding_counts`` is keyed by doc_type and reflects every
    record class regardless of the selected tab.
    """
    record_cls = _RECORD_CLS.get(doc_type)
    if record_cls is None:
        return StoreQuery()

    rows = record_cls.by_year(year, quarter)
    serialize = _SERIALIZERS[doc_type]
    records = [serialize(r) for r in rows]  # type: ignore[arg-type]

    totals = InvoiceRecord.eur_usd_totals(year)

    outstanding_counts: dict[str, int] = {}
    for dt, cls in _RECORD_CLS.items():
        outstanding_counts[dt] = len(cls.outstanding())

    return StoreQuery(
        records=records,
        totals_eur=totals.get("EUR", ""),
        totals_usd=totals.get("USD", ""),
        outstanding_counts=outstanding_counts,
    )
