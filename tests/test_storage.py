import io
import tempfile
from pathlib import Path

import boto3
import polars as pl
import pytest
import time_machine
from moto import mock_aws

from folio import storage
from folio.config import CSV_COLUMNS, STATIC_FIELDS

_BUCKET = "test-folio"

frozen_today = time_machine.travel("2026-05-21 12:00:00+00:00", tick=False)


@pytest.fixture
def s3():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=_BUCKET)
        yield client


def _csv_bytes(*rows: dict) -> bytes:
    df = pl.DataFrame(list(rows)).select(CSV_COLUMNS)
    buf = io.BytesIO()
    df.write_csv(buf)
    return buf.getvalue()


@frozen_today
def test_invoice_filename_uses_compact_lowercase_kebab_tokens():
    filename = storage.build_invoice_filename({
        "company": "US Mobile",
        "invoiceNumber": "435367220",
        "description": "1 GB Top Up",
        "amount": "2.00",
        "targetCurrency": "USD",
    })

    assert filename == "2026-05-21_us-mobile_435367220_2-00-usd.pdf"


@frozen_today
def test_invoice_filename_preserves_invoice_token_mechanically():
    filename = storage.build_invoice_filename({
        "company": "US Mobile",
        "invoiceNumber": "INV-435367220",
        "description": "1 GB Top Up",
        "amount": "2.00",
        "targetCurrency": "USD",
    })

    assert filename == "2026-05-21_us-mobile_inv-435367220_2-00-usd.pdf"


@frozen_today
def test_invoice_filename_uses_short_description_only_without_invoice():
    filename = storage.build_invoice_filename({
        "company": "US Mobile",
        "description": "1 GB Top Up",
        "amount": "2.00",
        "targetCurrency": "USD",
    })

    assert filename == "2026-05-21_us-mobile_1-gb-top-up_2-00-usd.pdf"


@frozen_today
def test_invoice_filename_caps_long_parts_and_preserves_amount_currency():
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


# --- S3 key helpers ---

@frozen_today
def test_object_key_structure():
    assert storage.object_key("invoice", "file.pdf") == "2026-05/invoices/file.pdf"


@frozen_today
def test_object_key_unknown_type_falls_back_to_exports():
    assert storage.object_key("mystery", "file.pdf") == "2026-05/exports/file.pdf"


@frozen_today
def test_payments_csv_key():
    assert storage.payments_csv_key() == "2026-05/payments.csv"


# --- S3 CSV helpers ---

def test_get_next_ref_s3_missing_returns_one(s3):
    ref = storage.get_next_ref_s3(s3, _BUCKET, "2026-05/payments.csv")
    assert ref == 1


def test_get_next_ref_s3_existing_returns_max_plus_one(s3):
    row = {**STATIC_FIELDS, "targetCurrency": "EUR", "amount": "10.00",
           "paymentReference": "ref1", "referenceNumber": "2"}
    s3.put_object(Bucket=_BUCKET, Key="2026-05/payments.csv", Body=_csv_bytes(row))
    assert storage.get_next_ref_s3(s3, _BUCKET, "2026-05/payments.csv") == 3


def test_append_csv_row_s3_roundtrip(s3):
    key = "2026-05/payments.csv"
    storage.append_csv_row_s3(s3, _BUCKET, key, "USD", "2.00", "INV-123", 1)
    storage.append_csv_row_s3(s3, _BUCKET, key, "EUR", "45.00", "INV-456", 2)
    body = s3.get_object(Bucket=_BUCKET, Key=key)["Body"].read()
    df = pl.read_csv(io.BytesIO(body), infer_schema_length=0)
    assert len(df) == 2
    assert df.columns == CSV_COLUMNS
