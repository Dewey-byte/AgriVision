"""Loopback HTTP sync so the sidebar map and browser map share tags."""

from __future__ import annotations

import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
_PORT_SPAN = 16
_MAX_BODY = 64 * 1024


class LiveMapSync:
    """Serves live_map.html and a tiny JSON API on localhost."""

    def __init__(self, maps_dir: str | Path = "output/maps") -> None:
        self.maps_dir = Path(maps_dir)
        self._lock = threading.Lock()
        self.version = 0
        self.payload: dict[str, Any] = {}
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.port: int | None = None
        self.base_url: str | None = None

    def start(self) -> str | None:
        if self.httpd is not None:
            return self.base_url
        self.maps_dir.mkdir(parents=True, exist_ok=True)
        httpd: ThreadingHTTPServer | None = None
        port = DEFAULT_PORT
        for port in range(DEFAULT_PORT, DEFAULT_PORT + _PORT_SPAN):
            try:
                httpd = ThreadingHTTPServer((DEFAULT_HOST, port), _make_handler(self))
                httpd.daemon_threads = True
                break
            except OSError:
                httpd = None
        if httpd is None:
            return None
        self.httpd = httpd
        self.port = port
        self.base_url = f"http://{DEFAULT_HOST}:{port}"
        self.thread = threading.Thread(
            target=httpd.serve_forever,
            name="AgriVisionMapSync",
            daemon=True,
        )
        self.thread.start()
        return self.base_url

    def stop(self) -> None:
        httpd = self.httpd
        self.httpd = None
        if httpd is not None:
            try:
                httpd.shutdown()
            except Exception:
                pass
            try:
                httpd.server_close()
            except Exception:
                pass
        thread = self.thread
        self.thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self.port = None
        self.base_url = None

    def publish(self, payload: dict[str, Any]) -> int:
        with self._lock:
            self.payload = payload
            self.version += 1
            return self.version

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"version": self.version, "payload": self.payload}

    def push_event(self, event: dict[str, Any]) -> None:
        self.events.put(event)

    def drain_events(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                break
        return items


def _make_handler(sync: LiveMapSync) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Cache-Control", "no-store")

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/api/state", "/api/live-map"):
                body = json.dumps(sync.snapshot()).encode("utf-8")
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path in ("/", "/live_map.html"):
                html_path = sync.maps_dir / "live_map.html"
                if not html_path.is_file():
                    self.send_error(404, "No live map yet")
                    return
                data = html_path.read_bytes()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_error(404, "Not found")

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path != "/api/event":
                self.send_error(404, "Not found")
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length < 1 or length > _MAX_BODY:
                self.send_error(400, "Invalid body")
                return
            raw = self.rfile.read(length)
            try:
                event = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self.send_error(400, "Invalid JSON")
                return
            if not isinstance(event, dict) or not event.get("type"):
                self.send_error(400, "Expected event object")
                return
            sync.push_event(event)
            body = json.dumps({"ok": True, **sync.snapshot()}).encode("utf-8")
            self.send_response(202)
            self._cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler
