"""/data page: totals strip + filter controls + per-doc-type record table."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import reflex as rx

from folio.components.header import header
from folio.states.data_view import DataViewState
from folio.states.file_browser import FileBrowserState

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# Totals strip
# ---------------------------------------------------------------------------


def _tile(label: str, value: rx.Var | str) -> rx.Component:
    return rx.card(
        rx.flex(
            rx.text(label, size="1", color="var(--gray-9)"),
            rx.text(value, size="5", weight="bold"),
            direction="column",
            spacing="1",
        ),
        flex_grow="1",
    )


def _totals_strip() -> rx.Component:
    outstanding_label = "Outstanding"
    return rx.flex(
        _tile("EUR invoiced", DataViewState.totals_eur),
        _tile("USD invoiced", DataViewState.totals_usd),
        _tile(
            outstanding_label,
            DataViewState.outstanding_counts[DataViewState.doc_type].to_string(),
        ),
        _tile("Records shown", DataViewState.records.length().to_string()),
        spacing="3",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Filter controls
# ---------------------------------------------------------------------------


def _year_options() -> list[str]:
    current = datetime.datetime.now(tz=datetime.UTC).year
    return [str(y) for y in range(current, 2021, -1)]


def _filters() -> rx.Component:
    return rx.flex(
        rx.segmented_control.root(
            rx.segmented_control.item("Invoices", value="invoice"),
            rx.segmented_control.item("Bank", value="bank_statement"),
            rx.segmented_control.item("Tax", value="tax_receipt"),
            rx.segmented_control.item("Payslips", value="payslip"),
            value=DataViewState.doc_type,
            on_change=DataViewState.set_doc_type,
        ),
        rx.flex(
            rx.select.root(
                rx.select.trigger(),
                rx.select.content(
                    rx.foreach(
                        _year_options(),
                        lambda y: rx.select.item(y, value=y),
                    ),
                ),
                value=DataViewState.year.to_string(),
                on_change=DataViewState.set_year,
            ),
            rx.select.root(
                rx.select.trigger(),
                rx.select.content(
                    rx.select.item("All", value="All"),
                    rx.select.item("Q1", value="Q1"),
                    rx.select.item("Q2", value="Q2"),
                    rx.select.item("Q3", value="Q3"),
                    rx.select.item("Q4", value="Q4"),
                ),
                value=rx.cond(
                    DataViewState.quarter == 0,
                    "All",
                    "Q" + DataViewState.quarter.to_string(),
                ),
                on_change=DataViewState.set_quarter,
            ),
            spacing="2",
            align="center",
        ),
        align="center",
        justify="between",
        width="100%",
    )


# ---------------------------------------------------------------------------
# Per-doc-type tables
# ---------------------------------------------------------------------------


def _download_cell(record: rx.Var) -> rx.Component:
    return rx.table.cell(
        rx.icon_button(
            rx.icon("download", size=13),
            variant="ghost",
            size="1",
            on_click=FileBrowserState.download_file(record["file_key"]),
        ),
        align="right",
    )


def _text(value: rx.Var) -> rx.Component:
    return rx.table.cell(rx.text(value, size="2"))


def _invoice_row(record: rx.Var) -> rx.Component:
    return rx.table.row(
        _text(record["company"]),
        _text(record["invoice_number"]),
        _text(record["amount"]),
        _text(record["currency"]),
        _text(record["invoice_date"]),
        _download_cell(record),
    )


def _bank_row(record: rx.Var) -> rx.Component:
    return rx.table.row(
        _text(record["transaction_date"]),
        _text(record["counterparty"]),
        _text(record["amount"]),
        _text(record["currency"]),
        _download_cell(record),
    )


def _tax_row(record: rx.Var) -> rx.Component:
    return rx.table.row(
        _text(record["tax_type"]),
        _text(record["period"]),
        _text(record["jurisdiction"]),
        _text(record["amount_paid"]),
        _download_cell(record),
    )


def _payslip_row(record: rx.Var) -> rx.Component:
    return rx.table.row(
        _text(record["period"]),
        _text(record["gross_salary"]),
        _text(record["income_tax"]),
        _text(record["net_pay"]),
        _download_cell(record),
    )


def _table_with_headers(
    headers: list[str],
    render_row: Callable[[rx.Var], rx.Component],
) -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                *[rx.table.column_header_cell(h) for h in headers[:-1]],
                rx.table.column_header_cell(headers[-1], align="right"),
            ),
        ),
        rx.table.body(rx.foreach(DataViewState.records, render_row)),
        width="100%",
        variant="surface",
    )


def _records_table() -> rx.Component:
    return rx.match(
        DataViewState.doc_type,
        (
            "invoice",
            _table_with_headers(
                ["Company", "Invoice #", "Amount", "Currency", "Date", ""],
                _invoice_row,
            ),
        ),
        (
            "bank_statement",
            _table_with_headers(
                ["Date", "Counterparty", "Amount", "Currency", ""],
                _bank_row,
            ),
        ),
        (
            "tax_receipt",
            _table_with_headers(
                ["Tax type", "Period", "Jurisdiction", "Amount paid", ""],
                _tax_row,
            ),
        ),
        (
            "payslip",
            _table_with_headers(
                ["Period", "Gross", "Income tax", "Net pay", ""],
                _payslip_row,
            ),
        ),
        rx.fragment(),
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def data_page() -> rx.Component:
    """Render the /data page."""
    return rx.flex(
        header(),
        rx.box(
            rx.flex(
                _totals_strip(),
                _filters(),
                rx.cond(
                    DataViewState.loading,
                    rx.flex(
                        rx.spinner(size="3"),
                        align="center",
                        justify="center",
                        padding="32px",
                    ),
                    _records_table(),
                ),
                direction="column",
                spacing="3",
                width="100%",
                padding="16px",
            ),
            flex_grow="1",
            overflow_y="auto",
            min_height="0",
        ),
        direction="column",
        height="100vh",
        width="100%",
        overflow="hidden",
    )
