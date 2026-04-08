"""Shown when neither Docker nor Kubernetes can be reached."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Label, Static


class ErrorScreen(Screen):

    BINDINGS = [Binding("q", "app.quit", "Quit")]

    CSS = """
    ErrorScreen {
        align: center middle;
        background: $background;
    }
    #error-box {
        width: 64;
        height: auto;
        border: round $error;
        padding: 1 2;
    }
    #error-title {
        text-align: center;
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    #error-subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    .error-row {
        margin-bottom: 1;
    }
    .error-label {
        text-style: bold;
        color: $text-muted;
    }
    .error-detail {
        color: $text;
    }
    #error-hint {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    ErrorScreen > Footer {
        dock: bottom;
    }
    """

    def __init__(self, docker_err: str, kube_err: str) -> None:
        super().__init__()
        self._docker_err = docker_err or "not installed or daemon not running"
        self._kube_err   = kube_err   or "no kubeconfig found or cluster unreachable"

    def compose(self) -> ComposeResult:
        with Static(id="error-box"):
            yield Label("KubeDock", id="error-title")
            yield Label("No backends could be reached", id="error-subtitle")
            with Static(classes="error-row"):
                yield Label("Docker   ", classes="error-label")
                yield Label(self._docker_err, classes="error-detail")
            with Static(classes="error-row"):
                yield Label("Kubernetes  ", classes="error-label")
                yield Label(self._kube_err, classes="error-detail")
            yield Label("Make sure Docker is running or a kubeconfig is present, then restart.", id="error-hint")
        yield Footer()
