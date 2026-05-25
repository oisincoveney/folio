"""Tests for ``services.exports`` and ``FileBrowserState.download_month_zip``."""

from __future__ import annotations

import io
import os
import zipfile

import pytest
import reflex as rx

from folio.services import exports
from folio.states.file_browser import FileBrowserState


@pytest.fixture
def _bucket() -> str:
    return os.environ["FOLIO_BUCKET_NAME"]


def test_build_month_zip_returns_bytes_with_all_files(s3, clean_bucket, _bucket):
    """build_month_zip pulls each S3 key and writes it under ``files[i]['name']``."""
    a_bytes = b"%PDF-1.4 contents-a"
    b_bytes = b"%PDF-1.4 contents-b"
    s3.put_object(Bucket=_bucket, Key="2024-03/a.pdf", Body=a_bytes)
    s3.put_object(Bucket=_bucket, Key="2024-03/b.pdf", Body=b_bytes)

    result = exports.build_month_zip(
        s3,
        _bucket,
        [
            {"key": "2024-03/a.pdf", "name": "a.pdf"},
            {"key": "2024-03/b.pdf", "name": "b.pdf"},
        ],
    )

    assert isinstance(result, bytes)
    with zipfile.ZipFile(io.BytesIO(result)) as zf:
        assert zf.namelist() == ["a.pdf", "b.pdf"]
        assert zf.read("a.pdf") == a_bytes
        assert zf.read("b.pdf") == b_bytes


def test_download_month_zip_returns_download_spec(s3, clean_bucket, _bucket):
    """FileBrowserState.download_month_zip returns an rx.download EventSpec."""
    s3.put_object(Bucket=_bucket, Key="2024-03/a.pdf", Body=b"%PDF-1.4 a")
    s3.put_object(Bucket=_bucket, Key="2024-03/b.pdf", Body=b"%PDF-1.4 b")

    state = FileBrowserState()
    state.load_file_browser()
    assert "2024-03" in state.browser_files

    spec = state.download_month_zip("2024-03")
    assert isinstance(spec, rx.event.EventSpec)
    # rx.download builds a data:URL with the bytes embedded; the filename
    # appears as the second positional arg.
    arg_values = [str(arg[1]) for arg in spec.args]
    assert any("folio-2024-03.zip" in v for v in arg_values)
    # The URL arg should be a data: URL since we passed raw bytes.
    assert any("data:application/octet-stream;base64," in v for v in arg_values)


def test_download_month_zip_no_files_returns_none():
    """When the month has no files, download_month_zip returns None."""
    state = FileBrowserState()
    assert state.download_month_zip("2024-03") is None
