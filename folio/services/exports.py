"""Export helpers — month-zip builder."""

from __future__ import annotations

import io
import zipfile
from typing import Any


def build_month_zip(client: Any, bucket: str, files: list[dict]) -> bytes:  # noqa: ANN401
    """Build a zip archive containing the given S3 files.

    Synchronous, in-RAM. Folio months are typically <50 MB; if a month ever
    exceeds ~200 MB, switch to ``stream-zip`` + multipart ``put_object``.

    Each ``files`` entry must have a ``key`` (S3 object key) and a ``name``
    (the filename to use inside the archive).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            body = client.get_object(Bucket=bucket, Key=f["key"])["Body"].read()
            zf.writestr(f["name"], body)
    return buf.getvalue()
