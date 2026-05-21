"""CSV record keeping and invoice file naming."""

import datetime
from pathlib import Path

import polars as pl
from slugify import slugify

from folio.config import CSV_COLUMNS, STATIC_FIELDS


def get_next_ref(csv_path: str | Path) -> int:
    """Return the next sequential reference number for the payments CSV."""
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
    return int(refs["referenceNumber"].max()) + 1


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
    """Append one payment row to the CSV, creating it with headers if needed."""
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


def build_filename(payment_reference: str, amount: str, currency: str) -> str:
    """Build a dated PDF filename from payment reference, amount and currency."""
    today = datetime.date.today().isoformat()
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
    today = datetime.date.today().isoformat()
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
