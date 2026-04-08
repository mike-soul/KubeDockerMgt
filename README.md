# KubeDock

A terminal UI for managing Docker containers and Kubernetes clusters — a lightweight, no-license alternative to Docker Desktop for corporate environments.

![Python](https://img.shields.io/badge/python-3.12+-blue) ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Tabs** for Containers, Volumes, Networks (Docker) and Pods, Nodes, Services, Deployments (Kubernetes)
- **Live log streaming** — tail follow any container or pod
- **Full inspect** — JSON detail view for any resource
- **Start / Stop / Delete** with confirmation prompts
- **Context switching** — pick from all available Docker and Kubernetes contexts at runtime
- Works if **only Docker**, **only Kubernetes**, or **both** are present — missing backends are silently skipped
- No Docker Desktop, no license fees, runs over SSH

---

## Keybindings

| Key | Action |
|-----|--------|
| `Tab` | Switch to next tab |
| `↑ / ↓` | Navigate list |
| `Enter` | Open action menu for selected item |
| `R` | Refresh current tab |
| `D` | Switch Docker context |
| `K` | Switch Kubernetes context |
| `Esc` | Close overlay / go back |
| `Q` | Quit |

---

## Installation

### One-liner (no admin required)

```powershell
irm https://raw.githubusercontent.com/mike-soul/KubeDockerMgt/main/install.ps1 | iex
```

This will:
1. Install Python 3.12 per-user via `winget` if not already present (no admin needed)
2. Copy the app to `%LOCALAPPDATA%\KubeDock\`
3. Create an isolated Python venv and install dependencies
4. Add a `kubedock` command to your user PATH

Open a new terminal after install, then run:

```powershell
kubedock
```

### From a local directory or network share

```powershell
# Clone or copy the repo, then:
.\install.ps1

# Or point at a UNC path:
.\install.ps1 -SourcePath "\\fileserver\tools\kubedock"
```

### Manual (any OS)

```bash
pip install -r requirements.txt
python main.py
```

---

## Requirements

- Python 3.12+
- Docker (optional) — any version with the Docker socket accessible
- Kubernetes (optional) — a valid `kubeconfig` file (`~/.kube/config`)

Python dependencies are installed automatically by the installer or via `pip install -r requirements.txt`:

```
textual
docker
kubernetes
```

---

## Project Structure

```
kubedock/
├── main.py                      # Entry point
├── requirements.txt
├── install.ps1                  # No-admin Windows installer
└── app/
    ├── docker_client.py         # Docker SDK wrapper + context switching
    ├── kube_client.py           # Kubernetes client wrapper + context switching
    ├── tui.py                   # Root Textual app + CSS
    └── screens/
        ├── main_screen.py       # Tab bar, data tables, action dispatch
        ├── log_screen.py        # Live log streaming viewer
        ├── info_screen.py       # JSON inspect viewer
        └── modals.py            # Action menu, context switcher, confirm dialog
```

---

## Updating

Re-run the install script — it overwrites app files and updates dependencies in place, leaving your venv intact.

---

## Notes on corporate environments

- The installer uses `winget install --scope user` which writes to `%LOCALAPPDATA%` — no admin or IT ticket required
- No EXE is produced; the app runs as plain Python scripts inside a venv, which avoids antivirus false positives common with PyInstaller bundles
- All network calls go directly to the Docker socket or Kubernetes API — no telemetry, no external services
