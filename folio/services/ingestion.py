"""Document ingestion service: S3 upload + DB upsert.

Extracted from ``folio.state.AppState.save_row``. The state class is responsible
for:

* claiming the pending file path via :func:`folio.services.parser.claim_pending`,
* reading bytes off disk,
* popping ``staged_files``,
* applying ``_patch_row`` to mutate ``rx.State`` after success/failure.

This module owns everything in between: building the S3 key, the put, appending
to the monthly payments.csv for invoices, hashing the content, and upserting
the matching ``*Record`` row in Postgres. Failures are surfaced as
:class:`IngestionError` with a structured ``stage`` attribute so the caller can
render the right message.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass

from botocore.exceptions import ClientError

from folio import aws
from folio import storage as storage_mod
from folio.db_models import (
    BankTransactionRecord,
    InvoiceRecord,
    PayslipRecord,
    TaxReceiptRecord,
)
from folio.models import InvoiceRow

_RECORD_CLS = {
    "invoice": InvoiceRecord,
    "bank_statement": BankTransactionRecord,
    "tax_receipt": TaxReceiptRecord,
    "payslip": PayslipRecord,
}


@dataclass(frozen=True)
class SavedRecord:
    """The result of a successful save: returned by :func:`save_record`."""

    key: str
    content_hash: str
    doc_type: str
    db_persisted: bool


class IngestionError(Exception):
    """Raised when S3 or DB persistence fails during :func:`save_record`."""

    def __init__(self, stage: str, message: str) -> None:
        """Initialize with a stage tag ("s3" or "db") and an underlying message."""
        super().__init__(message)
        self.stage = stage  # "s3" or "db"


def _row_to_record_dict(row: InvoiceRow, key: str, content_hash: str) -> dict[str, str]:
    """Build a record dict from an InvoiceRow for DB upsert."""
    base: dict[str, str] = {
        "file_key": key,
        "content_hash": content_hash,
        "saved_at": datetime.datetime.now(tz=datetime.UTC).date().isoformat(),
        "doc_type": row.doc_type,
        "status": "outstanding",
    }
    if row.doc_type == "invoice":
        base.update({
            "amount": row.amount,
            "currency": row.target_currency,
            "company": row.company,
            "invoice_number": row.invoice_number,
            "invoice_date": row.invoice_date,
            "description": row.description,
            "account_number": row.account_number,
            "payment_reference": row.payment_reference,
        })
    else:
        raw = row.raw_data
        for field in (
            "transaction_date", "amount", "currency", "counterparty", "description",
            "running_balance", "tax_type", "period", "amount_paid", "jurisdiction",
            "gross_salary", "income_tax", "social_tax", "net_pay",
        ):
            val = raw.get(field)
            if isinstance(val, str):
                base[field] = val
    return base


def save_record(row: InvoiceRow, file_bytes: bytes) -> SavedRecord:
    """Persist ``file_bytes`` to S3 and upsert a matching record row.

    Does NOT consume the parse-side pending claim and does NOT mutate any
    ``rx.State`` instance. The state class is responsible for those.

    Raises:
        IngestionError: with ``stage="s3"`` on any S3 ``ClientError``;
            with ``stage="db"`` on any DB upsert failure.
    """
    bucket = aws.bucket_name()
    client = aws.s3()
    filename = storage_mod.build_invoice_filename(
        {
            "company": row.company,
            "invoiceNumber": row.invoice_number,
            "amount": row.amount,
            "targetCurrency": row.target_currency,
            "description": row.description,
        },
    )
    key = storage_mod.object_key(row.doc_type, filename)
    try:
        client.put_object(Body=file_bytes, Bucket=bucket, Key=key)
        if row.doc_type == "invoice":
            csv_key = storage_mod.payments_csv_key()
            ref_num = storage_mod.get_next_ref_s3(client, bucket, csv_key)
            storage_mod.append_csv_row_s3(
                client, bucket, csv_key,
                row.target_currency, row.amount, row.payment_reference, ref_num,
            )
    except ClientError as e:
        raise IngestionError(stage="s3", message=str(e)) from e

    content_hash = hashlib.sha256(file_bytes).hexdigest()
    record_cls = _RECORD_CLS.get(row.doc_type, InvoiceRecord)
    try:
        record_cls.upsert(_row_to_record_dict(row, key, content_hash))
    except Exception as db_err:
        raise IngestionError(stage="db", message=str(db_err)) from db_err

    return SavedRecord(
        key=key,
        content_hash=content_hash,
        doc_type=row.doc_type,
        db_persisted=True,
    )
