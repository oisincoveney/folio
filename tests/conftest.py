"""Test infrastructure: ephemeral Postgres + Minio via testcontainers.

Containers start at conftest module-load time (before pytest collects test modules
or anything imports folio code). This ensures DATABASE_URL and FOLIO_BUCKET_* are
set before rxconfig.py and the storage module evaluate their `os.environ.get(...)`
defaults.

IMPORTANT: keep this file free of helpers that other test modules might want to
import. Pytest's conftest discovery loads it as `conftest`; an explicit
`from tests.conftest import …` loads it again as `tests.conftest`, which would
start a second set of containers and make the test DB and the app DB diverge.
Put shared helpers in `tests/_helpers.py`.
"""

from __future__ import annotations

import atexit
import os
import socket
import stat
import time
from collections.abc import Iterator

import boto3
import pytest
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer

_BUCKET = "test-folio"


def _wait_for_tcp(endpoint: str, timeout: float = 10.0) -> None:
    host, port = endpoint.rsplit(":", 1)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, int(port)), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    msg = f"minio endpoint {endpoint} never came up"
    raise TimeoutError(msg)


# --- start containers at module load -----------------------------------------

_pg = PostgresContainer("postgres:17", driver="psycopg2")
_pg.start()
os.environ["DATABASE_URL"] = _pg.get_connection_url()

_minio = MinioContainer()
_minio.start()
_minio_cfg = _minio.get_config()
os.environ["FOLIO_BUCKET_ENDPOINT"] = f"http://{_minio_cfg['endpoint']}"
os.environ["FOLIO_BUCKET_ACCESS_KEY"] = _minio_cfg["access_key"]
os.environ["FOLIO_BUCKET_SECRET_KEY"] = _minio_cfg["secret_key"]
os.environ["FOLIO_BUCKET_REGION"] = "us-east-1"
os.environ["FOLIO_BUCKET_NAME"] = _BUCKET

_wait_for_tcp(_minio_cfg["endpoint"])


def _minio_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["FOLIO_BUCKET_ENDPOINT"],
        aws_access_key_id=os.environ["FOLIO_BUCKET_ACCESS_KEY"],
        aws_secret_access_key=os.environ["FOLIO_BUCKET_SECRET_KEY"],
        region_name=os.environ["FOLIO_BUCKET_REGION"],
    )


_minio_client().create_bucket(Bucket=_BUCKET)


@atexit.register  # type: ignore[misc]
def _stop_containers() -> None:
    try:
        _minio.stop()
    finally:
        _pg.stop()


# --- schema setup (after DATABASE_URL is in env) ------------------------------

from sqlalchemy import create_engine, text  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from folio.db_models import (  # noqa: E402
    BankTransactionRecord,
    InvoiceRecord,
    PayslipRecord,
    TaxReceiptRecord,
)

_engine = create_engine(os.environ["DATABASE_URL"])
SQLModel.metadata.create_all(
    _engine,
    tables=[
        InvoiceRecord.__table__,
        BankTransactionRecord.__table__,
        TaxReceiptRecord.__table__,
        PayslipRecord.__table__,
    ],
)
_engine.dispose()


# --- per-test fixtures -------------------------------------------------------


@pytest.fixture
def s3():
    """Return a boto3 S3 client pointing at the test minio container."""
    return _minio_client()


@pytest.fixture
def clean_db() -> Iterator[None]:
    """Truncate all record tables before each test that uses the DB."""
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        for tbl in (
            InvoiceRecord.__table__,
            BankTransactionRecord.__table__,
            TaxReceiptRecord.__table__,
            PayslipRecord.__table__,
        ):
            conn.execute(text(f'TRUNCATE TABLE "{tbl.name}" RESTART IDENTITY CASCADE'))
    engine.dispose()
    yield


@pytest.fixture
def clean_bucket(s3) -> Iterator[None]:
    """Empty the test bucket before each test that uses S3."""
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=_BUCKET):
        for obj in page.get("Contents", []):
            # The minio image testcontainers ships with predates AWS's removal of
            # the Content-MD5 requirement on bulk DeleteObjects, so delete one at a
            # time to stay portable.
            s3.delete_object(Bucket=_BUCKET, Key=obj["Key"])
    yield


# --- fake opencode subprocess ------------------------------------------------

_FAKE_OPENCODE = '''\
#!/usr/bin/env python3
"""Fake opencode binary for E2E testing.

Recognises the classify and per-type extract prompts and prints canned JSON
on opencode's stream format. Behaviour is controlled via env vars set by tests:

- FAKE_DOC_TYPE: doc_type to return from the classify pass (default "invoice")
- FAKE_FAILURE_COUNTER: path to a counter file; if set, extract calls increment
  and the call exits 1 while counter < FAKE_FAIL_UNTIL (classify is never failed)
- FAKE_FAIL_UNTIL: number of extract attempts that should fail before success
"""
import json
import os
import sys
from pathlib import Path

argv = sys.argv
if len(argv) < 2 or argv[1] != "run":
    sys.exit(0)

prompt = argv[-1]
doc_type = os.environ.get("FAKE_DOC_TYPE", "invoice")

if "Classify the document type" in prompt:
    print(json.dumps({"type": "text", "part": {"text": json.dumps({"doc_type": doc_type})}}))
    sys.exit(0)

# Extract path: optionally fail to exercise retry.
fail_path = os.environ.get("FAKE_FAILURE_COUNTER")
if fail_path:
    p = Path(fail_path)
    n = int(p.read_text() or "0") if p.exists() else 0
    p.write_text(str(n + 1))
    if n < int(os.environ.get("FAKE_FAIL_UNTIL", "0")):
        sys.stderr.write(f"fake opencode forced failure attempt {n}\\n")
        sys.exit(1)

if "PDF invoice" in prompt:
    payload = {
        "amount": "199.00", "targetCurrency": "EUR",
        "company": "Acme Test Vendor", "invoiceNumber": "INV-100",
        "invoiceDate": "2026-05-20", "description": "Cloud Hosting May 2026",
        "accountNumber": "ACC-42",
    }
elif "PDF bank statement" in prompt:
    payload = {
        "transaction_date": "2026-05-15", "amount": "500.00", "currency": "EUR",
        "counterparty": "Wise", "description": "Transfer to savings",
        "running_balance": "1500.00",
    }
elif "PDF tax receipt" in prompt:
    payload = {
        "tax_type": "income_tax", "period": "2025",
        "amount_paid": "3200.00", "jurisdiction": "EE",
    }
elif "PDF payslip" in prompt:
    payload = {
        "period": "2026-04", "gross_salary": "4500.00",
        "income_tax": "900.00", "social_tax": "450.00", "net_pay": "3150.00",
    }
else:
    payload = {}

print(json.dumps({"type": "text", "part": {"text": json.dumps(payload)}}))
'''


@pytest.fixture
def fake_opencode(tmp_path, monkeypatch):
    """Write a fake opencode binary to disk and patch folio.parse.OPENCODE."""
    script = tmp_path / "fake_opencode"
    script.write_text(_FAKE_OPENCODE)
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setattr("folio.parse.OPENCODE", str(script))
    return script
