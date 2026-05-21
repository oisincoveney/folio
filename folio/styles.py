"""Design tokens for folio UI — all style values live here, never inline."""

# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------

CARD: dict = {
    "border_radius": "var(--radius-3)",
    "background": "var(--color-panel-solid)",
    "box_shadow": "var(--shadow-2)",
    "overflow": "hidden",
}

PANEL_HEADER: dict = {
    "border_bottom": "1px solid var(--gray-4)",
    "padding": "var(--space-3) var(--space-4)",
}

# ---------------------------------------------------------------------------
# Log panel (dark)
# ---------------------------------------------------------------------------

LOG_PANEL_HEADER: dict = {
    "border_bottom": "1px solid rgba(255,255,255,0.07)",
    "padding": "var(--space-3) var(--space-4)",
    "background": "#0e0f18",
    "color": "var(--gray-1)",
    "flex_shrink": "0",
}

LOG_PANEL: dict = {
    "background": "#0e0f18",
    "color": "var(--gray-1)",
    "flex_grow": "1",
    "overflow_y": "auto",
    "padding": "var(--space-3)",
    "min_height": "0",
}

LOG_ENTRY: dict = {
    "border_radius": "var(--radius-2)",
    "border": "1px solid rgba(255,255,255,0.07)",
    "background": "rgba(99,102,241,0.04)",
    "margin_bottom": "var(--space-2)",
}

LOG_ENTRY_HEADER: dict = {
    "border_bottom": "1px solid rgba(255,255,255,0.07)",
    "padding": "var(--space-2) var(--space-3)",
}

LOG_BODY: dict = {
    "padding": "var(--space-2) var(--space-3)",
    "white_space": "pre-wrap",
    "word_break": "break-words",
    "line_height": "1.6",
    "color": "var(--gray-3)",
    "font_size": "var(--font-size-1)",
}

LOG_BODY_MONO: dict = {**LOG_BODY, "font_family": "'IBM Plex Mono', monospace"}

# ---------------------------------------------------------------------------
# Field editor (below log panel)
# ---------------------------------------------------------------------------

FIELD_EDITOR: dict = {
    "border_top": "1px solid var(--gray-4)",
    "padding": "var(--space-4)",
    "flex_shrink": "0",
    "background": "var(--color-panel-solid)",
}

FIELD_LABEL: dict = {
    "font_size": "var(--font-size-1)",
    "font_weight": "500",
    "text_transform": "uppercase",
    "letter_spacing": "0.06em",
    "color": "var(--gray-9)",
    "display": "block",
}

# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

TABLE_HEADER_CELL: dict = {
    "font_size": "var(--font-size-1)",
    "font_weight": "500",
    "text_transform": "uppercase",
    "letter_spacing": "0.06em",
    "color": "var(--gray-9)",
    "white_space": "nowrap",
}

TABLE_CELL_MONO: dict = {
    "font_family": "'IBM Plex Mono', monospace",
    "font_size": "var(--font-size-1)",
    "color": "var(--gray-11)",
    "white_space": "nowrap",
}

TABLE_SUBTITLE: dict = {
    "font_size": "var(--font-size-1)",
    "color": "var(--gray-9)",
    "overflow": "hidden",
    "text_overflow": "ellipsis",
    "white_space": "nowrap",
}

TABLE_ERROR_TEXT: dict = {
    "font_size": "var(--font-size-1)",
    "color": "var(--amber-11)",
    "overflow": "hidden",
    "text_overflow": "ellipsis",
    "white_space": "nowrap",
}

# ---------------------------------------------------------------------------
# Semantic status colors (for rx.badge color_scheme=)
# ---------------------------------------------------------------------------

STATUS_COLOR: dict[str, str] = {
    "pending": "gray",
    "active": "blue",
    "done": "green",
    "error": "amber",
}
