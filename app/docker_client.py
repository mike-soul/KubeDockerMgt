"""Docker client wrapper — gracefully handles missing Docker or stopped daemon."""
from __future__ import annotations

import json
import subprocess
from typing import Any, Generator

try:
    import docker
    from docker.errors import DockerException, NotFound, APIError
    DOCKER_SDK = True
except ImportError:
    DOCKER_SDK = False


class DockerClient:
    def __init__(self) -> None:
        self.available: bool = False
        self.error: str = ""
        self.current_context: str = "default"
        self.contexts: list[dict] = []
        self._client = None
        self._init()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init(self) -> None:
        if not DOCKER_SDK:
            self.error = "docker Python SDK not installed"
            return
        try:
            self.contexts = self._fetch_contexts()
            self.current_context = self._fetch_active_context()
            self._connect()
        except Exception as exc:
            self.error = str(exc)
            self.available = False

    def _connect(self) -> None:
        try:
            self._client = docker.from_env()
            self._client.ping()
            self.available = True
            self.error = ""
        except Exception as exc:
            self.available = False
            self.error = str(exc)

    def _fetch_contexts(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["docker", "context", "ls", "--format", "{{json .}}"],
                capture_output=True, text=True, timeout=5
            )
            contexts = []
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line:
                    try:
                        contexts.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return contexts if contexts else [{"Name": "default", "Current": True}]
        except Exception:
            return [{"Name": "default", "Current": True}]

    def _fetch_active_context(self) -> str:
        try:
            result = subprocess.run(
                ["docker", "context", "show"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() or "default"
        except Exception:
            return "default"

    def context_names(self) -> list[str]:
        return [c.get("Name", "") for c in self.contexts if c.get("Name")]

    # ------------------------------------------------------------------
    # Context switching
    # ------------------------------------------------------------------

    def switch_context(self, name: str) -> bool | str:
        try:
            subprocess.run(
                ["docker", "context", "use", name],
                capture_output=True, text=True, timeout=5, check=True
            )
            self.current_context = name
            self._connect()
            return True
        except subprocess.CalledProcessError as exc:
            return exc.stderr.strip()
        except Exception as exc:
            return str(exc)

    # ------------------------------------------------------------------
    # Containers
    # ------------------------------------------------------------------

    def list_containers(self, all: bool = True) -> list[dict]:
        if not self.available:
            return []
        try:
            containers = [
                c for c in self._client.containers.list(all=all)
                if not c.name.startswith("k8s_")
            ]
            return [
                {
                    "id": c.short_id,
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                    "ports": _format_ports(c.ports),
                    "_raw_id": c.id,
                }
                for c in containers
            ]
        except Exception:
            return []

    def start_container(self, raw_id: str) -> bool | str:
        return self._container_action(raw_id, "start")

    def stop_container(self, raw_id: str) -> bool | str:
        return self._container_action(raw_id, "stop")

    def remove_container(self, raw_id: str, force: bool = True) -> bool | str:
        if not self.available:
            return "Docker not available"
        try:
            self._client.containers.get(raw_id).remove(force=force)
            return True
        except Exception as exc:
            return str(exc)

    def _container_action(self, raw_id: str, action: str) -> bool | str:
        if not self.available:
            return "Docker not available"
        try:
            container = self._client.containers.get(raw_id)
            getattr(container, action)()
            return True
        except Exception as exc:
            return str(exc)

    def inspect_container(self, raw_id: str) -> dict:
        if not self.available:
            return {}
        try:
            return self._client.containers.get(raw_id).attrs
        except Exception:
            return {}

    def stream_container_logs(self, raw_id: str, tail: int = 200) -> Generator[str, None, None]:
        if not self.available:
            return
        try:
            container = self._client.containers.get(raw_id)
            for chunk in container.logs(stream=True, follow=True, tail=tail):
                if isinstance(chunk, bytes):
                    yield chunk.decode("utf-8", errors="replace").rstrip("\n")
                else:
                    yield str(chunk).rstrip("\n")
        except Exception as exc:
            yield f"[error] {exc}"

    # ------------------------------------------------------------------
    # Volumes
    # ------------------------------------------------------------------

    def list_volumes(self) -> list[dict]:
        if not self.available:
            return []
        try:
            return [
                {
                    "name": v.name,
                    "driver": v.attrs.get("Driver", "-"),
                    "mountpoint": v.attrs.get("Mountpoint", "-"),
                    "scope": v.attrs.get("Scope", "-"),
                    "_raw_id": v.name,
                }
                for v in self._client.volumes.list()
            ]
        except Exception:
            return []

    def remove_volume(self, name: str) -> bool | str:
        if not self.available:
            return "Docker not available"
        try:
            self._client.volumes.get(name).remove()
            return True
        except Exception as exc:
            return str(exc)

    def inspect_volume(self, name: str) -> dict:
        if not self.available:
            return {}
        try:
            return self._client.volumes.get(name).attrs
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Networks
    # ------------------------------------------------------------------

    def list_networks(self) -> list[dict]:
        if not self.available:
            return []
        try:
            return [
                {
                    "id": n.short_id,
                    "name": n.name,
                    "driver": n.attrs.get("Driver", "-"),
                    "scope": n.attrs.get("Scope", "-"),
                    "subnet": _network_subnet(n),
                    "_raw_id": n.id,
                }
                for n in self._client.networks.list()
            ]
        except Exception:
            return []

    def remove_network(self, raw_id: str) -> bool | str:
        if not self.available:
            return "Docker not available"
        try:
            self._client.networks.get(raw_id).remove()
            return True
        except Exception as exc:
            return str(exc)

    def inspect_network(self, raw_id: str) -> dict:
        if not self.available:
            return {}
        try:
            return self._client.networks.get(raw_id).attrs
        except Exception:
            return {}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _format_ports(ports: dict) -> str:
    if not ports:
        return "-"
    parts = []
    for container_port, bindings in ports.items():
        if bindings:
            for b in bindings:
                host = b.get("HostIp", "")
                port = b.get("HostPort", "")
                prefix = f"{host}:" if host and host != "0.0.0.0" else ""
                parts.append(f"{prefix}{port}->{container_port}")
        else:
            parts.append(container_port)
    return ", ".join(parts) if parts else "-"


def _network_subnet(network) -> str:
    try:
        config = network.attrs.get("IPAM", {}).get("Config", [])
        if config:
            return config[0].get("Subnet", "-")
    except Exception:
        pass
    return "-"
