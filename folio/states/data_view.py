"""State for the /data page: doc-type / year / quarter filters + result rows."""

from __future__ import annotations

import asyncio
import datetime

import reflex as rx

from folio.services import store as store_svc


def _current_year() -> int:
    return datetime.datetime.now(tz=datetime.UTC).year


class DataViewState(rx.State):
    """UI state for the /data page."""

    doc_type: str = "invoice"
    year: int = _current_year()
    quarter: int = 0  # 0 = all quarters
    records: list[dict] = []
    totals_eur: str = ""
    totals_usd: str = ""
    outstanding_counts: dict[str, int] = {}
    loading: bool = False

    async def load(self) -> None:
        """Run the composite store query and unpack the result into fields.

        Runs the blocking database query on a thread pool so the Reflex event
        loop is not stalled (fixes the ``EventFuture`` worker crash).
        """
        self.loading = True
        doc_type = self.doc_type
        year = self.year
        quarter = self.quarter or None
        try:
            result = await asyncio.to_thread(
                store_svc.query, doc_type, year, quarter,
            )
            self.records = result.records
            self.totals_eur = result.totals_eur
            self.totals_usd = result.totals_usd
            self.outstanding_counts = result.outstanding_counts
        finally:
            self.loading = False

    async def set_doc_type(self, value: str | list[str]) -> None:
        """Switch the active doc-type tab and reload.

        ``rx.segmented_control`` emits ``str`` for single-select and
        ``list[str]`` for multi-select. We only configure single-select, but
        the type signature has to accept both for Reflex's event-handler
        validation to be happy.
        """
        if isinstance(value, list):
            value = value[0] if value else "invoice"
        self.doc_type = value
        await self.load()

    async def set_year(self, value: str | list[str]) -> None:
        """Switch the active year (``rx.select`` emits strings) and reload."""
        if isinstance(value, list):
            value = value[0] if value else str(_current_year())
        self.year = int(value)
        await self.load()

    async def set_quarter(self, value: str | list[str]) -> None:
        """Switch the active quarter (0 = all) and reload."""
        if isinstance(value, list):
            value = value[0] if value else "All"
        mapped = {"All": 0, "Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
        self.quarter = mapped.get(value, 0)
        await self.load()
