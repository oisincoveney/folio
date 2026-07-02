"""ModelSelectionState — opencode model identifier shared by parse + header.

Common ancestor for ``BatchState`` (the parse pipeline reads ``self.model`` when
dispatching a job) and ``HeaderState`` (the dropdown lists/filters
``self.models``). Lives above both because Reflex substates cannot iterate each
other's list fields inside ``@rx.var``: a cross-state reference is a symbolic
``Var`` at compute time, not a real list. Inheritance gives subclasses real
attribute access on a shared slot in the state tree.
"""

from __future__ import annotations

import asyncio

import reflex as rx

from folio.services import parser as parse_mod


def model_state_from_options(
    options: list[dict[str, str | bool]],
) -> tuple[list[dict[str, str | bool]], str]:
    """Return UI model rows and default selection from loaded parser options."""
    models = [{"id": str(m["id"]), "pdf": bool(m["pdf"])} for m in options]
    return models, parse_mod.select_default_model(options)


class ModelSelectionState(rx.State):
    """The active opencode model id plus the list of available options."""

    model: str = ""
    models: list[dict] = []

    @rx.event(background=True)
    async def load_models(self) -> None:
        """Populate the model list from parse module options.

        Runs the blocking ``opencode models`` subprocess on a thread pool so the
        Reflex event loop is not stalled (fixes the ``EventFuture`` worker crash
        that occurred with the synchronous version in Reflex 0.9).
        """
        options = await asyncio.to_thread(parse_mod.get_model_options)
        models, default_model = model_state_from_options(options)
        async with self:
            self.models = models
            if not self.model:
                self.model = default_model

    def update_model(self, model: str) -> None:
        """Update the active model selection."""
        self.model = model
