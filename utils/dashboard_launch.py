"""Start or open the AgriVision admin web dashboard from the desktop app."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_INDEX = REPO_ROOT / "web" / "frontend" / "dist" / "index.html"
ENV_FILE = REPO_ROOT / ".env.deploy"
LOG_PATH = REPO_ROOT / "output" / "dashboard.log"

_child: subprocess.Popen | None = None
_log_handle = None


def dashboard_port() -> int:
    raw = os.environ.get("AGRIVISION_DASHBOARD_PORT", "8077").strip()
    try:
        return int(raw)
    except ValueError:
        return 8077


def dashboard_url() -> str:
    return f"http://127.0.0.1:{dashboard_port()}"


def frontend_built() -> bool:
    return FRONTEND_INDEX.is_file()


def is_listening(host: str = "127.0.0.1", port: int | None = None) -> bool:
    port = dashboard_port() if port is None else port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex((host, port)) == 0


def _load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            values[key] = val
    return values


def start_api() -> subprocess.Popen:
    """Spawn uvicorn in the background. Raises RuntimeError if it cannot start."""
    global _child, _log_handle

    if is_listening():
        if _child is not None:
            return _child
        raise RuntimeError("Dashboard port is already in use.")

    env = os.environ.copy()
    env.update(_load_dotenv(ENV_FILE))

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _log_handle is None:
        _log_handle = open(LOG_PATH, "a", encoding="utf-8")
    _log_handle.write(f"\n--- starting dashboard on port {dashboard_port()} ---\n")
    _log_handle.flush()

    kwargs: dict = {
        "cwd": str(REPO_ROOT),
        "env": env,
        "stdout": _log_handle,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        # Hide the console; keep the process after the desktop app closes.
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )

    try:
        _child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "web.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(dashboard_port()),
            ],
            **kwargs,
        )
    except OSError as exc:
        raise RuntimeError(
            "Could not start the admin dashboard.\n\n"
            "Install API packages from the repo root:\n"
            "  py -3.10 -m pip install -r web/requirements.txt"
        ) from exc
    return _child


def open_in_browser() -> str:
    url = dashboard_url()
    webbrowser.open(url)
    return url
