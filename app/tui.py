"""Root application — initialises clients and launches main screen."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static

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
        color: $text-muted;
    }
    Tab.-active,
    Tabs:blur Tab.-active,
    Tabs:focus Tab.-active {
        color: $text;
        text-style: bold;
        background: $primary-darken-2;
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

    """

    def on_mount(self) -> None:
        self.run_worker(self._boot, thread=True)

    def _boot(self) -> None:
        """Initialise clients in a background thread so the UI stays responsive."""
        docker = DockerClient()
        kube = KubeClient()

        if not docker.available and not kube.available:
            from app.screens.error_screen import ErrorScreen
            self.call_from_thread(self.push_screen, ErrorScreen(docker.error, kube.error))
        else:
            from app.screens.main_screen import MainScreen
            self.call_from_thread(self.push_screen, MainScreen(docker, kube))

    def compose(self) -> ComposeResult:
        # Shown briefly while _boot runs
        with Static(id="splash"):
            yield Static("Connecting to Docker / Kubernetes…")

