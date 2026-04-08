"""Modal dialogs: action menu, context switcher, confirmation."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static


# ---------------------------------------------------------------------------
# Action menu
# ---------------------------------------------------------------------------

class ActionMenu(ModalScreen[str | None]):
    """Overlay showing available actions for a selected resource."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close", show=False),
    ]

    CSS = """
    ActionMenu {
        align: center middle;
    }
    ActionMenu > #panel {
        width: 40;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1 2;
    }
    ActionMenu > #panel > #title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        text-align: center;
    }
    ActionMenu > #panel > ListView {
        height: auto;
        background: $surface;
        border: none;
    }
    ActionMenu > #panel > ListView > ListItem {
        padding: 0 1;
    }
    ActionMenu > #panel > ListView > ListItem:hover,
    ActionMenu > #panel > ListView > ListItem.-highlighted {
        background: $primary 30%;
    }
    """

    def __init__(self, resource_name: str, actions: list[tuple[str, str]]) -> None:
        """
        Args:
            resource_name: Display name shown in title bar.
            actions: List of (action_id, label) pairs.
        """
        super().__init__()
        self._resource_name = resource_name
        self._actions = actions

    def compose(self) -> ComposeResult:
        with Static(id="panel"):
            yield Label(self._resource_name, id="title")
            with ListView():
                for action_id, label in self._actions:
                    item = ListItem(Label(label), id=f"action-{action_id}")
                    item.data = action_id  # type: ignore[attr-defined]
                    yield item

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        action_id = getattr(event.item, "data", None)
        self.dismiss(action_id)


# ---------------------------------------------------------------------------
# Context switcher
# ---------------------------------------------------------------------------

class ContextSwitcher(ModalScreen[str | None]):
    """Pick a Docker or Kubernetes context."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Close", show=False),
    ]

    CSS = """
    ContextSwitcher {
        align: center middle;
    }
    ContextSwitcher > #panel {
        width: 60;
        height: auto;
        max-height: 24;
        background: $surface;
        border: round $accent;
        padding: 1 2;
    }
    ContextSwitcher > #panel > #title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        text-align: center;
    }
    ContextSwitcher > #panel > ListView {
        height: auto;
        max-height: 16;
        background: $surface;
    }
    ContextSwitcher > #panel > ListView > ListItem.-highlighted {
        background: $accent 30%;
    }
    """

    def __init__(self, backend: str, contexts: list[str], current: str) -> None:
        """
        Args:
            backend: "Docker" or "Kubernetes"
            contexts: Available context names.
            current: Currently active context name.
        """
        super().__init__()
        self._backend = backend
        self._contexts = contexts
        self._current = current

    def compose(self) -> ComposeResult:
        with Static(id="panel"):
            yield Label(f"Switch {self._backend} context", id="title")
            with ListView():
                for name in self._contexts:
                    marker = " [active]" if name == self._current else ""
                    item = ListItem(Label(f"{name}{marker}"), id=f"ctx-{name}")
                    item.data = name  # type: ignore[attr-defined]
                    yield item

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(getattr(event.item, "data", None))


# ---------------------------------------------------------------------------
# Confirmation dialog
# ---------------------------------------------------------------------------

class ConfirmDialog(ModalScreen[bool]):
    """Simple yes/no confirmation before a destructive action."""

    BINDINGS = [
        Binding("escape", "dismiss(False)", "Cancel", show=False),
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "dismiss(False)", "No", show=False),
    ]

    CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > #panel {
        width: 50;
        height: auto;
        background: $surface;
        border: round $error;
        padding: 1 2;
    }
    ConfirmDialog > #panel > #message {
        margin-bottom: 1;
        text-align: center;
    }
    ConfirmDialog > #panel > #buttons {
        layout: horizontal;
        align: center middle;
        height: 3;
    }
    ConfirmDialog > #panel > #buttons > Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Static(id="panel"):
            yield Label(self._message, id="message")
            with Static(id="buttons"):
                yield Button("Yes [Y]", variant="error", id="btn-yes")
                yield Button("No [N]", variant="default", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")

    def action_confirm(self) -> None:
        self.dismiss(True)
