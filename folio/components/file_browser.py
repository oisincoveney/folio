"""File browser component for browsing and downloading S3 documents by month."""

import reflex as rx

from folio.states.file_browser import FileBrowserState


def _month_item(month: str) -> rx.Component:
    return rx.box(
        rx.text(month, size="2", weight="medium"),
        padding="8px 12px",
        border_radius="var(--radius-2)",
        cursor="pointer",
        background=rx.cond(
            FileBrowserState.browser_month == month,
            "var(--accent-3)",
            "transparent",
        ),
        color=rx.cond(
            FileBrowserState.browser_month == month,
            "var(--accent-11)",
            "var(--gray-12)",
        ),
        _hover={"background": "var(--gray-3)"},
        on_click=FileBrowserState.select_browser_month(month),
        width="100%",
    )


def _file_row(file: dict) -> rx.Component:
    return rx.table.row(
        rx.table.cell(
            rx.text(file["name"], size="2", font_family="'IBM Plex Mono', monospace"),
        ),
        rx.table.cell(
            rx.text(file["size"], size="2", color="var(--gray-9)"), align="right",
        ),
        rx.table.cell(
            rx.text(file["modified"], size="2", color="var(--gray-9)"), align="right",
        ),
        rx.table.cell(
            rx.button(
                rx.icon("download", size=13),
                size="1",
                variant="ghost",
                on_click=FileBrowserState.download_file(file["key"]),
            ),
            align="right",
        ),
    )


def file_browser() -> rx.Component:
    """Render the /files page with a month sidebar and file table."""
    current_files = FileBrowserState.browser_files[FileBrowserState.browser_month]

    return rx.flex(
        rx.box(
            rx.vstack(
                rx.text("Months", size="1", color="var(--gray-9)", weight="medium"),
                rx.cond(
                    FileBrowserState.browser_loading,
                    rx.spinner(size="2"),
                    rx.vstack(
                        rx.foreach(FileBrowserState.browser_months, _month_item),
                        gap="1",
                        width="100%",
                    ),
                ),
                gap="3",
                align="start",
                width="100%",
                padding="16px",
            ),
            width="180px",
            min_width="180px",
            border_right="1px solid var(--gray-4)",
            height="100%",
            overflow_y="auto",
        ),
        rx.box(
            rx.cond(
                FileBrowserState.browser_loading,
                rx.flex(
                    rx.spinner(size="3"),
                    align="center", justify="center", height="100%",
                ),
                rx.cond(
                    FileBrowserState.browser_month == "",
                    rx.flex(
                        rx.text(
                            "Select a month to browse files.",
                            color="var(--gray-9)",
                            size="2",
                        ),
                        align="center",
                        justify="center",
                        height="100%",
                    ),
                    rx.vstack(
                        rx.flex(
                            rx.text(
                                FileBrowserState.browser_month,
                                size="2",
                                weight="medium",
                                color="var(--gray-12)",
                            ),
                            rx.button(
                                rx.icon("archive", size=14),
                                "Download all",
                                size="1",
                                variant="soft",
                                disabled=current_files.length() == 0,
                                on_click=FileBrowserState.download_month_zip(
                                    FileBrowserState.browser_month,
                                ),
                            ),
                            justify="between",
                            align="center",
                            width="100%",
                        ),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("File"),
                                    rx.table.column_header_cell(
                                        "Size (bytes)", align="right",
                                    ),
                                    rx.table.column_header_cell(
                                        "Modified", align="right",
                                    ),
                                    rx.table.column_header_cell("", align="right"),
                                ),
                            ),
                            rx.table.body(
                                rx.foreach(current_files, _file_row),
                            ),
                            width="100%",
                            variant="surface",
                        ),
                        gap="3",
                        width="100%",
                    ),
                ),
            ),
            flex_grow="1",
            overflow_y="auto",
            padding="16px",
        ),
        width="100%",
        height="100%",
        overflow="hidden",
    )
