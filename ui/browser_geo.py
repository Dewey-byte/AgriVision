"""High-accuracy browser geolocation via QWebEngine (Wi‑Fi / GPS)."""

from __future__ import annotations

import json
import os

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

try:
    from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView

    _HAS_WEBENGINE = True
except ImportError:
    QWebEnginePage = None  # type: ignore[misc, assignment]
    QWebEngineView = None  # type: ignore[misc, assignment]
    _HAS_WEBENGINE = False


def browser_geo_available() -> bool:
    if not _HAS_WEBENGINE:
        return False
    platform = (os.environ.get("QT_QPA_PLATFORM") or "").strip().lower()
    return platform not in ("offscreen", "minimal")


class _GeoPermissionPage(QWebEnginePage):
    def featurePermissionRequested(self, securityOrigin, feature):
        if feature == QWebEnginePage.Geolocation:
            self.setFeaturePermission(
                securityOrigin,
                feature,
                QWebEnginePage.PermissionGrantedByUser,
            )


_GEO_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body>
<script>
(function() {
  if (!navigator.geolocation) {
    document.title = 'ERR:no geolocation API';
    return;
  }
  navigator.geolocation.getCurrentPosition(
    function(p) {
      document.title = JSON.stringify({
        lat: p.coords.latitude,
        lon: p.coords.longitude,
        acc: p.coords.accuracy
      });
    },
    function(e) {
      document.title = 'ERR:' + (e.message || 'denied');
    },
    { enableHighAccuracy: true, maximumAge: 0, timeout: TIMEOUT_MS }
  );
})();
</script>
</body></html>"""


class BrowserGeoLocator(QObject):
    """Runs HTML5 geolocation on the Qt main thread (required for WebEngine)."""

    ready = pyqtSignal(float, float, float)
    failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)
        if browser_geo_available():
            self._view = QWebEngineView(parent)
            self._view.setFixedSize(1, 1)
            self._view.hide()
            self._view.setPage(_GeoPermissionPage(self._view))
            self._view.titleChanged.connect(self._on_title)

    def locate(self, timeout_ms: int | None = None) -> None:
        if self._view is None:
            self.failed.emit("PyQtWebEngine not available")
            return
        ms = int(timeout_ms or os.environ.get("AGRIVISION_BROWSER_GEO_TIMEOUT", "20000"))
        self._timer.start(ms + 2000)
        html = _GEO_HTML.replace("TIMEOUT_MS", str(ms))
        self._view.setHtml(html)

    def _on_timeout(self) -> None:
        self.failed.emit("Browser GPS timed out — enable Location in Windows Settings.")

    def _on_title(self, title: str) -> None:
        if not title or title == "about:blank":
            return
        if title.startswith("ERR:"):
            self._timer.stop()
            self.failed.emit(title[4:].strip() or "Browser GPS denied")
            return
        try:
            data = json.loads(title)
            lat = float(data["lat"])
            lon = float(data["lon"])
            acc = float(data.get("acc") or 0)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return
        self._timer.stop()
        self.ready.emit(lat, lon, acc)
