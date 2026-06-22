"""Background geo lookup (Windows GPS / IP fallback)."""

from PyQt5.QtCore import QThread, pyqtSignal

from backend.geo import detect_my_location, format_location_label


class GeoLocateWorker(QThread):
    ready = pyqtSignal(float, float, str, str, float)
    failed = pyqtSignal(str)

    def run(self) -> None:
        found = detect_my_location()
        if found is None:
            self.failed.emit(
                "GPS unavailable. Turn on Windows Location, allow browser GPS, or enter lat/lon manually."
            )
            return
        tag = found.tag
        label = format_location_label(found.label, found.accuracy_m, tag.source)
        acc = float(found.accuracy_m or 0.0)
        self.ready.emit(tag.latitude, tag.longitude, label, tag.source, acc)
