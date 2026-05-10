import os
import sys
import time
from datetime import datetime

import cv2
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap

from utils.screen_capture import grab_letsview_cast
from utils.drawing import draw_boxes, draw_subtle_grid, detection_category
from utils.logger import log

from ui.components.feed_panel import PrimaryFeedPanel
from ui.components.sidebar import Sidebar
from ui.inference_worker import InferenceWorker


def _apply_letsview_app_defaults() -> None:
    for key, val in (
        ("AGRIVISION_TIMER_MS", "16"),
        ("AGRIVISION_NDVI_EVERY", "4"),
        ("AGRIVISION_IMGSZ", "320"),
        ("AGRIVISION_INFER_MAX_SIDE", "448"),
        ("AGRIVISION_EXG_MAX_W", "384"),
        ("AGRIVISION_WINDOW_MAX_W", "960"),
        ("AGRIVISION_GRID", "0"),
    ):
        os.environ.setdefault(key, val)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("MainRoot")
        self.setWindowTitle("AgriVision")
        self.setGeometry(100, 100, 1440, 820)

        _apply_letsview_app_defaults()

        self._running = False
        self._last_frame_mono = None
        self._fps_ema = 0.0
        self._last_log_t = 0.0
        self._last_det_total = None

        self._frame_n = 0
        self._cached_dets = []
        self._last_stress = None
        self._timer_ms = int(os.environ.get("AGRIVISION_TIMER_MS", "16"))
        self._ndvi_every = max(1, int(os.environ.get("AGRIVISION_NDVI_EVERY", "2")))

        self.init_ui()

        self._infer = InferenceWorker()
        self._infer.ready.connect(self._on_inference_ready, type=Qt.QueuedConnection)
        self._infer.start()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(18)

        # Header
        top_bar = QHBoxLayout()
        title = QLabel("AgriVision")
        title.setObjectName("brandTitle")

        status_wrap = QHBoxLayout()
        status_wrap.setSpacing(20)
        status_wrap.addWidget(self._status_chip("Drone Connected"))
        status_wrap.addWidget(self._status_chip("Processing"))

        top_bar.addWidget(title)
        top_bar.addStretch(1)
        top_bar.addLayout(status_wrap)
        main_layout.addLayout(top_bar)

        # Body
        content = QHBoxLayout()
        content.setSpacing(20)

        self.feed = PrimaryFeedPanel()
        self.sidebar = Sidebar()

        self.feed.btn_toggle.clicked.connect(self._on_toggle_feed)
        self.feed.btn_capture.clicked.connect(self.capture_frame)

        content.addWidget(self.feed, 3)
        content.addWidget(self.sidebar, 1)
        main_layout.addLayout(content, 1)

        self._apply_stylesheet()

        if os.environ.get("AGRIVISION_AUTOSTART", "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            QTimer.singleShot(450, self.start)

    def _apply_stylesheet(self):
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "styles", "style.qss")
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except OSError:
            pass

    def _status_chip(self, text: str) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        dot = QLabel("●")
        dot.setObjectName("statusDot")
        lab = QLabel(text)
        lab.setObjectName("statusPill")
        lay.addWidget(dot)
        lay.addWidget(lab)
        return row

    def _on_toggle_feed(self):
        if self._running:
            self.stop()
        else:
            self.start()

    def start(self):
        self._running = True
        self._frame_n = 0
        self._infer.set_active(True)
        self.timer.start(max(8, self._timer_ms))
        self.feed.set_running(True)

    def stop(self):
        self._running = False
        self._infer.set_active(False)
        self.timer.stop()
        self.feed.set_running(False)

    def closeEvent(self, event):
        try:
            if getattr(self, "_infer", None) is not None:
                self._infer.shutdown()
                self._infer = None
        finally:
            super().closeEvent(event)

    def _on_inference_ready(self, dets, stress):
        self._cached_dets = dets
        self._last_stress = stress

    def _exclude_screen_rect(self):
        """Only the live video area is blacked out in the grab, not the whole AgriVision window.

        That way LetsView can share one monitor: the sidebar/header can overlap LetsView
        without wiping the whole mirror (which used to leave a full-height black bar).
        """
        vid = self.feed.video
        tl = vid.mapToGlobal(vid.rect().topLeft())
        br = vid.mapToGlobal(vid.rect().bottomRight())
        m = 6
        w = br.x() - tl.x() + 1 + 2 * m
        h = br.y() - tl.y() + 1 + 2 * m
        return (tl.x() - m, tl.y() - m, w, h)

    def _capture_source_bgr(self):
        return grab_letsview_cast(
            self.sidebar.letsview_title_substring(),
            exclude_screen_rect=self._exclude_screen_rect(),
        )

    def capture_frame(self):
        frame = self._capture_source_bgr()
        if frame is None or frame.size == 0:
            self.sidebar.add_log("Capture skipped (no frame)")
            return
        cv2.imwrite("captured_frame.jpg", frame)
        self.sidebar.add_log("Frame captured and saved as captured_frame.jpg")
        self.feed.set_last_updated(f"Last updated: {self._clock_str()}")

    def update_frame(self):
        frame = self._capture_source_bgr()
        if frame is None or frame.size == 0:
            return

        now = time.monotonic()
        if self._last_frame_mono is not None:
            dt = now - self._last_frame_mono
            if dt > 1e-6:
                inst = 1.0 / dt
                self._fps_ema = (
                    0.88 * self._fps_ema + 0.12 * inst if self._fps_ema else inst
                )
        self._last_frame_mono = now
        fps = int(round(self._fps_ema)) if self._fps_ema else 0
        self.feed.set_fps_text(f"Real-time Processing • {fps} FPS")

        self._infer.submit(frame)

        detections = self._cached_dets

        grid_on = (os.environ.get("AGRIVISION_GRID") or "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        if grid_on:
            vis = draw_subtle_grid(frame.copy())
        else:
            vis = frame.copy()
        vis = draw_boxes(vis, detections)
        self.feed.video.update_frame(vis)

        healthy = stressed = diseased = 0
        for det in detections:
            c = detection_category(det.get("label", ""))
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

        if self._last_stress is not None and self._frame_n % self._ndvi_every == 0:
            ndvi_u8 = cv2.normalize(self._last_stress, None, 0, 255, cv2.NORM_MINMAX)
            ndvi_u8 = ndvi_u8.astype("uint8")
            heatmap = cv2.applyColorMap(ndvi_u8, cv2.COLORMAP_JET)
            rgb = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
            self.sidebar.update_ndvi(QPixmap.fromImage(img))

        self._frame_n += 1

        self.feed.set_last_updated(f"Last updated: {self._clock_str()}")

    @staticmethod
    def _clock_str():
        if sys.platform == "win32":
            return datetime.now().strftime("%#I:%M:%S %p")
        return datetime.now().strftime("%-I:%M:%S %p")
