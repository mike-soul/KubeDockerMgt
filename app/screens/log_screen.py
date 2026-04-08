"""Live log streaming screen for containers and pods."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog, Static
from textual.worker import Worker, WorkerState, get_current_worker


class LogScreen(Screen):
    """Full-screen live log viewer with tail follow."""

    BINDINGS = [
        Binding("escape,q", "app.pop_screen", "Back"),
        Binding("c", "clear_log", "Clear"),
        Binding("end", "scroll_end", "Bottom"),
        Binding("home", "scroll_home", "Top"),
    ]

    CSS = """
    LogScreen {
        layout: vertical;
    }
    LogScreen > #log-header {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    LogScreen > RichLog {
        height: 1fr;
        border: none;
        scrollbar-color: $primary;
    }
    LogScreen > Footer {
        height: 1;
    }
    """

    def __init__(
        self,
        resource_name: str,
        stream_fn,  # callable[[], Generator[str, None, None]]
    ) -> None:
        """
        Args:
            resource_name: Displayed in header bar.
            stream_fn: Zero-arg callable that returns a str generator (runs in thread).
        """
        super().__init__()
        self._resource_name = resource_name
        self._stream_fn = stream_fn
        self._worker: Worker | None = None

    def compose(self) -> ComposeResult:
        yield Static(f" Logs: {self._resource_name}  [ESC] back  [C] clear  [End] bottom", id="log-header")
        yield RichLog(highlight=True, markup=False, wrap=True, id="log")
        yield Footer()

    def on_mount(self) -> None:
        self._worker = self.run_worker(self._tail_logs, thread=True)

    def _tail_logs(self) -> None:
        worker = get_current_worker()
        log_widget = self.query_one(RichLog)
        try:
            for line in self._stream_fn():
                if worker.is_cancelled:
                    break
                self.call_from_thread(log_widget.write, line)
        except Exception as exc:
            self.call_from_thread(log_widget.write, f"[red][error] {exc}[/red]")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state in (WorkerState.ERROR, WorkerState.CANCELLED):
            log_widget = self.query_one(RichLog)
            log_widget.write("[dim]--- stream ended ---[/dim]")

    def action_clear_log(self) -> None:
        self.query_one(RichLog).clear()

    def action_scroll_end(self) -> None:
        self.query_one(RichLog).scroll_end(animate=False)

    def action_scroll_home(self) -> None:
        self.query_one(RichLog).scroll_home(animate=False)

    def on_unmount(self) -> None:
        if self._worker:
            self._worker.cancel()
