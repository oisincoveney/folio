"""Test infrastructure: ephemeral Postgres + Minio via testcontainers.

Containers start at conftest module-load time (before pytest collects test modules
or anything imports folio code). This ensures DATABASE_URL and FOLIO_BUCKET_* are
set before rxconfig.py and the storage module evaluate their `os.environ.get(...)`
defaults. Cleanup is registered via atexit + a session-scope autouse fixture as a
belt-and-braces stop.
"""

from __future__ import annotations

import atexit
import os
import socket
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
    with engine.connect() as conn:
        for tbl in (
            InvoiceRecord.__table__,
            BankTransactionRecord.__table__,
            TaxReceiptRecord.__table__,
            PayslipRecord.__table__,
        ):
            conn.execute(text(f'TRUNCATE TABLE "{tbl.name}" RESTART IDENTITY CASCADE'))
        conn.commit()
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
