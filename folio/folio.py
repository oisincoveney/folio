"""Main Reflex application entry point."""

import reflex as rx

from folio.components.file_picker import file_picker
from folio.components.header import header
from folio.components.results_table import results_table
from folio.state import AppState


def index() -> rx.Component:
    """Render the main page."""
    return rx.flex(
        header(),
        rx.box(
            rx.cond(AppState.has_rows, results_table(), file_picker()),
            flex_grow="1",
            display="flex",
            flex_direction="column",
            overflow="hidden",
            min_height="0",
        ),
        direction="column",
        height="100vh",
        width="100%",
        overflow="hidden",
    )


app = rx.App(
    theme=rx.theme(
        accent_color="indigo",
        gray_color="slate",
        radius="small",
    ),
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap",
    ],
    style={
        "font_family": "'IBM Plex Sans', system-ui, sans-serif",
    },
)
app.add_page(index, on_load=AppState.load_models)
