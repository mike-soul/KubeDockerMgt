"""Main screen: tab bar + data table + context bar."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Label, Static, Tab, Tabs

from app.docker_client import DockerClient
from app.kube_client import KubeClient


# ---------------------------------------------------------------------------
# Tab definitions
# ---------------------------------------------------------------------------

@dataclass
class TabDef:
    id: str
    label: str
    backend: str  # "docker" | "kube"
    columns: list[tuple[str, str]]  # (key, header)
    supports_logs: bool = False
    supports_start_stop: bool = False


DOCKER_TABS: list[TabDef] = [
    TabDef(
        id="containers",
        label="Containers",
        backend="docker",
        columns=[
            ("name", "Name"),
            ("status", "Status"),
            ("image", "Image"),
            ("ports", "Ports"),
            ("id", "ID"),
        ],
        supports_logs=True,
        supports_start_stop=True,
    ),
    TabDef(
        id="volumes",
        label="Volumes",
        backend="docker",
        columns=[
            ("name", "Name"),
            ("driver", "Driver"),
            ("scope", "Scope"),
            ("mountpoint", "Mountpoint"),
        ],
    ),
    TabDef(
        id="networks",
        label="Networks",
        backend="docker",
        columns=[
            ("name", "Name"),
            ("driver", "Driver"),
            ("scope", "Scope"),
            ("subnet", "Subnet"),
            ("id", "ID"),
        ],
    ),
]

KUBE_TABS: list[TabDef] = [
    TabDef(
        id="pods",
        label="Pods",
        backend="kube",
        columns=[
            ("name", "Name"),
            ("namespace", "Namespace"),
            ("status", "Status"),
            ("ready", "Ready"),
            ("restarts", "Restarts"),
            ("node", "Node"),
            ("age", "Age"),
        ],
        supports_logs=True,
    ),
    TabDef(
        id="nodes",
        label="Nodes",
        backend="kube",
        columns=[
            ("name", "Name"),
            ("status", "Status"),
            ("roles", "Roles"),
            ("version", "Version"),
            ("os", "OS"),
            ("age", "Age"),
        ],
    ),
    TabDef(
        id="services",
        label="Services",
        backend="kube",
        columns=[
            ("name", "Name"),
            ("namespace", "Namespace"),
            ("type", "Type"),
            ("cluster_ip", "Cluster IP"),
            ("external_ip", "External IP"),
            ("ports", "Ports"),
            ("age", "Age"),
        ],
    ),
    TabDef(
        id="deployments",
        label="Deployments",
        backend="kube",
        columns=[
            ("name", "Name"),
            ("namespace", "Namespace"),
            ("ready", "Ready"),
            ("up_to_date", "Up-to-date"),
            ("available", "Available"),
            ("age", "Age"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------

class MainScreen(Screen):

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("enter", "open_actions", "Actions"),
        Binding("d", "switch_docker_context", "Docker ctx"),
        Binding("k", "switch_kube_context", "Kube ctx"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, docker: DockerClient, kube: KubeClient) -> None:
        super().__init__()
        self.docker = docker
        self.kube = kube
        self._tabs: list[TabDef] = self._build_tab_list()
        self._active_tab: TabDef = self._tabs[0]
        self._rows: list[dict] = []

    # ------------------------------------------------------------------
    # Build available tab list based on what is reachable
    # ------------------------------------------------------------------

    def _build_tab_list(self) -> list[TabDef]:
        tabs: list[TabDef] = []
        if self.docker.available:
            tabs.extend(DOCKER_TABS)
        if self.kube.available:
            tabs.extend(KUBE_TABS)
        return tabs

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("", id="context-bar")
        yield Tabs(*[Tab(t.label, id=t.id) for t in self._tabs])
        yield DataTable(id="main-table", zebra_stripes=True, cursor_type="row")
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._update_context_bar()
        self._load_tab(self._active_tab)
        self.query_one(DataTable).focus()

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        tab_def = self._tab_by_id(event.tab.id)
        if tab_def:
            self._active_tab = tab_def
            self._load_tab(tab_def)
            self.query_one(DataTable).focus()

    def _tab_by_id(self, tab_id: str) -> TabDef | None:
        for t in self._tabs:
            if t.id == tab_id:
                return t
        return None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_tab(self, tab: TabDef) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)

        for key, header in tab.columns:
            table.add_column(header, key=key)

        self._rows = self._fetch_data(tab)
        self._populate_table(table, tab)
        self._set_status(f"{len(self._rows)} item(s)")

    def _fetch_data(self, tab: TabDef) -> list[dict]:
        fetch_map = {
            "containers": self.docker.list_containers,
            "volumes": self.docker.list_volumes,
            "networks": self.docker.list_networks,
            "pods": self.kube.list_pods,
            "nodes": self.kube.list_nodes,
            "services": self.kube.list_services,
            "deployments": self.kube.list_deployments,
        }
        fn = fetch_map.get(tab.id)
        return fn() if fn else []

    def _populate_table(self, table: DataTable, tab: TabDef) -> None:
        for row in self._rows:
            cells = [str(row.get(col_key, "-")) for col_key, _ in tab.columns]
            table.add_row(*cells)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_refresh(self) -> None:
        self._load_tab(self._active_tab)
        self.app.notify("Refreshed", timeout=1)

    def action_open_actions(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row < 0 or not self._rows:
            return
        row_data = self._rows[table.cursor_row]
        self._show_action_menu(row_data)

    def _show_action_menu(self, row: dict) -> None:
        from app.screens.modals import ActionMenu

        name = row.get("name", row.get("id", "?"))
        tab = self._active_tab
        actions: list[tuple[str, str]] = [("info", "Info / Inspect")]

        if tab.supports_logs:
            actions.append(("logs", "Logs (live tail)"))
        if tab.supports_start_stop:
            actions.append(("start", "Start"))
            actions.append(("stop", "Stop"))
        actions.append(("delete", "Delete"))

        def handle_action(action: str | None) -> None:
            if action:
                self._dispatch_action(action, row)

        self.app.push_screen(ActionMenu(name, actions), handle_action)

    def _dispatch_action(self, action: str, row: dict) -> None:
        tab = self._active_tab
        name = row.get("name", row.get("id", "?"))

        if action == "info":
            self._open_info(tab, row)
        elif action == "logs":
            self._open_logs(tab, row)
        elif action == "start":
            self._do_start(row)
        elif action == "stop":
            self._do_stop(row)
        elif action == "delete":
            self._confirm_delete(tab, row, name)

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def _open_info(self, tab: TabDef, row: dict) -> None:
        from app.screens.info_screen import InfoScreen

        name = row.get("name", "?")
        raw_id = row.get("_raw_id", name)
        namespace = row.get("_namespace")

        data: dict = {}
        if tab.id == "containers":
            data = self.docker.inspect_container(raw_id)
        elif tab.id == "volumes":
            data = self.docker.inspect_volume(raw_id)
        elif tab.id == "networks":
            data = self.docker.inspect_network(raw_id)
        elif tab.id == "pods":
            data = self.kube.describe_pod(name, namespace or "default")
        elif tab.id == "nodes":
            data = self.kube.describe_node(name)
        elif tab.id == "services":
            data = self.kube.describe_service(name, namespace or "default")
        elif tab.id == "deployments":
            data = self.kube.describe_deployment(name, namespace or "default")

        self.app.push_screen(InfoScreen(name, data))

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def _open_logs(self, tab: TabDef, row: dict) -> None:
        from app.screens.log_screen import LogScreen

        name = row.get("name", "?")
        raw_id = row.get("_raw_id", name)
        namespace = row.get("_namespace")

        if tab.id == "containers":
            stream_fn = lambda: self.docker.stream_container_logs(raw_id)
        elif tab.id == "pods":
            stream_fn = lambda: self.kube.stream_pod_logs(name, namespace or "default")
        else:
            return

        self.app.push_screen(LogScreen(name, stream_fn))

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------

    def _do_start(self, row: dict) -> None:
        raw_id = row.get("_raw_id", row.get("name", ""))
        result = self.docker.start_container(raw_id)
        if result is True:
            self.app.notify(f"Started {row.get('name', raw_id)}")
            self.action_refresh()
        else:
            self.app.notify(f"Error: {result}", severity="error")

    def _do_stop(self, row: dict) -> None:
        raw_id = row.get("_raw_id", row.get("name", ""))
        result = self.docker.stop_container(raw_id)
        if result is True:
            self.app.notify(f"Stopped {row.get('name', raw_id)}")
            self.action_refresh()
        else:
            self.app.notify(f"Error: {result}", severity="error")

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def _confirm_delete(self, tab: TabDef, row: dict, name: str) -> None:
        from app.screens.modals import ConfirmDialog

        def do_delete(confirmed: bool) -> None:
            if confirmed:
                self._do_delete(tab, row)

        self.app.push_screen(
            ConfirmDialog(f"Delete '{name}'? This cannot be undone."),
            do_delete,
        )

    def _do_delete(self, tab: TabDef, row: dict) -> None:
        name = row.get("name", "?")
        raw_id = row.get("_raw_id", name)
        namespace = row.get("_namespace")

        result: bool | str = False
        if tab.id == "containers":
            result = self.docker.remove_container(raw_id)
        elif tab.id == "volumes":
            result = self.docker.remove_volume(raw_id)
        elif tab.id == "networks":
            result = self.docker.remove_network(raw_id)
        elif tab.id == "pods":
            result = self.kube.delete_pod(name, namespace or "default")
        elif tab.id == "services":
            result = self.kube.delete_service(name, namespace or "default")
        elif tab.id == "deployments":
            result = self.kube.delete_deployment(name, namespace or "default")

        if result is True:
            self.app.notify(f"Deleted {name}")
            self.action_refresh()
        else:
            self.app.notify(f"Error: {result}", severity="error")

    # ------------------------------------------------------------------
    # Context switching
    # ------------------------------------------------------------------

    def action_switch_docker_context(self) -> None:
        if not self.docker.available and not self.docker.contexts:
            self.app.notify("Docker not available", severity="warning")
            return
        from app.screens.modals import ContextSwitcher

        names = self.docker.context_names()
        if not names:
            self.app.notify("No Docker contexts found", severity="warning")
            return

        def on_chosen(name: str | None) -> None:
            if name and name != self.docker.current_context:
                result = self.docker.switch_context(name)
                if result is True:
                    self.app.notify(f"Docker context: {name}")
                    self._reload_after_context_change()
                else:
                    self.app.notify(f"Switch failed: {result}", severity="error")

        self.app.push_screen(
            ContextSwitcher("Docker", names, self.docker.current_context),
            on_chosen,
        )

    def action_switch_kube_context(self) -> None:
        if not self.kube.contexts:
            self.app.notify("No Kubernetes contexts found", severity="warning")
            return
        from app.screens.modals import ContextSwitcher

        def on_chosen(name: str | None) -> None:
            if name and name != self.kube.current_context:
                result = self.kube.switch_context(name)
                if result is True:
                    self.app.notify(f"Kubernetes context: {name}")
                    self._reload_after_context_change()
                else:
                    self.app.notify(f"Switch failed: {result}", severity="error")

        self.app.push_screen(
            ContextSwitcher("Kubernetes", self.kube.contexts, self.kube.current_context),
            on_chosen,
        )

    def _reload_after_context_change(self) -> None:
        self._update_context_bar()
        self._load_tab(self._active_tab)

    # ------------------------------------------------------------------
    # Status / context bar helpers
    # ------------------------------------------------------------------

    def _update_context_bar(self) -> None:
        parts: list[str] = []
        if self.docker.available:
            parts.append(f"Docker: {self.docker.current_context}")
        else:
            parts.append("Docker: unavailable")
        if self.kube.available:
            parts.append(f"K8s: {self.kube.current_context}")
        else:
            parts.append("K8s: unavailable")
        self.query_one("#context-bar", Static).update("  |  ".join(parts))

    def _set_status(self, msg: str) -> None:
        self.query_one("#status-bar", Static).update(msg)
