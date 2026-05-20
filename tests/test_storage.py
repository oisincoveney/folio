import datetime
import tempfile
from pathlib import Path

import polars as pl

import storage
from config import CSV_COLUMNS


class FixedDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 5, 21)


def freeze_today(monkeypatch):
    monkeypatch.setattr(storage.datetime, "date", FixedDate)


def test_invoice_filename_uses_compact_lowercase_kebab_tokens(monkeypatch):
    freeze_today(monkeypatch)

    filename = storage.build_invoice_filename({
        "company": "US Mobile",
        "invoiceNumber": "435367220",
        "description": "1 GB Top Up",
        "amount": "2.00",
        "targetCurrency": "USD",
    })

    assert filename == "2026-05-21_us-mobile_435367220_2-00-usd.pdf"


def test_invoice_filename_preserves_invoice_token_mechanically(monkeypatch):
    freeze_today(monkeypatch)

    filename = storage.build_invoice_filename({
        "company": "US Mobile",
        "invoiceNumber": "INV-435367220",
        "description": "1 GB Top Up",
        "amount": "2.00",
        "targetCurrency": "USD",
    })

    assert filename == "2026-05-21_us-mobile_inv-435367220_2-00-usd.pdf"


def test_invoice_filename_uses_short_description_only_without_invoice(monkeypatch):
    freeze_today(monkeypatch)

    filename = storage.build_invoice_filename({
        "company": "US Mobile",
        "description": "1 GB Top Up",
        "amount": "2.00",
        "targetCurrency": "USD",
    })

    assert filename == "2026-05-21_us-mobile_1-gb-top-up_2-00-usd.pdf"


def test_invoice_filename_caps_long_parts_and_preserves_amount_currency(monkeypatch):
    freeze_today(monkeypatch)

    filename = storage.build_invoice_filename({
        "company": "Very Long Company Name That Keeps Going Incorporated Limited",
        "invoiceNumber": "INV-1234567890-ABCDEFGHIJK-LONG-SUFFIX",
        "description": (
            "This is a ridiculously long product description with many details "
            "and billing periods"
        ),
        "amount": "1234.56",
        "targetCurrency": "USD",
    })

    assert filename == (
        "2026-05-21_very-long-company-name-that_"
        "inv-1234567890-abcdefghijk-long_1234-56-usd.pdf"
    )
    assert filename.endswith("_1234-56-usd.pdf")


def test_append_csv_row_column_order_matches_csv_header():
    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / "payments.csv"
        storage.append_csv_row(csv_path, "USD", "2.00", "INV-123", 1)
        storage.append_csv_row(csv_path, "EUR", "45.00", "INV-456", 2)
        df = pl.read_csv(csv_path, infer_schema_length=0)
        assert df.columns == CSV_COLUMNS
