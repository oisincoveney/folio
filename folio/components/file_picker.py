"""File picker shown before any files are loaded."""

import reflex as rx

from folio.states.batch import BatchState

_PICK_ID = "folio-pdf-chooser"


def upload_drop_event() -> rx.event.EventSpec:
    """Upload dropped PDFs; the upload handler starts parsing after staging."""
    return BatchState.handle_upload(rx.upload_files(upload_id=_PICK_ID))


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
                    on_drop=upload_drop_event(),
                    border="none",
                    padding="0",
                    width="fit-content",
                    display="inline-flex",
                ),
                spacing="3",
                justify="center",
                align="center",
            ),
            rx.cond(
                BatchState.parsing,
                rx.flex(
                    rx.progress(value=BatchState.progress_pct, max=100, width="100%"),
                    rx.text(
                        BatchState.completed,
                        " of ",
                        BatchState.total,
                        " files",
                        size="1",
                        color="var(--gray-9)",
                    ),
                    direction="column",
                    spacing="2",
                    width="100%",
                    align="center",
                ),
            ),
            direction="column",
            spacing="6",
            align="center",
            width="100%",
            max_width="400px",
        ),
        align="center",
        justify="center",
        flex_grow="1",
        width="100%",
    )
