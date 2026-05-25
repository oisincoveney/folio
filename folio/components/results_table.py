"""Two-column results view: scrollable table on the left, log panel on the right."""

import reflex as rx

from folio import styles
from folio.components.log_panel import log_panel
from folio.models import InvoiceRow
from folio.states.batch import BatchState
from folio.states.file_browser import FileBrowserState

# ---------------------------------------------------------------------------
# Status icon
# ---------------------------------------------------------------------------


def _status_icon(row: InvoiceRow) -> rx.Component:
    """Render a status icon for a row."""
    return rx.match(
        row.status,
        ("active", rx.spinner(size="1")),
        ("done", rx.icon("circle_check", size=15, color="var(--green-9)")),
        ("error", rx.icon("triangle_alert", size=15, color="var(--amber-9)")),
        rx.icon("circle", size=15, color="var(--gray-7)"),
    )


# ---------------------------------------------------------------------------
# File cell (filename + subtitle + error)
# ---------------------------------------------------------------------------


def _file_cell(row: InvoiceRow) -> rx.Component:
    """Render the file name, subtitle, and optional error text for a table row."""
    return rx.flex(
        rx.text(row.filename_original, size="2", weight="medium"),
        rx.flex(
            rx.cond(
                row.company != "",
                rx.text(row.company, **styles.TABLE_SUBTITLE),
            ),
            rx.cond(
                (row.company != "") & (row.invoice_number != ""),
                rx.text("·", size="1", color="var(--gray-6)"),
            ),
            rx.cond(
                row.invoice_number != "",
                rx.text("Inv ", row.invoice_number, **styles.TABLE_SUBTITLE),
            ),
            rx.cond(
                (row.description != "")
                & ((row.company != "") | (row.invoice_number != "")),
                rx.text("·", size="1", color="var(--gray-6)"),
            ),
            rx.cond(
                row.description != "",
                rx.text(row.description, **styles.TABLE_SUBTITLE),
            ),
            gap="1",
            align="center",
            flex_wrap="nowrap",
            overflow="hidden",
        ),
        rx.cond(
            row.error != "",
            rx.text(row.error, **styles.TABLE_ERROR_TEXT),
        ),
        direction="column",
        gap="0",
        min_width="0",
        overflow="hidden",
    )


# ---------------------------------------------------------------------------
# Save/retry/queued cell
# ---------------------------------------------------------------------------


def _save_cell(row: InvoiceRow) -> rx.Component:
    """Render saved indicator, Retry button, or Queued badge per row status."""
    return rx.cond(
        row.status_ok,
        rx.flex(
            rx.icon("check", size=14, color="var(--green-9)"),
            rx.cond(
                row.db_persisted,
                rx.badge("DB", size="1", color_scheme="green", variant="soft"),
            ),
            rx.icon_button(
                rx.icon("download", size=12),
                size="1",
                variant="ghost",
                on_click=FileBrowserState.download_file(row.saved_as),
                title=row.saved_as,
            ),
            gap="1",
            align="center",
        ),
        rx.cond(
            row.status == "error",
            rx.button(
                "Retry",
                size="1",
                color_scheme="amber",
                variant="soft",
                on_click=BatchState.retry_row(row.file_key),
            ),
            rx.cond(
                (row.status == "pending") & BatchState.parsing,
                rx.badge("Queued", color_scheme="blue", size="1", variant="soft"),
                rx.text(""),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Table row
# ---------------------------------------------------------------------------


def _table_row(row: InvoiceRow) -> rx.Component:
    """Render one row in the results table."""
    return rx.table.row(
        rx.table.cell(_status_icon(row), padding="var(--space-2)"),
        rx.table.cell(_file_cell(row)),
        rx.table.cell(
            rx.text(row.amount, **styles.TABLE_CELL_MONO),
            padding="var(--space-2)",
        ),
        rx.table.cell(
            rx.text(row.target_currency, **styles.TABLE_CELL_MONO),
            padding="var(--space-2)",
        ),
        rx.table.cell(_save_cell(row), padding="var(--space-2)"),
        on_click=BatchState.select_row(row.file_key),
        cursor="pointer",
        background=rx.cond(
            row.file_key == BatchState.selected_file_key,
            "var(--accent-3)",
            "transparent",
        ),
        _hover={"background": "var(--gray-3)"},
        align="center",
    )


# ---------------------------------------------------------------------------
# Table header (left panel top)
# ---------------------------------------------------------------------------


def _table_header() -> rx.Component:
    """Render the batch header with status counts and action buttons."""
    counts = BatchState.status_counts
    return rx.flex(
        rx.flex(
            rx.text("Batch", size="3", weight="bold"),
            rx.cond(
                counts["active"] > 0,
                rx.badge(counts["active"], color_scheme="blue", variant="soft"),
            ),
            rx.cond(
                counts["done"] > 0,
                rx.badge(counts["done"], color_scheme="green", variant="soft"),
            ),
            rx.cond(
                counts["error"] > 0,
                rx.badge(counts["error"], color_scheme="amber", variant="soft"),
            ),
            gap="2",
            align="center",
        ),
        rx.flex(
            rx.text(
                rx.icon("database", size=12),
                rx.cond(
                    BatchState.bucket_name != "",
                    BatchState.bucket_name,
                    "No bucket configured",
                ),
                size="1",
                color="var(--gray-9)",
                display="flex",
                align="center",
                gap="1",
            ),
            rx.cond(
                counts["done"] > 0,
                rx.button(
                    "Save completed",
                    size="1",
                    variant="soft",
                    color_scheme="green",
                    on_click=BatchState.save_all_done,
                    disabled=BatchState.parsing,
                ),
            ),
            rx.cond(
                counts["error"] > 0,
                rx.button(
                    "Retry failed",
                    size="1",
                    variant="soft",
                    color_scheme="amber",
                    on_click=BatchState.retry_failed,
                    disabled=BatchState.parsing,
                ),
            ),
            rx.button(
                "Clear",
                size="1",
                variant="soft",
                color_scheme="gray",
                on_click=BatchState.clear_session,
                disabled=BatchState.parsing,
            ),
            gap="2",
            align="center",
        ),
        justify="between",
        align="center",
        **styles.PANEL_HEADER,
    )


# ---------------------------------------------------------------------------
# Public component
# ---------------------------------------------------------------------------


def results_table() -> rx.Component:
    """Render the two-column results view."""
    return rx.flex(
        rx.flex(
            _table_header(),
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("", padding="var(--space-2)"),
                            rx.table.column_header_cell(
                                rx.text("File", **styles.TABLE_HEADER_CELL),
                            ),
                            rx.table.column_header_cell(
                                rx.text("Amount", **styles.TABLE_HEADER_CELL),
                            ),
                            rx.table.column_header_cell(
                                rx.text("Cur", **styles.TABLE_HEADER_CELL),
                            ),
                            rx.table.column_header_cell(""),
                        ),
                    ),
                    rx.table.body(rx.foreach(BatchState.rows, _table_row)),
                    width="100%",
                ),
                overflow_y="auto",
                flex_grow="1",
                min_height="0",
            ),
            direction="column",
            flex="1",
            min_width="0",
            **styles.CARD,
        ),
        rx.box(
            log_panel(),
            flex="1",
            min_width="0",
            display="flex",
            flex_direction="column",
            overflow="hidden",
        ),
        gap="var(--space-4)",
        padding="var(--space-4)",
        flex_grow="1",
        overflow="hidden",
        align="stretch",
    )
