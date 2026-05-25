"""Right panel: dark log stream + field editor for the selected file.

Log filtering (``visible_logs`` / ``hidden_technical_count`` /
``toggle_technical``) lives on ``BatchState``. Reflex's substate hierarchy
makes cross-state ``@rx.var`` iteration unworkable, and the filter is just a
presentational view over the same row logs ``BatchState`` already owns — so
it belongs on the same state slot, not a sibling state.
"""

import reflex as rx

from folio import styles
from folio.models import LogEntry
from folio.states.batch import BatchState

# ---------------------------------------------------------------------------
# Log entry rendering
# ---------------------------------------------------------------------------


def _log_item(entry: LogEntry) -> rx.Component:
    """Render one log entry in the dark panel."""
    return rx.box(
        rx.flex(
            rx.badge(
                entry.stream,
                color_scheme=rx.cond(entry.stream == "stderr", "amber", "gray"),
                variant="soft",
                size="1",
            ),
            rx.text(entry.title, size="1", weight="medium", color="var(--gray-3)"),
            rx.cond(
                entry.meta != "",
                rx.text(entry.meta, size="1", color="var(--gray-7)"),
            ),
            align="center",
            spacing="2",
            **styles.LOG_ENTRY_HEADER,
        ),
        rx.cond(
            entry.body != "",
            rx.cond(
                (entry.type == "tool_use") | (entry.type == "raw"),
                rx.text(entry.body, **styles.LOG_BODY_MONO),
                rx.text(entry.body, **styles.LOG_BODY),
            ),
        ),
        **styles.LOG_ENTRY,
    )


# ---------------------------------------------------------------------------
# Log panel header
# ---------------------------------------------------------------------------


def _panel_header() -> rx.Component:
    """Render the dark header bar of the log panel."""
    return rx.flex(
        rx.flex(
            rx.text(
                BatchState.selected_row.filename_original,
                size="2",
                weight="medium",
                color="var(--gray-1)",
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            rx.text(
                BatchState.visible_logs.length(),
                " events",
                size="1",
                color="var(--gray-7)",
            ),
            rx.cond(
                (BatchState.hidden_technical_count > 0)
                & ~BatchState.show_technical,
                rx.text(
                    " · ",
                    BatchState.hidden_technical_count,
                    " hidden",
                    size="1",
                    color="var(--gray-8)",
                ),
            ),
            spacing="2",
            align="center",
            min_width="0",
            flex_grow="1",
        ),
        rx.flex(
            rx.cond(
                BatchState.selected_row.status == "error",
                rx.button(
                    rx.icon("rotate_cw", size=12),
                    "Retry",
                    size="1",
                    color_scheme="amber",
                    variant="soft",
                    on_click=BatchState.retry_row(BatchState.selected_file_key),
                ),
            ),
            rx.icon_button(
                rx.icon("wand_2", size=13),
                variant="ghost",
                color_scheme="gray",
                size="1",
                on_click=BatchState.rebuild_reference,
                disabled=BatchState.selected_row.parsing,
                title="Rebuild reference",
                color="var(--gray-7)",
            ),
            rx.icon_button(
                rx.icon("eye", size=13),
                variant="ghost",
                color_scheme="gray",
                size="1",
                on_click=BatchState.toggle_technical,
                title="Toggle technical entries",
                color="var(--gray-7)",
            ),
            rx.match(
                BatchState.selected_row.status,
                ("active", rx.spinner(size="1")),
                ("done", rx.icon("circle_check", size=14, color="var(--green-9)")),
                ("error", rx.icon("triangle_alert", size=14, color="var(--amber-9)")),
                rx.icon("circle", size=14, color="var(--gray-7)"),
            ),
            spacing="2",
            align="center",
            flex_shrink="0",
        ),
        align="center",
        spacing="3",
        **styles.LOG_PANEL_HEADER,
    )


# ---------------------------------------------------------------------------
# Field editor
# ---------------------------------------------------------------------------


def _label(text: str) -> rx.Component:
    return rx.text(text, as_="label", **styles.FIELD_LABEL)


def _field(label: str, input_component: rx.Component) -> rx.Component:
    return rx.flex(
        _label(label),
        input_component,
        direction="column",
        spacing="2",
    )


def _field_editor() -> rx.Component:
    """Render the editable invoice field form below the log panel."""
    dis = BatchState.selected_row.parsing
    mono = "'IBM Plex Mono', monospace"
    return rx.flex(
        rx.grid(
            _field(
                "Amount",
                rx.input(
                    value=BatchState.selected_row.amount,
                    on_change=BatchState.set_selected_amount,
                    disabled=dis,
                    font_family=mono,
                ),
            ),
            _field(
                "Currency",
                rx.input(
                    value=BatchState.selected_row.target_currency,
                    on_change=BatchState.set_selected_target_currency,
                    disabled=dis,
                    font_family=mono,
                    max_length=3,
                ),
            ),
            _field(
                "Reference",
                rx.input(
                    value=BatchState.selected_row.payment_reference,
                    on_change=BatchState.set_selected_payment_reference,
                    disabled=dis,
                ),
            ),
            _field(
                "Company",
                rx.input(
                    value=BatchState.selected_row.company,
                    on_change=BatchState.set_selected_company,
                    disabled=dis,
                ),
            ),
            _field(
                "Invoice #",
                rx.input(
                    value=BatchState.selected_row.invoice_number,
                    on_change=BatchState.set_selected_invoice_number,
                    disabled=dis,
                ),
            ),
            rx.box(),
            _field(
                "Date",
                rx.input(
                    value=BatchState.selected_row.invoice_date,
                    on_change=BatchState.set_selected_invoice_date,
                    disabled=dis,
                ),
            ),
            _field(
                "Account",
                rx.input(
                    value=BatchState.selected_row.account_number,
                    on_change=BatchState.set_selected_account_number,
                    disabled=dis,
                ),
            ),
            rx.box(),
            columns="3",
            spacing="4",
        ),
        _field(
            "Description",
            rx.text_area(
                value=BatchState.selected_row.description,
                on_change=BatchState.set_selected_description,
                disabled=dis,
                rows="2",
                width="100%",
            ),
        ),
        direction="column",
        spacing="4",
        **styles.FIELD_EDITOR,
    )


# ---------------------------------------------------------------------------
# Public component
# ---------------------------------------------------------------------------


def log_panel() -> rx.Component:
    """Render the right-column panel: dark log stream + field editor."""
    return rx.flex(
        _panel_header(),
        rx.box(
            rx.foreach(BatchState.visible_logs, _log_item),
            **styles.LOG_PANEL,
        ),
        _field_editor(),
        direction="column",
        flex="1",
        min_height="0",
        **styles.CARD,
    )
