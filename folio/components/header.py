"""Header bar: logo, searchable model dropdown with PDF/non-PDF sections."""

import reflex as rx

from folio.states.model_selection import ModelSelectionState


class HeaderState(ModelSelectionState):
    """UI state for the header model dropdown.

    Subclasses ``ModelSelectionState`` so the ``@rx.var``s below can iterate
    ``self.models`` at compute time. (Reflex does not support iterating a
    sibling state's symbolic ``Var`` inside ``@rx.var``.)
    """

    search: str = ""

    def set_search(self, v: str) -> None:
        """Update the model search filter."""
        self.search = v

    @rx.var
    def filtered_pdf_models(self) -> list[dict]:
        """Return PDF-capable models matching the current search."""
        s = self.search.lower()
        return [
            m for m in self.models if m["pdf"] and (not s or s in m["id"].lower())
        ]

    @rx.var
    def filtered_non_pdf_models(self) -> list[dict]:
        """Return non-PDF models matching the current search."""
        s = self.search.lower()
        return [
            m for m in self.models
            if not m["pdf"] and (not s or s in m["id"].lower())
        ]


def _model_option(model: dict) -> rx.Component:
    """Render one model option in the dropdown list."""
    return rx.box(
        rx.text(model["id"], size="2"),
        on_click=HeaderState.update_model(model["id"]),
        padding="var(--space-1) var(--space-3)",
        cursor="pointer",
        border_radius="var(--radius-2)",
        _hover={"background": "var(--gray-3)"},
    )


def _model_section(title: str, models: rx.Var) -> rx.Component:
    """Render a labeled group of model options."""
    return rx.flex(
        rx.text(
            title,
            size="1",
            weight="medium",
            color="var(--gray-9)",
            style={"textTransform": "uppercase", "letterSpacing": "0.06em"},
            padding="var(--space-2) var(--space-3) var(--space-1)",
            display="block",
        ),
        rx.foreach(models, _model_option),
        direction="column",
    )


def _nav_link(label: str, href: str) -> rx.Component:
    """Render a primary navigation link, accent-highlighted when active."""
    return rx.link(
        rx.text(label, size="2", weight="medium"),
        href=href,
        color=rx.cond(
            rx.State.router.page.path == href,
            "var(--accent-11)",
            "var(--gray-11)",
        ),
        _hover={"color": "var(--accent-11)"},
        text_decoration="none",
    )


def header() -> rx.Component:
    """Render the top header bar."""
    return rx.flex(
        rx.text(
            "folio",
            size="3",
            weight="bold",
            color="var(--gray-12)",
            font_family="'IBM Plex Mono', monospace",
            letter_spacing="-0.02em",
        ),
        rx.flex(
            _nav_link("Parse", "/"),
            _nav_link("Files", "/files"),
            _nav_link("Data", "/data"),
            gap="4",
            align="center",
        ),
        rx.flex(
            rx.popover.root(
                rx.popover.trigger(
                    rx.button(
                        HeaderState.model,
                        rx.icon("chevron_down", size=13),
                        variant="soft",
                        color_scheme="gray",
                        gap="2",
                    ),
                ),
                rx.popover.content(
                    rx.flex(
                        rx.input(
                            placeholder="Search models…",
                            value=HeaderState.search,
                            on_change=HeaderState.set_search,
                            size="1",
                        ),
                        rx.cond(
                            HeaderState.filtered_pdf_models.length() > 0,
                            _model_section(
                                "PDF models", HeaderState.filtered_pdf_models,
                            ),
                        ),
                        rx.cond(
                            HeaderState.filtered_non_pdf_models.length() > 0,
                            _model_section(
                                "Other models", HeaderState.filtered_non_pdf_models,
                            ),
                        ),
                        direction="column",
                        gap="1",
                        width="320px",
                        max_height="400px",
                        overflow_y="auto",
                    ),
                    side="bottom",
                    align="start",
                ),
            ),
            rx.icon_button(
                rx.icon("refresh_cw", size=13),
                variant="ghost",
                color_scheme="gray",
                on_click=HeaderState.load_models,
                title="Refresh models",
            ),
            gap="1",
            align="center",
        ),
        align="center",
        justify="between",
        padding="var(--space-3) var(--space-4)",
        border_bottom="1px solid var(--gray-4)",
        width="100%",
    )
