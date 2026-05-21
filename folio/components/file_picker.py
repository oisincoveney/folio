"""File picker shown before any files are loaded."""

import reflex as rx

from folio.state import AppState

_PICK_ID = "folio-pdf-chooser"


def file_picker() -> rx.Component:
    """Render PDF source buttons with optional parse progress."""
    return rx.flex(
        rx.flex(
            rx.flex(
                rx.upload(
                    rx.button(
                        rx.icon("file_plus", size=14),
                        "Choose PDFs",
                        variant="solid",
                        size="3",
                    ),
                    id=_PICK_ID,
                    accept={"application/pdf": [".pdf"]},
                    multiple=True,
                    on_drop=AppState.handle_upload(rx.upload_files(upload_id=_PICK_ID)),
                    border="none",
                    padding="0",
                    width="fit-content",
                    display="inline-flex",
                ),
                rx.button(
                    rx.icon("folder_open", size=14),
                    "Choose Folder",
                    variant="soft",
                    color_scheme="gray",
                    size="3",
                    on_click=AppState.handle_folder_source,
                ),
                gap="3",
                justify="center",
                align="center",
            ),
            rx.cond(
                AppState.parsing,
                rx.flex(
                    rx.progress(value=AppState.progress_pct, max=100, width="100%"),
                    rx.text(
                        AppState.completed,
                        " of ",
                        AppState.total,
                        " files",
                        size="1",
                        color="var(--gray-9)",
                    ),
                    direction="column",
                    gap="2",
                    width="100%",
                    align="center",
                ),
            ),
            direction="column",
            gap="6",
            align="center",
            width="100%",
            max_width="400px",
        ),
        align="center",
        justify="center",
        flex_grow="1",
        width="100%",
    )
