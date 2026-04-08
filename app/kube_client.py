"""Kubernetes client wrapper — gracefully handles missing kubeconfig or unreachable cluster."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generator

try:
    from kubernetes import client, config, watch
    from kubernetes.config.config_exception import ConfigException
    KUBE_SDK = True
except ImportError:
    KUBE_SDK = False


class KubeClient:
    def __init__(self) -> None:
        self.available: bool = False
        self.error: str = ""
        self.current_context: str = ""
        self.contexts: list[str] = []
        self._core: Any = None
        self._apps: Any = None
        self._init()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init(self) -> None:
        if not KUBE_SDK:
            self.error = "kubernetes Python SDK not installed"
            return
        try:
            ctx_list, active = config.list_kube_config_contexts()
            self.contexts = [c["name"] for c in ctx_list]
            self.current_context = active["name"] if active else (self.contexts[0] if self.contexts else "")
            self._load_context(self.current_context)
        except ConfigException as exc:
            self.error = f"No kubeconfig found: {exc}"
        except Exception as exc:
            self.error = str(exc)

    def _load_context(self, context: str) -> None:
        try:
            config.load_kube_config(context=context)
            self._core = client.CoreV1Api()
            self._apps = client.AppsV1Api()
            # Connectivity probe — fast timeout
            self._core.list_namespace(limit=1, _request_timeout=5)
            self.available = True
            self.error = ""
        except Exception as exc:
            self.available = False
            self.error = str(exc)

    # ------------------------------------------------------------------
    # Context switching
    # ------------------------------------------------------------------

    def switch_context(self, name: str) -> bool | str:
        try:
            self._load_context(name)
            if self.available:
                self.current_context = name
                return True
            return self.error
        except Exception as exc:
            return str(exc)

    # ------------------------------------------------------------------
    # Pods
    # ------------------------------------------------------------------

    def list_pods(self) -> list[dict]:
        if not self.available:
            return []
        try:
            pods = self._core.list_pod_for_all_namespaces(_request_timeout=10)
            return [
                {
                    "name": p.metadata.name,
                    "namespace": p.metadata.namespace,
                    "status": _pod_phase(p),
                    "ready": _pod_ready(p),
                    "restarts": _pod_restarts(p),
                    "node": p.spec.node_name or "-",
                    "age": _age(p.metadata.creation_timestamp),
                    "_namespace": p.metadata.namespace,
                }
                for p in pods.items
            ]
        except Exception:
            return []

    def delete_pod(self, name: str, namespace: str) -> bool | str:
        if not self.available:
            return "Kubernetes not available"
        try:
            self._core.delete_namespaced_pod(name, namespace)
            return True
        except Exception as exc:
            return str(exc)

    def describe_pod(self, name: str, namespace: str) -> dict:
        if not self.available:
            return {}
        try:
            return self._core.read_namespaced_pod(name, namespace).to_dict()
        except Exception:
            return {}

    def stream_pod_logs(self, name: str, namespace: str, tail: int = 200) -> Generator[str, None, None]:
        if not self.available:
            return
        try:
            w = watch.Watch()
            for line in w.stream(
                self._core.read_namespaced_pod_log,
                name=name,
                namespace=namespace,
                tail_lines=tail,
                follow=True,
                _request_timeout=0,  # no timeout on streaming
            ):
                yield line
        except Exception as exc:
            yield f"[error] {exc}"

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def list_nodes(self) -> list[dict]:
        if not self.available:
            return []
        try:
            nodes = self._core.list_node(_request_timeout=10)
            return [
                {
                    "name": n.metadata.name,
                    "status": _node_status(n),
                    "roles": _node_roles(n),
                    "version": (n.status.node_info.kubelet_version if n.status and n.status.node_info else "-"),
                    "os": (n.status.node_info.os_image if n.status and n.status.node_info else "-"),
                    "age": _age(n.metadata.creation_timestamp),
                    "_namespace": None,
                }
                for n in nodes.items
            ]
        except Exception:
            return []

    def describe_node(self, name: str) -> dict:
        if not self.available:
            return {}
        try:
            return self._core.read_node(name).to_dict()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def list_services(self) -> list[dict]:
        if not self.available:
            return []
        try:
            services = self._core.list_service_for_all_namespaces(_request_timeout=10)
            return [
                {
                    "name": s.metadata.name,
                    "namespace": s.metadata.namespace,
                    "type": s.spec.type or "-",
                    "cluster_ip": s.spec.cluster_ip or "-",
                    "external_ip": _svc_external_ip(s),
                    "ports": _svc_ports(s),
                    "age": _age(s.metadata.creation_timestamp),
                    "_namespace": s.metadata.namespace,
                }
                for s in services.items
            ]
        except Exception:
            return []

    def delete_service(self, name: str, namespace: str) -> bool | str:
        if not self.available:
            return "Kubernetes not available"
        try:
            self._core.delete_namespaced_service(name, namespace)
            return True
        except Exception as exc:
            return str(exc)

    def describe_service(self, name: str, namespace: str) -> dict:
        if not self.available:
            return {}
        try:
            return self._core.read_namespaced_service(name, namespace).to_dict()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Deployments
    # ------------------------------------------------------------------

    def list_deployments(self) -> list[dict]:
        if not self.available:
            return []
        try:
            deps = self._apps.list_deployment_for_all_namespaces(_request_timeout=10)
            return [
                {
                    "name": d.metadata.name,
                    "namespace": d.metadata.namespace,
                    "ready": f"{d.status.ready_replicas or 0}/{d.spec.replicas or 0}",
                    "up_to_date": str(d.status.updated_replicas or 0),
                    "available": str(d.status.available_replicas or 0),
                    "age": _age(d.metadata.creation_timestamp),
                    "_namespace": d.metadata.namespace,
                }
                for d in deps.items
            ]
        except Exception:
            return []

    def delete_deployment(self, name: str, namespace: str) -> bool | str:
        if not self.available:
            return "Kubernetes not available"
        try:
            self._apps.delete_namespaced_deployment(name, namespace)
            return True
        except Exception as exc:
            return str(exc)

    def describe_deployment(self, name: str, namespace: str) -> dict:
        if not self.available:
            return {}
        try:
            return self._apps.read_namespaced_deployment(name, namespace).to_dict()
        except Exception:
            return {}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _age(ts) -> str:
    if not ts:
        return "-"
    try:
        now = datetime.now(timezone.utc)
        delta = now - ts
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes = rem // 60
        if days > 0:
            return f"{days}d{hours}h"
        if hours > 0:
            return f"{hours}h{minutes}m"
        return f"{minutes}m"
    except Exception:
        return "-"


def _pod_phase(pod) -> str:
    try:
        return pod.status.phase or "-"
    except Exception:
        return "-"


def _pod_ready(pod) -> str:
    try:
        for c in (pod.status.conditions or []):
            if c.type == "Ready":
                return "True" if c.status == "True" else "False"
    except Exception:
        pass
    return "-"


def _pod_restarts(pod) -> str:
    try:
        statuses = pod.status.container_statuses or []
        return str(sum(cs.restart_count for cs in statuses))
    except Exception:
        return "0"


def _node_status(node) -> str:
    try:
        for c in (node.status.conditions or []):
            if c.type == "Ready":
                return "Ready" if c.status == "True" else "NotReady"
    except Exception:
        pass
    return "Unknown"


def _node_roles(node) -> str:
    try:
        labels = node.metadata.labels or {}
        roles = [k.split("/")[-1] for k in labels if "node-role.kubernetes.io/" in k]
        return ",".join(roles) if roles else "worker"
    except Exception:
        return "-"


def _svc_external_ip(svc) -> str:
    try:
        ingress = svc.status.load_balancer.ingress
        if ingress:
            return ingress[0].ip or ingress[0].hostname or "-"
    except Exception:
        pass
    return "<none>"


def _svc_ports(svc) -> str:
    try:
        parts = []
        for p in (svc.spec.ports or []):
            if p.node_port:
                parts.append(f"{p.port}:{p.node_port}/{p.protocol}")
            else:
                parts.append(f"{p.port}/{p.protocol}")
        return ",".join(parts) if parts else "-"
    except Exception:
        return "-"
