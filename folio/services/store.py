"""Composite read queries for the /data page.

This is a skeleton — branch 5 will implement the real ``query`` function backed
by ``folio.db_models``. For now it returns an empty StoreQuery so the module
can be imported without side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StoreQuery:
    """Result of a composite read for the /data page."""

    records: list[dict] = field(default_factory=list)
    totals_eur: str = ""
    totals_usd: str = ""
    outstanding_counts: dict[str, int] = field(default_factory=dict)


def query(doc_type: str, year: int, quarter: int | None = None) -> StoreQuery:  # noqa: ARG001
    """Return records, totals and outstanding counts for the given filters.

    Skeleton: returns an empty StoreQuery. Branch 5 fills this in.
    """
    return StoreQuery()
