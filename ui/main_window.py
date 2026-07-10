import os
import sys
import time
from datetime import datetime
from pathlib import Path
import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFrame
from PyQt5.QtCore import QTimer, Qt

from utils.screen_capture import LiveMirrorCapture, pick_mirror_cast_window
from utils.cast_manager import MirrorManager, resolve_android_device_ip
from utils.win_util import configure_background_capture
from utils.phone_frame import is_live_video_frame
from utils.frame_quality import is_analyzable_frame
from utils.drawing import draw_boxes, draw_subtle_grid, detection_category
from utils.logger import log

from core.preprocess import FramePreprocessor

from backend.report import export_field_report
from backend.session import SessionRecorder
from backend.map_export import build_map_html, build_map_payload, write_map_html

from ui.components.feed_panel import PrimaryFeedPanel
from ui.components.sidebar import Sidebar
from ui.inference_worker import InferenceWorker
from ui.capture_worker import MirrorCaptureThread
from ui.geo_worker import GeoLocateWorker
from ui.android_ip_worker import AndroidIpWorker
from ui.browser_geo import BrowserGeoLocator, browser_geo_available
from backend.geo import should_auto_detect_location, format_location_label, default_field_bounds


def _apply_mirror_app_defaults() -> None:
    """Tuned for aerial banana canopy: more boxes per frame on small datasets."""
    for key, val in (
        ("AGRIVISION_TIMER_MS", "16"),
        ("AGRIVISION_INFER_EVERY", "12"),
        ("AGRIVISION_IMGSZ", "640"),
        ("AGRIVISION_INFER_MAX_SIDE", "1280"),
        ("AGRIVISION_WINDOW_MAX_W", "1920"),
        ("AGRIVISION_INFER_FRAME_MAX_W", "1280"),
        ("AGRIVISION_GRID", "0"),
        ("AGRIVISION_PHONE_CROP", "1"),
        ("AGRIVISION_PREPROC_ALIGN", "1"),
        ("AGRIVISION_CLS_MIN_CONF", "0.45"),
        ("AGRIVISION_INFER_MODE", "both"),
        ("AGRIVISION_DET_TILES", "4"),
        ("AGRIVISION_DET_TILE_OVERLAP", "0.25"),
        ("AGRIVISION_MAX_DET", "300"),
        ("AGRIVISION_DET_CONF", "0.30"),
        ("AGRIVISION_DET_IOU", "0.55"),
        ("AGRIVISION_DET_MIN_CONF", "0.35"),
        ("AGRIVISION_DET_MIN_AREA", "300"),
        ("AGRIVISION_MIN_TREE_BOXES", "6"),
        ("AGRIVISION_GRID_CLS", "5"),
        ("AGRIVISION_GRID_FALLBACK", "0"),
    ):
        os.environ.setdefault(key, val)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("MainRoot")
        self.setWindowTitle("AgriVision")
        self.setGeometry(0, 0, 1280, 800)
        self.setMinimumSize(800, 500)

        _apply_mirror_app_defaults()

        self._running = False
        self._last_frame_mono = None
        self._fps_ema = 0.0
        self._last_log_t = 0.0
        self._last_det_total = None

        self._frame_n = 0
        self._cached_dets = []
        self._last_stress = None
        self._exclude_rect = None
        self._timer_ms = int(os.environ.get("AGRIVISION_TIMER_MS", "16"))
        self._infer_every = max(1, int(os.environ.get("AGRIVISION_INFER_EVERY", "4")))
        self._geo_map_every = max(1, int(os.environ.get("AGRIVISION_GEO_MAP_EVERY", "90")))
        self._exclude_refresh_every = max(
            1, int(os.environ.get("AGRIVISION_EXCLUDE_REFRESH_EVERY", "15"))
        )

        self._mirror = MirrorManager()
        self._capture_window_title = ""
        self._capture = LiveMirrorCapture()
        self._capture_thread = MirrorCaptureThread(self._capture)
        self._last_capture_ver = -1
        self._analyzable_cached = False
        self._live_cached = False
        self._quality_every = max(
            1, int(os.environ.get("AGRIVISION_QUALITY_CHECK_EVERY", "5"))
        )
        self._preprocessor = FramePreprocessor()
        self._session = SessionRecorder()
        self._cast_ok_streak = 0
        self._last_display_frame = None
        self._drone_dot = None
        self._processing_dot = None

        self.init_ui()

        self._geo_worker = GeoLocateWorker()
        self._geo_worker.ready.connect(self._on_geo_detected, type=Qt.QueuedConnection)
        self._geo_worker.failed.connect(self._on_geo_failed, type=Qt.QueuedConnection)
        self._browser_geo = BrowserGeoLocator(self) if browser_geo_available() else None
        if self._browser_geo is not None:
            self._browser_geo.ready.connect(self._on_browser_geo_ready, type=Qt.QueuedConnection)
            self._browser_geo.failed.connect(self._on_browser_geo_failed, type=Qt.QueuedConnection)
        self.sidebar.btn_detect_geo.clicked.connect(self._start_geo_detect)
        self.sidebar.geo_updated.connect(self._refresh_leaflet_map)
        self.sidebar.report_export_requested.connect(self._on_export_field_report)
        self.sidebar.btn_open_map.clicked.connect(self._open_map_in_browser)
        self.sidebar.map_panel.field_area_drawn.connect(self._on_field_area_drawn)
        self.sidebar.map_panel.field_area_cleared.connect(self._on_field_area_cleared)
        self.sidebar.map_panel.manual_tag_added.connect(self._on_manual_tag_added)
        self.sidebar.map_panel.manual_tag_removed.connect(self._on_manual_tag_removed)
        self.sidebar.map_panel.manual_tags_cleared.connect(self._on_manual_tags_cleared)

        if should_auto_detect_location():
            QTimer.singleShot(300, self._start_geo_detect)
        else:
            self._refresh_leaflet_map()

        if not self.sidebar.mirror_android_ip():
            QTimer.singleShot(500, self._start_android_ip_detect)

        self._infer = InferenceWorker()
        self._infer.ready.connect(self._on_inference_ready, type=Qt.QueuedConnection)
        self._infer.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("headerBar")
        top_bar = QHBoxLayout(header)
        top_bar.setContentsMargins(12, 8, 12, 8)
        top_bar.setSpacing(10)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        title = QLabel("AgriVision")
        title.setObjectName("brandTitle")
        subtitle = QLabel("Aerial crop intelligence")
        subtitle.setObjectName("brandSubtitle")
        brand_col.addWidget(title)
        brand_col.addWidget(subtitle)

        status_wrap = QHBoxLayout()
        status_wrap.setSpacing(8)
        drone_chip, self._drone_dot = self._status_chip("Drone Connected")
        proc_chip, self._processing_dot = self._status_chip("Processing")
        status_wrap.addWidget(drone_chip)
        status_wrap.addWidget(proc_chip)
        self._set_status_dot(self._drone_dot, False)
        self._set_status_dot(self._processing_dot, False)

        top_bar.addLayout(brand_col)
        top_bar.addStretch(1)
        top_bar.addLayout(status_wrap)
        root.addWidget(header)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setObjectName("mainSplitter")
        self._splitter.setHandleWidth(4)
        self._splitter.setChildrenCollapsible(False)

        self.feed = PrimaryFeedPanel()
        self.sidebar = Sidebar()

        self.feed.btn_toggle.clicked.connect(self._on_toggle_feed)
        self.feed.btn_capture.clicked.connect(self.capture_frame)
        self.sidebar.mirror_start_requested.connect(self._on_mirror_start)
        self.sidebar.mirror_stop_requested.connect(self._on_mirror_stop)
        self.sidebar.android_ip_detect_requested.connect(self._start_android_ip_detect)

        self._splitter.addWidget(self.feed)
        self._splitter.addWidget(self.sidebar)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        root.addWidget(self._splitter, 1)

        self._apply_stylesheet()
        QTimer.singleShot(0, self._sync_splitter_sizes)
        QTimer.singleShot(0, self.feed._fit_landscape_display)

        if os.environ.get("AGRIVISION_AUTOSTART", "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            QTimer.singleShot(450, self.start)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "feed") and self.width() > 0:
            self._sync_splitter_sizes()
            self.feed._fit_landscape_display()

    def _sync_splitter_sizes(self) -> None:
        """Feed column uses all space left after the sidebar (~24% width cap)."""
        if not hasattr(self, "sidebar"):
            return
        total = max(400, self.width())
        side = min(self.sidebar.maximumWidth(), max(260, int(total * 0.26)))
        feed = max(200, total - side - self._splitter.handleWidth())
        self._splitter.setSizes([feed, side])

    def _apply_stylesheet(self):
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "styles", "style.qss")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except OSError:
            pass

    def _status_chip(self, text: str):
        row = QFrame()
        row.setObjectName("statusChip")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(4, 4, 12, 4)
        lay.setSpacing(5)
        dot = QLabel("●")
        dot.setObjectName("statusDotIdle")
        lab = QLabel(text)
        lab.setObjectName("statusPill")
        lay.addWidget(dot)
        lay.addWidget(lab)
        return row, dot

    def _set_status_dot(self, dot: QLabel, active: bool) -> None:
        if dot is None:
            return
        dot.setObjectName("statusDotOk" if active else "statusDotIdle")
        dot.style().unpolish(dot)
        dot.style().polish(dot)

    def _update_cast_status(self, live: bool) -> None:
        if live:
            self._cast_ok_streak = min(30, self._cast_ok_streak + 1)
        else:
            self._cast_ok_streak = 0

        cast_ok = self._cast_ok_streak >= 3
        processing_ok = bool(self._running and cast_ok)
        self._set_status_dot(self._drone_dot, cast_ok)
        self._set_status_dot(self._processing_dot, processing_ok)

    def _on_toggle_feed(self):
        if self._running:
            self.stop()
        else:
            self.start()

    def start(self):
        self._running = True
        self._frame_n = 0
        self._cast_ok_streak = 0
        self._exclude_rect = None
        self._last_capture_ver = -1
        self._capture.reset()
        self._preprocessor.reset()
        self._session.reset()
        self._infer.set_active(True)
        self._capture_thread.set_title(self._capture_window_title)
        self._capture_thread.start_capture()
        self.timer.start(max(1, self._timer_ms))
        self.feed.set_running(True)
        self._set_status_dot(self._drone_dot, False)
        self._set_status_dot(self._processing_dot, False)

    def stop(self):
        self._running = False
        self._cast_ok_streak = 0
        self._infer.set_active(False)
        self.timer.stop()
        self._capture_thread.stop_capture()
        self.feed.set_running(False)
        self._set_status_dot(self._drone_dot, False)
        self._set_status_dot(self._processing_dot, False)

    def closeEvent(self, event):
        try:
            if getattr(self, "_capture_thread", None) is not None:
                self._capture_thread.stop_capture()
            if getattr(self, "_geo_worker", None) is not None and self._geo_worker.isRunning():
                self._geo_worker.wait(3000)
            if getattr(self, "_infer", None) is not None:
                self._infer.shutdown()
                self._infer = None
            if getattr(self, "_mirror", None) is not None:
                self._mirror.stop()
        finally:
            super().closeEvent(event)

    def _on_inference_ready(self, dets, stress_map, summary, vegetation):
        self._cached_dets = dets
        if stress_map is not None:
            self._last_stress = stress_map
        if summary:
            self._session.record_analysis(summary, vegetation)

    def _start_android_ip_detect(self) -> None:
        worker = getattr(self, "_android_ip_worker", None)
        if worker is not None and worker.isRunning():
            return
        self.sidebar.set_android_ip_detect_enabled(False)
        self.sidebar.set_mirror_status("Mirror: detecting phone on hotspot…")
        self._android_ip_worker = AndroidIpWorker()
        self._android_ip_worker.ready.connect(self._on_android_ip_detected, type=Qt.QueuedConnection)
        self._android_ip_worker.failed.connect(self._on_android_ip_failed, type=Qt.QueuedConnection)
        self._android_ip_worker.finished.connect(
            lambda: self.sidebar.set_android_ip_detect_enabled(True),
            type=Qt.QueuedConnection,
        )
        self._android_ip_worker.start()

    def _on_android_ip_detected(self, ip: str, source: str) -> None:
        self.sidebar.set_android_ip(ip)
        label = {"adb": "ADB", "mdns": "wireless debugging", "hotspot": "laptop hotspot"}.get(
            source, source
        )
        self.sidebar.set_mirror_status(f"Phone detected: {ip} ({label})")
        self.sidebar.add_log(log(f"Android IP auto-detected: {ip} ({label})"))
        QTimer.singleShot(800, self._retry_phone_gps_if_needed)

    def _retry_phone_gps_if_needed(self) -> None:
        geo = self.sidebar.geo_tag()
        if geo.source == "android_gps":
            return
        if self._geo_worker.isRunning():
            return
        self.sidebar.add_log(log("Phone connected — reading GPS from phone…"))
        self._start_geo_detect()

    def _on_android_ip_failed(self, message: str) -> None:
        self.sidebar.set_mirror_status("Mirror: phone not found (USB or enter IP manually)")
        self.sidebar.add_log(log(message))

    def _on_mirror_start(self) -> None:
        self.sidebar.set_mirror_status("Mirror: starting…")
        device_ip = self.sidebar.mirror_android_ip()
        if not device_ip:
            resolved_ip, source = resolve_android_device_ip("")
            if resolved_ip:
                self.sidebar.set_android_ip(resolved_ip)
                device_ip = resolved_ip
                label = {"adb": "ADB", "mdns": "wireless debugging", "hotspot": "laptop hotspot"}.get(
                    source, source
                )
                self.sidebar.add_log(log(f"Using detected Android IP: {resolved_ip} ({label})"))
        result = self._mirror.start_android(
            device_ip=device_ip,
            quality=self.sidebar.mirror_quality(),
        )

        self.sidebar.add_log(log(result.message))
        if not result.ok:
            self.sidebar.set_mirror_status(f"Mirror: {result.message}")
            return

        self.sidebar.set_mirror_status(result.message)
        self.sidebar.set_mirror_running(True)
        self._capture_window_title = result.window_title or ""
        # Give scrcpy time to create its window, then configure it:
        # full-screen size for max capture resolution, hidden from taskbar.
        QTimer.singleShot(2500, self._configure_scrcpy_display)
        if not self._running:
            QTimer.singleShot(1200, self.start)

    def _configure_scrcpy_display(self) -> None:
        """Run after scrcpy starts: resize its window to fill the monitor so
        PrintWindow captures at the highest possible resolution, then hide it
        from the taskbar and bring AgriVision back on top."""
        title = self._capture_window_title
        if not title:
            return

        win = pick_mirror_cast_window(title)
        if win is None:
            # Window not ready yet — retry once more
            QTimer.singleShot(2000, self._configure_scrcpy_display)
            return

        scrcpy_hwnd = int(getattr(win, "_hWnd", 0) or 0)
        if not scrcpy_hwnd:
            return

        agrivision_hwnd = int(self.winId())
        ok = configure_background_capture(scrcpy_hwnd, agrivision_hwnd)
        if ok:
            # Force cache reset so LiveMirrorCapture re-resolves at the new size
            self._capture_thread.set_title(self._capture_window_title)
            if self._capture_thread.isRunning():
                self._capture_thread.request_reset()
            else:
                self._capture.reset()
            self.sidebar.add_log(log("Mirror window configured: full-screen background capture active."))

    def _on_mirror_stop(self) -> None:
        self._mirror.stop()
        self._capture_thread.stop_capture()
        self._capture_window_title = ""
        self.sidebar.set_mirror_running(False)
        self.sidebar.set_mirror_status("Mirror: stopped")
        self.sidebar.add_log(log("Built-in mirror stopped."))

    def _exclude_screen_rect(self):
        """Screen rect to mask on desktop (MSS) fallback grabs only.

        PrintWindow capture on Windows reads the scrcpy window directly (like OBS), so overlap
        does not need masking; this is used only if window capture fails.
        """
        if self._exclude_rect is not None and (
            self._frame_n % self._exclude_refresh_every
        ) != 0:
            return self._exclude_rect

        vid = self.feed.video
        tl = vid.mapToGlobal(vid.rect().topLeft())
        br = vid.mapToGlobal(vid.rect().bottomRight())
        m = 6
        w = br.x() - tl.x() + 1 + 2 * m
        h = br.y() - tl.y() + 1 + 2 * m
        self._exclude_rect = (tl.x() - m, tl.y() - m, w, h)
        return self._exclude_rect

    def _capture_source_bgr(self):
        return self._capture.grab(
            self._capture_window_title,
            exclude_screen_rect=self._exclude_screen_rect(),
        )

    def _preprocess_frame(self, frame):
        if frame is None or frame.size == 0:
            return frame
        return self._preprocessor.process(frame)

    def _display_frame(self, raw_capture):
        """Light path for UI — no heavy preprocess (that runs in the inference worker)."""
        if raw_capture is None or raw_capture.size == 0:
            return raw_capture
        return raw_capture

    def _infer_frame(self, raw_capture):
        """Downscale for YOLO so the UI can keep full-res mirror capture."""
        if raw_capture is None or raw_capture.size == 0:
            return raw_capture
        max_w = int(os.environ.get("AGRIVISION_INFER_FRAME_MAX_W", "640") or "640")
        if max_w <= 0 or raw_capture.shape[1] <= max_w:
            return raw_capture
        scale = max_w / float(raw_capture.shape[1])
        new_h = max(1, int(round(raw_capture.shape[0] * scale)))
        return cv2.resize(raw_capture, (max_w, new_h), interpolation=cv2.INTER_AREA)

    def _annotated_capture_frame(self, frame, detections):
        """Match live-feed overlays: optional grid + detection bounding boxes."""
        vis = frame.copy()
        grid_on = (os.environ.get("AGRIVISION_GRID") or "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        if grid_on:
            vis = draw_subtle_grid(vis)
        return draw_boxes(vis, detections)

    def _latest_frame_bgr(self, *, fresh: bool = False):
        """Best available BGR frame for export (display cache, capture thread, or direct grab)."""
        if not fresh and self._last_display_frame is not None and self._last_display_frame.size > 0:
            return self._last_display_frame
        if self._capture_thread.isRunning():
            frame, _ = self._capture_thread.latest()
            if frame is not None and frame.size > 0:
                return self._display_frame(frame)
        frame = self._capture_source_bgr()
        if frame is None or frame.size == 0:
            return None
        return self._display_frame(frame)

    def _run_field_report_export(self, *, save_captured_jpg: bool = False) -> dict[str, str] | None:
        frame = self._latest_frame_bgr(fresh=save_captured_jpg)
        if frame is None or frame.size == 0:
            return None
        detections = list(self._cached_dets)
        annotated = self._annotated_capture_frame(frame, detections)
        if save_captured_jpg:
            cv2.imwrite("captured_frame.jpg", annotated)

        paths = export_field_report(
            annotated,
            detections,
            self._last_stress,
            video_source=self.sidebar.video_source(),
            geo=self.sidebar.geo_tag(),
            session=self._session.to_dict(),
            vegetation=self._session.last_vegetation,
            heat_points=self._session.heatmap_for_display(),
            geo_markers=self._session.geo_markers,
            field_bounds=self._field_bounds_for_session(),
            manual_tags=self._session.manual_tags,
        )
        return paths

    def _log_export_paths(self, paths: dict[str, str]) -> None:
        self.sidebar.add_log(f"Report JSON: {paths.get('json', '')}")
        self.sidebar.add_log(f"Report CSV: {paths.get('csv', '')}")
        if paths.get("map"):
            self.sidebar.add_log(f"Leaflet map: {paths['map']}")
        if paths.get("frame"):
            self.sidebar.add_log(f"Annotated frame: {paths['frame']}")

    def _reveal_export_folder(self, paths: dict[str, str]) -> None:
        folder = Path(paths.get("json") or paths.get("map") or "output/reports").parent
        try:
            if sys.platform == "win32":
                os.startfile(str(folder.resolve()))  # noqa: S606
            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(["open", str(folder.resolve())])
            else:
                import subprocess

                subprocess.Popen(["xdg-open", str(folder.resolve())])
        except OSError:
            self.sidebar.add_log(f"Reports folder: {folder.resolve()}")

    def _on_export_field_report(self) -> None:
        self.sidebar.btn_export_report.setEnabled(False)
        try:
            paths = self._run_field_report_export()
            if not paths:
                self.sidebar.add_log("Export skipped (no frame — start mirror or feed first)")
                return
            self._log_export_paths(paths)
            self._reveal_export_folder(paths)
            self.feed.set_last_updated(f"Last updated: {self._clock_str()}")
        finally:
            self.sidebar.btn_export_report.setEnabled(True)

    def capture_frame(self):
        paths = self._run_field_report_export(save_captured_jpg=True)
        if not paths:
            self.sidebar.add_log("Capture skipped (no frame)")
            return
        self.sidebar.add_log("Frame captured and saved as captured_frame.jpg")
        self._log_export_paths(paths)
        self.feed.set_last_updated(f"Last updated: {self._clock_str()}")

    def _start_geo_detect(self) -> None:
        if self._geo_worker.isRunning():
            return
        self._browser_geo_tried = False
        self.sidebar.set_geo_detect_enabled(False)
        self.sidebar.set_geo_status("Location: detecting phone GPS / Wi‑Fi…")
        self._geo_worker.start()

    def _apply_geo_result(
        self, lat: float, lon: float, label: str, source: str, accuracy_m: float = 0.0
    ) -> None:
        self.sidebar.set_geo_coordinates(
            lat, lon, label=label, source=source, accuracy_m=accuracy_m
        )
        self.sidebar.set_geo_detect_enabled(True)
        self.sidebar.add_log(log(f"Location: {label} ({lat:.5f}, {lon:.5f})"))
        if accuracy_m >= 2000:
            self.sidebar.add_log(
                log("Low accuracy — enter exact plantation lat/lon for field mapping.")
            )

    def _on_browser_geo_ready(self, lat: float, lon: float, accuracy_m: float) -> None:
        if self.sidebar.geo_tag().source == "android_gps":
            self.sidebar.set_geo_detect_enabled(True)
            return
        label = format_location_label("Browser GPS", accuracy_m, "browser_gps")
        self._apply_geo_result(lat, lon, label, "browser_gps", accuracy_m)

    def _on_browser_geo_failed(self, message: str) -> None:
        self.sidebar.set_geo_status(f"Location: browser GPS failed")
        self.sidebar.add_log(log(f"Browser GPS: {message}"))
        self._finish_geo_failed(
            "GPS unavailable. Connect phone via hotspot + ADB, enable Location on phone, "
            "or enter lat/lon manually."
        )

    def _finish_geo_failed(self, message: str) -> None:
        from backend.geo import DEFAULT_LAT, DEFAULT_LON

        if not self.sidebar.lat_edit.text().strip():
            self.sidebar.set_geo_coordinates(
                DEFAULT_LAT,
                DEFAULT_LON,
                label="Compostela Valley (fallback)",
                source="default",
            )
        self.sidebar.set_geo_status(f"Location: {message}")
        self.sidebar.set_geo_detect_enabled(True)
        self.sidebar.add_log(log(message))

    def _on_geo_detected(
        self, lat: float, lon: float, label: str, source: str, accuracy_m: float
    ) -> None:
        self._apply_geo_result(lat, lon, label, source, accuracy_m)

    def _on_geo_failed(self, message: str) -> None:
        if self.sidebar.geo_tag().source == "android_gps":
            self.sidebar.set_geo_detect_enabled(True)
            return
        if self._browser_geo is not None and not getattr(self, "_browser_geo_tried", False):
            self._browser_geo_tried = True
            self.sidebar.set_geo_status("Location: trying laptop Wi‑Fi GPS…")
            self._browser_geo.locate()
            return
        self._finish_geo_failed(message)

    def _field_bounds_for_session(self):
        bounds = self.sidebar.field_bounds()
        if bounds is not None:
            return bounds
        return default_field_bounds(self.sidebar.geo_tag())

    def _on_field_area_drawn(
        self, south: float, west: float, north: float, east: float
    ) -> None:
        self.sidebar.set_field_bounds_quiet(south, west, north, east)
        self._session.heatmap_points = []
        self.sidebar.add_log(log("Field area set on map."))

    def _on_field_area_cleared(self) -> None:
        self.sidebar.clear_field_bounds()
        self._session.heatmap_points = []
        self.sidebar.add_log(log("Field area cleared."))
        self._refresh_leaflet_map()

    def _on_manual_tag_added(self, lat: float, lon: float, category: str) -> None:
        self._session.add_manual_tag(lat, lon, category)
        labels = {"healthy": "Healthy", "stressed": "Moderate", "diseased": "High stress"}
        self.sidebar.set_manual_tag_status(len(self._session.manual_tags))
        self.sidebar.add_log(
            log(f"Manual tag: {labels.get(category, category)} at {lat:.6f}, {lon:.6f}")
        )

    def _on_manual_tag_removed(self, lat: float, lon: float, category: str) -> None:
        if self._session.remove_manual_tag(lat, lon, category):
            labels = {"healthy": "Healthy", "stressed": "Moderate", "diseased": "High stress"}
            self.sidebar.set_manual_tag_status(len(self._session.manual_tags))
            self.sidebar.add_log(
                log(f"Removed tag: {labels.get(category, category)} at {lat:.6f}, {lon:.6f}")
            )
            if not self._session.manual_tags:
                self._refresh_leaflet_map()

    def _on_manual_tags_cleared(self) -> None:
        self._session.clear_manual_tags()
        self.sidebar.set_manual_tag_status(0)
        self.sidebar.add_log(log("Manual tags cleared."))
        self._refresh_leaflet_map()

    def _map_payload(self) -> dict:
        geo = self.sidebar.geo_tag()
        payload = build_map_payload(
            center_lat=geo.latitude,
            center_lon=geo.longitude,
            heat_points=self._session.heatmap_for_display(),
            markers=[],
            manual_tags=self._session.manual_tags,
            field_bounds=self._field_bounds_for_session(),
            accuracy_m=geo.accuracy_m,
            altitude_m=geo.altitude_m,
            source=geo.source,
        )
        return payload

    def _write_live_map_file(self, map_data: dict) -> Path:
        from backend.map_export import build_map_html, write_map_html

        geo = self.sidebar.geo_tag()
        html = build_map_html(
            center_lat=geo.latitude,
            center_lon=geo.longitude,
            heat_points=map_data["heatPoints"],
            markers=[],
            manual_tags=self._session.manual_tags,
            field_bounds=self._field_bounds_for_session(),
            accuracy_m=geo.accuracy_m,
            altitude_m=geo.altitude_m,
            source=geo.source,
        )
        path = write_map_html(html, "output/maps/live_map.html")
        self.sidebar.map_panel.set_map_file(path)
        return Path(path)

    def _open_map_in_browser(self) -> None:
        map_data = self._map_payload()
        self._write_live_map_file(map_data)
        self.sidebar.map_panel.open_in_browser()

    def _refresh_leaflet_map(self) -> None:
        map_data = self._map_payload()
        path = self._write_live_map_file(map_data)
        if not self.sidebar.map_panel.needs_map_reload() and self.sidebar.map_panel.update_map_data(map_data):
            self.sidebar.set_manual_tag_status(len(self._session.manual_tags))
            return

        html = path.read_text(encoding="utf-8")
        self.sidebar.update_leaflet_map(html, path, map_data)
        self.sidebar.set_manual_tag_status(len(self._session.manual_tags))

    def update_frame(self):
        raw_capture, ver = self._capture_thread.latest()
        if raw_capture is None or raw_capture.size == 0:
            self._update_cast_status(False)
            return
        # Skip redundant work when the capture thread has no new frame yet.
        if ver == self._last_capture_ver:
            return
        self._last_capture_ver = ver

        frame = self._display_frame(raw_capture)
        self._last_display_frame = frame
        self._session.record_frame()

        # Frame-quality analysis (grayscale passes) is expensive; recompute it on
        # a cadence and reuse the cached verdict so the display stays smooth.
        if self._frame_n % self._quality_every == 0:
            self._live_cached = is_live_video_frame(raw_capture)
            self._analyzable_cached = (
                self._live_cached and is_analyzable_frame(raw_capture)
            )
        analyzable = self._analyzable_cached

        now = time.monotonic()
        if self._last_frame_mono is not None:
            dt = now - self._last_frame_mono
            if dt > 1e-6:
                inst = 1.0 / dt
                self._fps_ema = (
                    0.88 * self._fps_ema + 0.12 * inst if self._fps_ema else inst
                )
        self._last_frame_mono = now
        if (self._frame_n % 3) == 0:
            fps = int(round(self._fps_ema)) if self._fps_ema else 0
            self.feed.set_fps_text(f"Real-time Processing • {fps} FPS")

        if analyzable and self._frame_n % self._infer_every == 0:
            self._infer.submit(self._infer_frame(raw_capture))
        elif not analyzable:
            self._cached_dets = []
            if (self._frame_n % 45) == 0:
                self.sidebar.add_log(log("Waiting for live banana leaf video…"))

        detections = self._cached_dets if analyzable else []

        grid_on = (os.environ.get("AGRIVISION_GRID") or "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        if not grid_on and not detections:
            vis = frame
        else:
            vis = frame.copy()
            if grid_on:
                vis = draw_subtle_grid(vis)
            vis = draw_boxes(vis, detections)
        self.feed.video.update_frame(vis)
        if (self._frame_n % 12) == 0:
            self.feed._fit_landscape_display()

        healthy = stressed = diseased = 0
        for det in detections:
            c = detection_category(det.get("label", ""))
            if c == "none":
                continue
            if c == "diseased":
                diseased += 1
            elif c == "stressed":
                stressed += 1
            else:
                healthy += 1
        total = len(detections)
        self.sidebar.update_stats(total, healthy, stressed, diseased)

        now_wall = time.time()
        if total != self._last_det_total or now_wall - self._last_log_t >= 3.0:
            self._last_det_total = total
            self._last_log_t = now_wall
            self.sidebar.add_log(log(f"{total} object(s) in frame"))

        self._update_cast_status(self._live_cached)
        self._frame_n += 1

        if (self._frame_n % 10) == 0:
            self.feed.set_last_updated(f"Last updated: {self._clock_str()}")

    @staticmethod
    def _clock_str():
        if sys.platform == "win32":
            return datetime.now().strftime("%#I:%M:%S %p")
        return datetime.now().strftime("%-I:%M:%S %p")
