"""Embedded Leaflet map (PyQtWebEngine) with browser fallback."""

from __future__ import annotations

import json
import os
import webbrowser
from pathlib import Path

from PyQt5.QtCore import QObject, QUrl, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

try:
    from PyQt5.QtWebChannel import QWebChannel
    from PyQt5.QtWebEngineWidgets import QWebEngineView

    _HAS_WEBENGINE = True
except ImportError:
    QWebChannel = None  # type: ignore[misc, assignment]
    QWebEngineView = None  # type: ignore[misc, assignment]
    _HAS_WEBENGINE = False


def _webengine_allowed() -> bool:
    if not _HAS_WEBENGINE:
        return False
    platform = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
    return platform not in ("offscreen", "minimal")


class MapBridge(QObject):
    """Receives field-area rectangles and manual stress tags from the Leaflet map."""

    field_area_drawn = pyqtSignal(float, float, float, float)
    field_area_cleared = pyqtSignal()
    manual_tag_added = pyqtSignal(float, float, str)
    manual_tag_removed = pyqtSignal(float, float, str)
    manual_tags_cleared = pyqtSignal()

    @pyqtSlot(float, float, float, float)
    def onFieldAreaDrawn(self, south: float, west: float, north: float, east: float) -> None:
        self.field_area_drawn.emit(south, west, north, east)

    @pyqtSlot()
    def onFieldAreaCleared(self) -> None:
        self.field_area_cleared.emit()

    @pyqtSlot(float, float, str)
    def onManualTagAdded(self, lat: float, lon: float, category: str) -> None:
        self.manual_tag_added.emit(lat, lon, category)

    @pyqtSlot(float, float, str)
    def onManualTagRemoved(self, lat: float, lon: float, category: str) -> None:
        self.manual_tag_removed.emit(lat, lon, category)

    @pyqtSlot()
    def onManualTagsCleared(self) -> None:
        self.manual_tags_cleared.emit()


class MapPanel(QWidget):
    field_area_drawn = pyqtSignal(float, float, float, float)
    field_area_cleared = pyqtSignal()
    manual_tag_added = pyqtSignal(float, float, str)
    manual_tag_removed = pyqtSignal(float, float, str)
    manual_tags_cleared = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("leafletMapPanel")
        self._last_path = Path("output/maps/live_map.html")
        self._view = None
        self._html_loaded = False
        self._pending_draw = False
        self._map_js_version = 0
        self._bridge = MapBridge()
        self._bridge.field_area_drawn.connect(self.field_area_drawn.emit)
        self._bridge.field_area_cleared.connect(self.field_area_cleared.emit)
        self._bridge.manual_tag_added.connect(self.manual_tag_added.emit)
        self._bridge.manual_tag_removed.connect(self.manual_tag_removed.emit)
        self._bridge.manual_tags_cleared.connect(self.manual_tags_cleared.emit)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._hint = QLabel(
            "Use the map toolbar: Tag Healthy / Moderate / High Stress, then click locations.\n"
            "The heatmap updates automatically from your manual pins."
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
        self._view.loadFinished.connect(self._on_load_finished)

        channel = QWebChannel(self._view.page())
        channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(channel)

        lay = root or self.layout()
        if lay is not None:
            lay.insertWidget(0, self._view)
        if self._hint is not None:
            self._hint.setVisible(False)
        if self._open_btn is not None:
            self._open_btn.setVisible(False)

    @property
    def last_map_path(self) -> Path:
        return self._last_path

    def _on_load_finished(self, ok: bool) -> None:
        self._html_loaded = bool(ok)
        if ok:
            from backend.map_export import _MAP_JS_VERSION

            self._map_js_version = _MAP_JS_VERSION
            if self._pending_draw:
                self._pending_draw = False
                self.enable_field_draw()

    def needs_map_reload(self) -> bool:
        from backend.map_export import _MAP_JS_VERSION

        return self._map_js_version != _MAP_JS_VERSION

    def enable_field_draw(self) -> None:
        if self._view is None:
            return
        if not self._html_loaded:
            self._pending_draw = True
            return
        self._view.page().runJavaScript("window.agriVisionEnableDrawMode(true);")

    def clear_field_on_map(self) -> None:
        if self._view is not None and self._html_loaded:
            self._view.page().runJavaScript(
                "window.agriVisionSetFieldBounds(null, false);"
            )

    def update_map_data(self, map_data: dict) -> bool:
        if self._view is None or not self._html_loaded:
            return False
        payload = json.dumps(map_data)
        self._view.page().runJavaScript(
            f"window.agriVisionUpdateMap && window.agriVisionUpdateMap({payload});"
        )
        return True

    def load_map_html(
        self,
        html: str,
        file_path: Path | None = None,
        map_data: dict | None = None,
    ) -> None:
        path = Path(file_path or self._last_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        self._last_path = path.resolve()

        if _webengine_allowed():
            self._ensure_webview()
        if self._view is not None:
            if map_data is not None and self.update_map_data(map_data):
                pass
            else:
                base = QUrl.fromLocalFile(str(path.parent) + "/")
                self._html_loaded = False
                self._view.setHtml(html, base)
        self._open_btn.setEnabled(True)

    def set_map_file(self, path: Path) -> None:
        self._last_path = Path(path).resolve()

    def open_in_browser(self) -> None:
        if self._last_path.is_file():
            webbrowser.open(self._last_path.resolve().as_uri())
