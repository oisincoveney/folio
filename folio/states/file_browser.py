"""State for the /files page: month sidebar + per-month file table."""

from __future__ import annotations

import reflex as rx

from folio import aws


class FileBrowserState(rx.State):
    """UI state for the file browser page."""

    browser_months: list[str] = []
    browser_files: dict[str, list[dict]] = {}
    browser_loading: bool = False
    browser_month: str = ""

    def load_file_browser(self) -> None:
        """Populate browser_months and browser_files from S3 bucket listing."""
        bucket = aws.bucket_name()
        if not bucket:
            return
        self.browser_loading = True
        client = aws.s3()
        months: dict[str, list[dict]] = {}
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                parts = key.split("/")
                if len(parts) < 2:  # noqa: PLR2004
                    continue
                month = parts[0]
                months.setdefault(month, []).append({
                    "key": key,
                    "size": str(obj.get("Size", 0)),
                    "modified": obj["LastModified"].strftime("%Y-%m-%d %H:%M"),
                    "name": parts[-1],
                })
        self.browser_months = sorted(months.keys(), reverse=True)
        self.browser_files = months
        if self.browser_months and not self.browser_month:
            self.browser_month = self.browser_months[0]
        self.browser_loading = False

    def select_browser_month(self, month: str) -> None:
        """Set the active month in the file browser."""
        self.browser_month = month

    def download_file(self, key: str) -> rx.event.EventSpec:
        """Generate a presigned URL for the given S3 key and redirect to it."""
        url: str = aws.s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": aws.bucket_name(), "Key": key},
            ExpiresIn=300,
        )
        return rx.redirect(url)  # pyright: ignore[reportReturnType]
