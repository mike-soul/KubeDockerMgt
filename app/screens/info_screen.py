"""Resource info/inspect screen — pretty-prints JSON detail."""
from __future__ import annotations

import json
from datetime import date, datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static
from textual.scroll_view import ScrollView
from textual.widgets import TextArea


def _default_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class InfoScreen(Screen):
    """Scrollable JSON view of a resource's full detail."""

    BINDINGS = [
        Binding("escape,q", "app.pop_screen", "Back"),
        Binding("end", "scroll_end", "Bottom"),
        Binding("home", "scroll_home", "Top"),
    ]

    CSS = """
    InfoScreen {
        layout: vertical;
    }
    InfoScreen > #info-header {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    InfoScreen > TextArea {
        height: 1fr;
        border: none;
    }
    InfoScreen > Footer {
        height: 1;
    }
    """

    def __init__(self, resource_name: str, data: dict) -> None:
        super().__init__()
        self._resource_name = resource_name
        self._data = data

    def compose(self) -> ComposeResult:
        yield Static(
            f" Info: {self._resource_name}  [ESC] back",
            id="info-header",
        )
        text = json.dumps(self._data, indent=2, default=_default_serializer)
        yield TextArea(text, read_only=True, language="json", id="content")
        yield Footer()

    def action_scroll_end(self) -> None:
        self.query_one(TextArea).scroll_end(animate=False)

    def action_scroll_home(self) -> None:
        self.query_one(TextArea).scroll_home(animate=False)
