"""Right panel: dark log stream + field editor for the selected file."""

import reflex as rx

from folio import styles
from folio.models import LogEntry
from folio.state import AppState


class LogPanelState(AppState):
    """UI state for the right-column log panel."""

    show_technical: bool = False

    def toggle_technical(self) -> None:
        """Toggle visibility of technical log entries."""
        self.show_technical = not self.show_technical

    @rx.var
    def visible_logs(self) -> list[LogEntry]:
        """Return log entries for the selected row, filtered by show_technical."""
        row_logs: list[LogEntry] = []
        for row in self.rows:
            if row.file_key == self.selected_file_key:
                row_logs = row.logs
                break
        if not row_logs and self.rows:
            row_logs = self.rows[0].logs
        if self.show_technical:
            return row_logs
        return [e for e in row_logs if not e.technical]

    @rx.var
    def hidden_technical_count(self) -> int:
        """Count of technical entries currently hidden."""
        row_logs: list[LogEntry] = []
        for row in self.rows:
            if row.file_key == self.selected_file_key:
                row_logs = row.logs
                break
        if not row_logs and self.rows:
            row_logs = self.rows[0].logs
        return sum(1 for e in row_logs if e.technical)


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
            gap="2",
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
                AppState.selected_row.filename_original,
                size="2",
                weight="medium",
                color="var(--gray-1)",
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
            rx.text(
                LogPanelState.visible_logs.length(),
                " events",
                size="1",
                color="var(--gray-7)",
            ),
            rx.cond(
                (LogPanelState.hidden_technical_count > 0)
                & ~LogPanelState.show_technical,
                rx.text(
                    " · ",
                    LogPanelState.hidden_technical_count,
                    " hidden",
                    size="1",
                    color="var(--gray-8)",
                ),
            ),
            gap="2",
            align="center",
            min_width="0",
            flex_grow="1",
        ),
        rx.flex(
            rx.cond(
                AppState.selected_row.status == "error",
                rx.button(
                    rx.icon("rotate_cw", size=12),
                    "Retry",
                    size="1",
                    color_scheme="amber",
                    variant="soft",
                    on_click=AppState.retry_row(AppState.selected_file_key),
                ),
            ),
            rx.icon_button(
                rx.icon("wand_2", size=13),
                variant="ghost",
                color_scheme="gray",
                size="1",
                on_click=AppState.rebuild_reference,
                disabled=AppState.selected_row.parsing,
                title="Rebuild reference",
                color="var(--gray-7)",
            ),
            rx.icon_button(
                rx.icon("eye", size=13),
                variant="ghost",
                color_scheme="gray",
                size="1",
                on_click=LogPanelState.toggle_technical,
                title="Toggle technical entries",
                color="var(--gray-7)",
            ),
            rx.match(
                AppState.selected_row.status,
                ("active", rx.spinner(size="1")),
                ("done", rx.icon("circle_check", size=14, color="var(--green-9)")),
                ("error", rx.icon("triangle_alert", size=14, color="var(--amber-9)")),
                rx.icon("circle", size=14, color="var(--gray-7)"),
            ),
            gap="2",
            align="center",
            flex_shrink="0",
        ),
        align="center",
        gap="3",
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
        gap="2",
    )


def _field_editor() -> rx.Component:
    """Render the editable invoice field form below the log panel."""
    dis = AppState.selected_row.parsing
    mono = "'IBM Plex Mono', monospace"
    return rx.flex(
        rx.grid(
            _field(
                "Amount",
                rx.input(
                    value=AppState.selected_row.amount,
                    on_change=AppState.set_selected_amount,
                    disabled=dis,
                    font_family=mono,
                ),
            ),
            _field(
                "Currency",
                rx.input(
                    value=AppState.selected_row.target_currency,
                    on_change=AppState.set_selected_target_currency,
                    disabled=dis,
                    font_family=mono,
                    max_length=3,
                ),
            ),
            _field(
                "Reference",
                rx.input(
                    value=AppState.selected_row.payment_reference,
                    on_change=AppState.set_selected_payment_reference,
                    disabled=dis,
                ),
            ),
            _field(
                "Company",
                rx.input(
                    value=AppState.selected_row.company,
                    on_change=AppState.set_selected_company,
                    disabled=dis,
                ),
            ),
            _field(
                "Invoice #",
                rx.input(
                    value=AppState.selected_row.invoice_number,
                    on_change=AppState.set_selected_invoice_number,
                    disabled=dis,
                ),
            ),
            rx.box(),
            _field(
                "Date",
                rx.input(
                    value=AppState.selected_row.invoice_date,
                    on_change=AppState.set_selected_invoice_date,
                    disabled=dis,
                ),
            ),
            _field(
                "Account",
                rx.input(
                    value=AppState.selected_row.account_number,
                    on_change=AppState.set_selected_account_number,
                    disabled=dis,
                ),
            ),
            rx.box(),
            columns="3",
            gap="1rem",
        ),
        _field(
            "Description",
            rx.text_area(
                value=AppState.selected_row.description,
                on_change=AppState.set_selected_description,
                disabled=dis,
                rows="2",
                width="100%",
            ),
        ),
        direction="column",
        gap="4",
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
            rx.foreach(LogPanelState.visible_logs, _log_item),
            **styles.LOG_PANEL,
        ),
        _field_editor(),
        direction="column",
        flex="1",
        min_height="0",
        **styles.CARD,
    )
