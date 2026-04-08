"""Root application — initialises clients and launches main screen."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Label, Static

from app.docker_client import DockerClient
from app.kube_client import KubeClient


class KubeDockTUI(App):
    """KubeDock — a Docker & Kubernetes terminal manager."""

    TITLE = "KubeDock"
    SUB_TITLE = "Docker & Kubernetes Terminal Manager"

    CSS = """
    /* ---- Global ---- */
    Screen {
        background: $background;
    }

    /* ---- Context bar (top status strip) ---- */
    #context-bar {
        height: 1;
        background: $primary-darken-2;
        color: $text-muted;
        padding: 0 1;
        text-style: italic;
    }

    /* ---- Tabs ---- */
    Tabs {
        height: 3;
        background: $surface;
        border-bottom: tall $primary-darken-1;
    }
    Tab {
        padding: 0 2;
    }
    Tab.-active {
        color: $primary;
        text-style: bold;
        border-bottom: tall $primary;
    }

    /* ---- Main data table ---- */
    DataTable {
        height: 1fr;
        background: $background;
        border: none;
    }
    DataTable > .datatable--header {
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: $primary 40%;
    }
    DataTable > .datatable--hover {
        background: $primary 20%;
    }

    /* ---- Status bar ---- */
    #status-bar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }

    /* ---- Footer ---- */
    Footer {
        background: $primary-darken-2;
        color: $text-muted;
    }
    Footer > .footer--key {
        background: $primary;
        color: $background;
    }

    /* ---- Splash / error screen ---- */
    #splash {
        align: center middle;
        height: 1fr;
    }
    #splash > Static {
        width: 60;
        height: auto;
        border: round $error;
        padding: 1 2;
        text-align: center;
    }
    """

    def on_mount(self) -> None:
        self.run_worker(self._boot, thread=True)

    def _boot(self) -> None:
        """Initialise clients in a background thread so the UI stays responsive."""
        docker = DockerClient()
        kube = KubeClient()

        if not docker.available and not kube.available:
            self.call_from_thread(self._show_error, docker.error, kube.error)
        else:
            from app.screens.main_screen import MainScreen
            self.call_from_thread(self.push_screen, MainScreen(docker, kube))

    def compose(self) -> ComposeResult:
        # Shown briefly while _boot runs
        with Static(id="splash"):
            yield Static("Connecting to Docker / Kubernetes…")

    def _show_error(self, docker_err: str, kube_err: str) -> None:
        splash = self.query_one("#splash", Static)
        splash.remove()
        with self.query_one(Static):
            pass
        msg = (
            "Neither Docker nor Kubernetes could be reached.\n\n"
            f"Docker: {docker_err or 'not available'}\n"
            f"Kubernetes: {kube_err or 'not available'}\n\n"
            "Press Q to quit."
        )
        self.mount(Static(msg, id="error-msg"))
        self.bind("q", "quit", description="Quit")
