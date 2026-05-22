"""CSV record keeping and invoice file naming."""

import datetime
import io
from pathlib import Path
from typing import Any

import polars as pl
from botocore.exceptions import ClientError
from slugify import slugify

from folio.config import CSV_COLUMNS, STATIC_FIELDS

DOC_TYPE_PREFIX: dict[str, str] = {
    "invoice": "invoices",
    "bank_statement": "bank-statements",
    "tax_receipt": "tax-receipts",
    "payslip": "payslips",
}


def object_key(doc_type: str, filename: str, date: datetime.date | None = None) -> str:
    """Return the S3 object key for a document, e.g. '2026-05/invoices/file.pdf'."""
    d = date or datetime.datetime.now(tz=datetime.UTC).date()
    prefix = DOC_TYPE_PREFIX.get(doc_type, "exports")
    return f"{d.strftime('%Y-%m')}/{prefix}/{filename}"


def payments_csv_key(date: datetime.date | None = None) -> str:
    """Return the S3 object key for the month's payments CSV."""
    d = date or datetime.datetime.now(tz=datetime.UTC).date()
    return f"{d.strftime('%Y-%m')}/payments.csv"


def get_next_ref(csv_path: str | Path) -> int:
    """Return the next sequential reference number for a local payments CSV."""
    p = Path(csv_path)
    if not p.exists():
        return 1
    df = pl.read_csv(p, infer_schema_length=0)
    if df.is_empty():
        return 1
    refs = (
        df.select(pl.col("referenceNumber").cast(pl.Int64, strict=False))
        .drop_nulls()
    )
    if refs.is_empty():
        return 1
    max_ref = refs["referenceNumber"].max()
    if max_ref is None:
        return 1
    return int(max_ref) + 1  # type: ignore[arg-type]


def get_next_ref_s3(s3_client: Any, bucket: str, key: str) -> int:  # noqa: ANN401
    """Return the next sequential reference number from a payments CSV in S3."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        df = pl.read_csv(
            io.BytesIO(response["Body"].read()), infer_schema_length=0,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return 1
        raise
    if df.is_empty():
        return 1
    refs = (
        df.select(pl.col("referenceNumber").cast(pl.Int64, strict=False))
        .drop_nulls()
    )
    if refs.is_empty():
        return 1
    max_ref = refs["referenceNumber"].max()
    if max_ref is None:
        return 1
    return int(max_ref) + 1  # type: ignore[arg-type]


def ensure_csv(csv_path: Path) -> None:
    """Create the payments CSV with the correct header if it does not exist."""
    if not csv_path.exists():
        pl.DataFrame(schema=dict.fromkeys(CSV_COLUMNS, pl.String)).write_csv(csv_path)


def append_csv_row(
    csv_path: str | Path,
    target_currency: str,
    amount: str,
    payment_reference: str,
    ref_num: int,
) -> None:
    """Append one payment row to a local CSV, creating it with headers if needed."""
    p = Path(csv_path)
    ensure_csv(p)
    row = {
        **STATIC_FIELDS,
        "targetCurrency": target_currency,
        "amount": amount,
        "paymentReference": payment_reference,
        "referenceNumber": str(ref_num),
    }
    existing = pl.read_csv(p, infer_schema_length=0)
    new_row = pl.DataFrame([row]).select(CSV_COLUMNS)
    pl.concat([existing, new_row]).write_csv(p)


def append_csv_row_s3(  # noqa: PLR0913
    s3_client: Any,  # noqa: ANN401
    bucket: str,
    key: str,
    target_currency: str,
    amount: str,
    payment_reference: str,
    ref_num: int,
) -> None:
    """Append one payment row to a payments CSV in S3, creating it if needed."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        existing = pl.read_csv(
            io.BytesIO(response["Body"].read()), infer_schema_length=0,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            existing = pl.DataFrame(schema=dict.fromkeys(CSV_COLUMNS, pl.String))
        else:
            raise
    row = {
        **STATIC_FIELDS,
        "targetCurrency": target_currency,
        "amount": amount,
        "paymentReference": payment_reference,
        "referenceNumber": str(ref_num),
    }
    new_row = pl.DataFrame([row]).select(CSV_COLUMNS)
    buf = io.BytesIO()
    pl.concat([existing, new_row]).write_csv(buf)
    s3_client.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())


def build_filename(payment_reference: str, amount: str, currency: str) -> str:
    """Build a dated PDF filename from payment reference, amount and currency."""
    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
    ref = _filename_part(payment_reference)
    amount_part = _filename_part(amount)
    currency_part = _filename_part(currency)
    return f"{today}_{ref}_{amount_part}_{currency_part}.pdf"


def _filename_part(value: str, max_len: int = 0) -> str:
    return slugify(
        value or "",
        lowercase=True,
        separator="-",
        max_length=max_len,
        word_boundary=bool(max_len),
        save_order=True,
    )


def build_invoice_filename(row: dict) -> str:
    """Build a dated PDF filename from invoice row fields."""
    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
    company = _filename_part(row.get("company", ""), 28)
    invoice = _filename_part(row.get("invoiceNumber", ""), 32)
    amount = _filename_part(row.get("amount", ""))
    currency = _filename_part(row.get("targetCurrency", ""), 3)

    parts = [today, company]
    if invoice:
        parts.append(invoice)
    elif row.get("description"):
        parts.append(_filename_part(row.get("description", ""), 24))
    if amount and currency:
        parts.append(f"{amount}-{currency}")
    else:
        parts.extend([amount, currency])

    return f"{'_'.join(part for part in parts if part)}.pdf"
