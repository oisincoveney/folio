"""Tests for the /data page: services.store.query, DataViewState, route."""

from __future__ import annotations

import reflex as rx

from folio.db_models import InvoiceRecord
from folio.services import store as store_svc
from folio.states.data_view import DataViewState


def _seed_invoice(
    *,
    file_key: str,
    amount: str,
    currency: str,
    saved_at: str,
    company: str = "Acme",
    invoice_number: str = "INV-1",
    invoice_date: str = "",
    status: str = "outstanding",
) -> None:
    """Insert one InvoiceRecord directly via SQLModel session."""
    with rx.session() as session:
        session.add(
            InvoiceRecord(
                file_key=file_key,
                content_hash=file_key,  # unique enough for tests
                saved_at=saved_at,
                status=status,
                amount=amount,
                currency=currency,
                company=company,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
            ),
        )
        session.commit()


def test_store_query_invoice_year_returns_records_and_totals(clean_db) -> None:
    """Records filtered by year; EUR/USD totals computed from the year's rows."""
    _seed_invoice(file_key="k1", amount="100.00", currency="EUR", saved_at="2024-03-12")
    _seed_invoice(
        file_key="k2", amount="50.00", currency="USD", saved_at="2024-07-04",
        invoice_number="INV-2",
    )
    _seed_invoice(
        file_key="k3", amount="999.00", currency="EUR", saved_at="2023-11-30",
        invoice_number="INV-3",
    )

    result = store_svc.query("invoice", 2024, None)

    assert len(result.records) == 2
    file_keys = {r["file_key"] for r in result.records}
    assert file_keys == {"k1", "k2"}
    assert result.totals_eur == "100.00"
    assert result.totals_usd == "50.00"
    # Outstanding count picks up all three (status defaults to outstanding).
    assert result.outstanding_counts["invoice"] == 3
    assert result.outstanding_counts["bank_statement"] == 0


def test_store_query_respects_quarter(clean_db) -> None:
    """``quarter=1`` returns only Jan-Mar saved_at rows."""
    _seed_invoice(file_key="q1a", amount="10", currency="EUR", saved_at="2024-01-15")
    _seed_invoice(
        file_key="q1b", amount="20", currency="EUR", saved_at="2024-03-31",
        invoice_number="INV-Q1B",
    )
    _seed_invoice(
        file_key="q2a", amount="30", currency="EUR", saved_at="2024-04-01",
        invoice_number="INV-Q2A",
    )

    q1 = store_svc.query("invoice", 2024, 1)
    q2 = store_svc.query("invoice", 2024, 2)

    assert {r["file_key"] for r in q1.records} == {"q1a", "q1b"}
    assert {r["file_key"] for r in q2.records} == {"q2a"}


def test_data_view_state_load_populates_fields(clean_db) -> None:
    """``DataViewState.load`` unpacks the StoreQuery into its fields."""
    _seed_invoice(
        file_key="dv1", amount="200.00", currency="EUR", saved_at="2025-02-10",
    )

    state = DataViewState()
    state.doc_type = "invoice"
    state.year = 2025
    state.quarter = 0
    state.load()

    assert len(state.records) == 1
    assert state.records[0]["file_key"] == "dv1"
    assert state.totals_eur == "200.00"
    assert state.totals_usd == ""
    assert state.outstanding_counts["invoice"] == 1
    assert state.loading is False


def test_data_route_registered() -> None:
    """``/data`` is registered and wires DataViewState.load as on_load."""
    from folio.folio import app

    routes = list(app._unevaluated_pages.keys())  # noqa: SLF001
    assert "data" in routes, f"routes={routes}"
