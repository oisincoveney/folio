"""Shared test helpers. Kept separate from conftest.py so importing them doesn't
trigger conftest's container startup twice (once via pytest's conftest discovery,
once via `from tests.conftest import …`).
"""

from __future__ import annotations

import datetime
import io
import queue
from pathlib import Path

import reflex as rx


def month_prefix() -> str:
    """Return the current UTC month as 'YYYY-MM' for asserting S3 key prefixes."""
    return datetime.datetime.now(tz=datetime.UTC).date().strftime("%Y-%m")


def make_upload_file(name: str, data: bytes) -> rx.UploadFile:
    """Build a real rx.UploadFile suitable for state.handle_upload."""
    return rx.UploadFile(file=io.BytesIO(data), path=Path(name))


async def drain_active_job(state) -> None:  # noqa: ANN001
    """Pull events from the parse queue and apply them to state.

    Substitutes for stream_parse's @rx.event(background=True) loop so tests don't
    have to spin Reflex's background-event machinery.
    """
    from folio.state import _active_jobs  # noqa: PLC0415

    job_id, q = next(iter(_active_jobs.items()))
    while True:
        try:
            event = q.get(block=True, timeout=10)
        except queue.Empty:
            break
        state._apply_event(event)  # noqa: SLF001
        if event.get("type") == "done":
            break
    _active_jobs.pop(job_id, None)
