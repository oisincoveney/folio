"""AWS / S3 client factory + bucket name accessor."""

import os
from typing import Any

import boto3


def s3() -> Any:  # noqa: ANN401
    """Return a boto3 S3 client configured from FOLIO_BUCKET_* env vars."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("FOLIO_BUCKET_ENDPOINT"),
        aws_access_key_id=os.environ.get("FOLIO_BUCKET_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("FOLIO_BUCKET_SECRET_KEY"),
        region_name=os.environ.get("FOLIO_BUCKET_REGION", "auto"),
    )


def bucket_name() -> str:
    """Return the configured S3 bucket name."""
    return os.environ.get("FOLIO_BUCKET_NAME", "")
