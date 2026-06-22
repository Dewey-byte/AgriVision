import os
import sys
import time
from datetime import datetime
import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QFrame
from PyQt5.QtCore import QTimer, Qt

from utils.screen_capture import LiveMirrorCapture, pick_mirror_cast_window
from utils.cast_manager import MirrorManager
from utils.win_util import configure_background_capture
from utils.phone_frame import is_live_video_frame
from utils.frame_quality import is_analyzable_frame
from utils.drawing import draw_boxes, draw_subtle_grid, detection_category
from utils.logger import log

from core.preprocess import FramePreprocessor

from backend.report import export_field_report
from backend.session import SessionRecorder
from backend.map_export import build_map_html, write_map_html

from ui.components.feed_panel import PrimaryFeedPanel
from ui.components.sidebar import Sidebar
from ui.inference_worker import InferenceWorker
from ui.geo_worker import GeoLocateWorker
from ui.browser_geo import BrowserGeoLocator, browser_geo_available
from backend.geo import should_auto_detect_location, format_location_label


def _apply_mirror_app_defaults() -> None:
    for key, val in (
        ("AGRIVISION_TIMER_MS", "16"),
        ("AGRIVISION_INFER_EVERY", "25"),
        ("AGRIVISION_IMGSZ", "224"),
        ("AGRIVISION_INFER_MAX_SIDE", "320"),
        ("AGRIVISION_WINDOW_MAX_W", "0"),
        ("AGRIVISION_INFER_FRAME_MAX_W", "640"),
        ("AGRIVISION_GRID", "0"),
        ("AGRIVISION_PHONE_CROP", "1"),
        ("AGRIVISION_PREPROC_ALIGN", "0"),
        ("AGRIVISION_CLS_MIN_CONF", "0.55"),
        ("AGRIVISION_INFER_MODE", "both"),
        ("AGRIVISION_DET_TILES", "3"),
        ("AGRIVISION_MAX_DET", "80"),
        ("AGRIVISION_DET_MIN_CONF", "0.35"),
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
        self._exclude_rect = None
        self._timer_ms = int(os.environ.get("AGRIVISION_TIMER_MS", "16"))
        self._infer_every = max(1, int(os.environ.get("AGRIVISION_INFER_EVERY", "4")))
        self._geo_map_every = max(1, int(os.environ.get("AGRIVISION_GEO_MAP_EVERY", "30")))
        self._exclude_refresh_every = max(
            1, int(os.environ.get("AGRIVISION_EXCLUDE_REFRESH_EVERY", "15"))
        )

        self._mirror = MirrorManager()
        self._capture_window_title = ""
        self._capture = LiveMirrorCapture()
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

        if should_auto_detect_location():
            QTimer.singleShot(300, self._start_geo_detect)
        else:
            self._refresh_leaflet_map()

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
        self._capture.reset()
        self._preprocessor.reset()
        self._session.reset()
        self._infer.set_active(True)
        self.timer.start(max(1, self._timer_ms))
        self.feed.set_running(True)
        self._set_status_dot(self._drone_dot, False)
        self._set_status_dot(self._processing_dot, False)

    def stop(self):
        self._running = False
        self._cast_ok_streak = 0
        self._infer.set_active(False)
        self.timer.stop()
        self.feed.set_running(False)
        self._set_status_dot(self._drone_dot, False)
        self._set_status_dot(self._processing_dot, False)

    def closeEvent(self, event):
        try:
            if getattr(self, "_geo_worker", None) is not None and self._geo_worker.isRunning():
                self._geo_worker.wait(3000)
            if getattr(self, "_infer", None) is not None:
                self._infer.shutdown()
                self._infer = None
            if getattr(self, "_mirror", None) is not None:
                self._mirror.stop()
        finally:
            super().closeEvent(event)

    def _on_inference_ready(self, dets, summary):
        self._cached_dets = dets
        if summary:
            self._session.record_analysis(summary)

    def _on_mirror_start(self) -> None:
        self.sidebar.set_mirror_status("Mirror: starting…")
        result = self._mirror.start_android(
            device_ip=self.sidebar.mirror_android_ip(),
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
            self._capture.reset()
            self.sidebar.add_log(log("Mirror window configured: full-screen background capture active."))

    def _on_mirror_stop(self) -> None:
        self._mirror.stop()
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

    def capture_frame(self):
        frame = self._capture_source_bgr()
        if frame is None or frame.size == 0:
            self.sidebar.add_log("Capture skipped (no frame)")
            return
        frame = self._preprocess_frame(frame)
        cv2.imwrite("captured_frame.jpg", frame)

        paths = export_field_report(
            frame,
            self._cached_dets,
            video_source=self.sidebar.video_source(),
            geo=self.sidebar.geo_tag(),
            session=self._session.to_dict(),
            geo_markers=self._session.geo_markers,
        )
        self.sidebar.add_log("Frame captured and saved as captured_frame.jpg")
        self.sidebar.add_log(f"Report exported: {paths.get('json', 'output/reports')}")
        if paths.get("map"):
            self.sidebar.add_log(f"Leaflet map: {paths['map']}")
        self.feed.set_last_updated(f"Last updated: {self._clock_str()}")

    def _start_geo_detect(self) -> None:
        if self._geo_worker.isRunning():
            return
        self.sidebar.set_geo_detect_enabled(False)
        self.sidebar.set_geo_status("Location: detecting (high accuracy GPS / Wi‑Fi)…")
        if self._browser_geo is not None:
            self._browser_geo.locate()
        else:
            self._geo_worker.start()

    def _apply_geo_result(
        self, lat: float, lon: float, label: str, source: str, accuracy_m: float = 0.0
    ) -> None:
        self.sidebar.set_geo_coordinates(lat, lon, label=label, source=source)
        self.sidebar.set_geo_detect_enabled(True)
        self.sidebar.add_log(log(f"Location: {label} ({lat:.5f}, {lon:.5f})"))
        if accuracy_m >= 2000:
            self.sidebar.add_log(
                log("Low accuracy — enter exact plantation lat/lon for field mapping.")
            )

    def _on_browser_geo_ready(self, lat: float, lon: float, accuracy_m: float) -> None:
        label = format_location_label("Browser GPS", accuracy_m, "browser_gps")
        self._apply_geo_result(lat, lon, label, "browser_gps", accuracy_m)

    def _on_browser_geo_failed(self, message: str) -> None:
        self.sidebar.set_geo_status(f"Location: browser GPS failed — trying Windows…")
        self.sidebar.add_log(log(f"Browser GPS: {message}"))
        if not self._geo_worker.isRunning():
            self._geo_worker.start()

    def _on_geo_detected(
        self, lat: float, lon: float, label: str, source: str, accuracy_m: float
    ) -> None:
        self._apply_geo_result(lat, lon, label, source, accuracy_m)

    def _on_geo_failed(self, message: str) -> None:
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

    def _refresh_leaflet_map(self) -> None:
        geo = self.sidebar.geo_tag()
        html = build_map_html(
            center_lat=geo.latitude,
            center_lon=geo.longitude,
            markers=self._session.geo_markers,
        )
        path = write_map_html(html, "output/maps/live_map.html")
        self.sidebar.update_leaflet_map(html, path)

    def update_frame(self):
        raw_capture = self._capture_source_bgr()
        if raw_capture is None or raw_capture.size == 0:
            self._update_cast_status(False)
            return

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

        if analyzable and detections and self._frame_n % self._geo_map_every == 0:
            geo = self.sidebar.geo_tag()
            fh, fw = frame.shape[:2]
            self._session.record_geo_markers(geo, detections, (fh, fw))
            self._refresh_leaflet_map()

        self._update_cast_status(self._live_cached)
        self._frame_n += 1

        if (self._frame_n % 10) == 0:
            self.feed.set_last_updated(f"Last updated: {self._clock_str()}")

    @staticmethod
    def _clock_str():
        if sys.platform == "win32":
            return datetime.now().strftime("%#I:%M:%S %p")
        return datetime.now().strftime("%-I:%M:%S %p")
