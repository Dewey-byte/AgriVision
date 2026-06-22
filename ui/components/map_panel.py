"""Embedded Leaflet map (PyQtWebEngine) with browser fallback."""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView

    _HAS_WEBENGINE = True
except ImportError:
    QWebEngineView = None  # type: ignore[misc, assignment]
    _HAS_WEBENGINE = False


def _webengine_allowed() -> bool:
    if not _HAS_WEBENGINE:
        return False
    platform = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
    return platform not in ("offscreen", "minimal")


class MapPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("leafletMapPanel")
        self._last_path = Path("output/maps/live_map.html")
        self._view = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._hint = QLabel(
            "Leaflet map loads when processing starts.\n"
            "Requires internet for OpenStreetMap tiles."
        )
        self._hint.setWordWrap(True)
        self._hint.setObjectName("mutedLabel")
        root.addWidget(self._hint)

        self._open_btn = QPushButton("Open Leaflet Map")
        self._open_btn.setObjectName("btnSecondary")
        self._open_btn.setCursor(Qt.PointingHandCursor)
        self._open_btn.clicked.connect(self.open_in_browser)
        root.addWidget(self._open_btn)

        if _webengine_allowed():
            self._ensure_webview(root)

    def _ensure_webview(self, root: QVBoxLayout | None = None) -> None:
        if self._view is not None or not _webengine_allowed():
            return
        self._view = QWebEngineView()
        self._view.setMinimumHeight(120)
        self._view.setContextMenuPolicy(Qt.NoContextMenu)
        lay = root or self.layout()
        if lay is not None:
            lay.insertWidget(0, self._view)
        # The embedded map fills the panel; the placeholder hint and the
        # internal browser button are only needed as a no-WebEngine fallback
        # (the sidebar already provides an "Open Map in Browser" button).
        if self._hint is not None:
            self._hint.setVisible(False)
        if self._open_btn is not None:
            self._open_btn.setVisible(False)

    @property
    def last_map_path(self) -> Path:
        return self._last_path

    def load_map_html(self, html: str, file_path: Path | None = None) -> None:
        path = Path(file_path or self._last_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        self._last_path = path.resolve()

        if _webengine_allowed():
            self._ensure_webview()
        if self._view is not None:
            base = QUrl.fromLocalFile(str(path.parent) + "/")
            self._view.setHtml(html, base)
        self._open_btn.setEnabled(True)

    def open_in_browser(self) -> None:
        if self._last_path.is_file():
            webbrowser.open(self._last_path.resolve().as_uri())
